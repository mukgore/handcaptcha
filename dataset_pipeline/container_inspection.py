"""Independent ffprobe packet/track check for explicit CFR video candidates.

This does not prove anatomical masking, browser compatibility, rights or
attack resistance. Unknown/extra tracks and timing are rejected.
"""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from dataset_pipeline.storage import private_output


def _integer(value):
    if isinstance(value,bool) or not isinstance(value,(str,int)) or not re.fullmatch(r'-?[0-9]+',str(value)):
        raise ValueError('Explicit integer packet timestamp required')
    return int(value)


def analyze(probe, expected):
    count,width,height=(_integer(expected[k]) for k in ('frame_count','width','height'))
    fps=Fraction(str(expected['fps']))
    if min(count,width,height)<=0 or fps<=0:raise ValueError('Positive explicit candidate metadata required')
    reasons=[];streams=probe.get('streams',[]);packets=probe.get('packets',[])
    if not isinstance(streams,list) or len(streams)!=1 or streams[0].get('codec_type')!='video':
        return {'passed':False,'reasons':['exactly_one_video_track_required'],'track_count':len(streams) if isinstance(streams,list) else None}
    stream=streams[0];fmt=probe.get('format',{})
    if stream.get('codec_name') not in ('mpeg4','h264','hevc','vp9','av1'):reasons.append('unsupported_codec')
    if stream.get('width')!=width or stream.get('height')!=height:reasons.append('dimensions_differ')
    if stream.get('disposition',{}).get('attached_pic',0):reasons.append('poster_track_forbidden')
    if stream.get('side_data_list'):reasons.append('unreviewed_stream_side_data')
    allowed_format={'major_brand','minor_version','compatible_brands','encoder'}
    allowed_stream={'language','handler_name','vendor_id','encoder'}
    if set(fmt.get('tags',{}))-allowed_format or set(stream.get('tags',{}))-allowed_stream:
        reasons.append('unreviewed_metadata_fields')
    for tags in (fmt.get('tags',{}),stream.get('tags',{})):
        if 'encoder' in tags and not re.fullmatch(r'Lav[fc][0-9.]+(?: (?:mpeg4|libx264|h264|libx265|libvpx-vp9|libaom-av1))?',tags['encoder']):
            reasons.append('unreviewed_encoder_metadata')
    if not isinstance(packets,list) or len(packets)!=count:reasons.append('packet_count_differs')
    timing=None
    try:
        base=Fraction(stream['time_base'])
        if base<=0:raise ValueError('Invalid timebase')
        pts=[];dts=[];durations=[]
        for packet in packets:
            if packet.get('stream_index')!=stream['index'] or packet.get('side_data_list'):
                raise ValueError('Unknown packet stream or side data')
            pts.append(_integer(packet['pts'])*base);dts.append(_integer(packet['dts'])*base)
            if _integer(packet['duration'])<=0:raise ValueError('Packet duration missing')
            durations.append(_integer(packet['duration'])*base)
        if any(b<=a for a,b in zip(dts,dts[1:])):reasons.append('decode_timestamps_not_increasing')
        ordered=sorted(pts)
        if any(t<0 for t in ordered) or len(set(ordered))!=len(ordered):reasons.append('invalid_presentation_timestamps')
        tolerance=max(base/2,Fraction(1,1_000_000))
        if any(abs(value-Fraction(1,1)/fps)>max(base,Fraction(1,1_000_000)) for value in durations):
            reasons.append('packet_duration_differs_from_explicit_cfr')
        if any(abs(t-Fraction(i,1)/fps)>tolerance for i,t in enumerate(ordered)):
            reasons.append('presentation_timeline_differs_from_explicit_cfr')
        duration=Fraction(fmt['duration'])
        if abs(duration-Fraction(count,1)/fps)>max(base,Fraction(1,1_000_000)):
            reasons.append('container_duration_differs')
        timing={'time_base':str(base),'first_pts_seconds':float(ordered[0]) if ordered else None,
                'last_pts_seconds':float(ordered[-1]) if ordered else None,'duration_seconds':float(duration)}
    except (KeyError,ValueError,TypeError,ZeroDivisionError):
        reasons.append('missing_or_invalid_packet_timing')
    return {'passed':not reasons,'reasons':sorted(set(reasons)),'track_count':len(streams),
            'packet_count':len(packets) if isinstance(packets,list) else None,'codec':stream.get('codec_name'),
            'timing':timing,'scope':'single_primary_cfr_file_only','release_allowed':False}


def inspect_container(source, expected, output_dir, *, ffprobe=None, timeout_seconds=60, max_packets=20000):
    source=Path(source).resolve(strict=True)
    if not source.is_file() or source.suffix.lower()!='.mp4':raise ValueError('Local MP4 file required')
    executable=ffprobe or shutil.which('ffprobe')
    if not executable or not Path(executable).is_file():raise FileNotFoundError('ffprobe executable required for independent container inspection')
    if type(max_packets) is not int or not 1<=max_packets<=20000:raise ValueError('Bounded positive packet budget required')
    if _integer(expected['frame_count'])>max_packets:raise ValueError('Candidate exceeds packet budget')
    folder=private_output(output_dir);folder.mkdir(parents=True,exist_ok=False)
    def source_hash():
        h=hashlib.sha256()
        with source.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
        return h.hexdigest()
    before=source_hash()
    command=[str(executable),'-v','error','-protocol_whitelist','file','-f','mov',
             '-read_intervals','%+#'+str(max_packets+1),'-show_packets','-show_streams','-show_format','-of','json',str(source)]
    with (folder/'probe.json').open('xb') as stdout,(folder/'stderr.txt').open('xb') as stderr:
        result=subprocess.run(command,stdout=stdout,stderr=stderr,timeout=timeout_seconds)
    if result.returncode:raise ValueError('ffprobe rejected this file; private diagnostics retained')
    if (folder/'probe.json').stat().st_size>64*1024*1024:raise ValueError('Probe output exceeds inspection budget')
    probe=json.loads((folder/'probe.json').read_text(encoding='utf8'))
    if source_hash()!=before:raise ValueError('File changed during independent inspection')
    report={'schema_version':1,'artifact_sha256':before,'expected':expected,**analyze(probe,expected)}
    (folder/'inspection.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True);parser.add_argument('--expected-json',required=True)
    parser.add_argument('--output',required=True);parser.add_argument('--ffprobe')
    args=parser.parse_args();report=inspect_container(args.source,json.loads(Path(args.expected_json).read_text(encoding='utf8')),args.output,ffprobe=args.ffprobe)
    print(json.dumps({k:report[k] for k in ('passed','reasons','scope','release_allowed')}))
    raise SystemExit(0 if report['passed'] else 1)
