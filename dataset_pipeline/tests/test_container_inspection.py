import copy
import unittest

from dataset_pipeline.container_inspection import analyze


class ContainerInspectionTests(unittest.TestCase):
    def setUp(self):
        self.expected={'frame_count':3,'width':32,'height':32,'fps':10}
        self.probe={'streams':[{'index':0,'codec_type':'video','codec_name':'mpeg4','width':32,'height':32,'time_base':'1/1000','tags':{'encoder':'Lavc61.1.1 mpeg4'}}],
                    'packets':[{'stream_index':0,'pts':i*100,'dts':i*100,'duration':100} for i in range(3)],'format':{'duration':'0.300000','tags':{'encoder':'Lavf61.1.1'}}}

    def test_exact_single_track_cfr_candidate_passes_only_this_inspection(self):
        report=analyze(self.probe,self.expected)
        self.assertTrue(report['passed']);self.assertFalse(report['release_allowed'])

    def test_extra_audio_subtitle_or_poster_track_is_rejected(self):
        for kind in ('audio','subtitle','attachment'):
            probe=copy.deepcopy(self.probe);probe['streams'].append({'index':1,'codec_type':kind})
            with self.subTest(kind=kind):self.assertFalse(analyze(probe,self.expected)['passed'])
        self.probe['streams'][0]['disposition']={'attached_pic':1}
        self.assertFalse(analyze(self.probe,self.expected)['passed'])

    def test_missing_duplicate_or_wrong_pts_and_duration_are_rejected(self):
        variants=[]
        for field,value in (('pts',None),('pts',0),('pts',250),('duration',0)):
            probe=copy.deepcopy(self.probe);probe['packets'][1][field]=value;variants.append(probe)
        probe=copy.deepcopy(self.probe);probe['format']['duration']='0.5';variants.append(probe)
        for probe in variants:self.assertFalse(analyze(probe,self.expected)['passed'])

    def test_b_frame_decode_order_can_have_reordered_unique_presentation_times(self):
        self.probe['packets'][1]['pts']=200;self.probe['packets'][2]['pts']=100
        self.assertTrue(analyze(self.probe,self.expected)['passed'])

    def test_unknown_metadata_side_data_and_dimensions_are_rejected(self):
        for modify in (lambda p:p['format']['tags'].update(reference='hidden'),lambda p:p['streams'][0].update(width=64),lambda p:p['packets'][0].update(side_data_list=[{'unknown':1}])):
            probe=copy.deepcopy(self.probe);modify(probe);self.assertFalse(analyze(probe,self.expected)['passed'])
