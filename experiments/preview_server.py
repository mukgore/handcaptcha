"""Loopback public research preview with single-byte-range support.

Private output roots and hidden files are never served. This is not the
registry-backed operating media service or a trusted capture endpoint.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from pathlib import Path
import re
import threading
from urllib.parse import unquote, urlsplit

ROOT=Path(__file__).resolve().parents[1]
BLOCKED={'pipeline_output','private_artifacts','private_tools','data','raw','reference','candidate','artifacts','release'}
PUBLIC={'.html','.js','.css','.png','.svg','.jpg','.jpeg','.mp4','.webm','.woff2','.ico'}
DEVICES={'con','prn','aux','nul'}|{f'{prefix}{i}' for prefix in ('com','lpt') for i in range(1,10)}


def byte_range(header, size):
    if header is None:return (0,size-1,False)
    if len(header)>128 or size<=0:raise ValueError('Unsatisfiable range')
    match=re.fullmatch(r'bytes=([0-9]*)-([0-9]*)',header)
    if not match or not any(match.groups()):raise ValueError('Unsupported byte range')
    first,last=match.groups()
    if not first:
        suffix=int(last)
        if suffix<=0:raise ValueError('Unsatisfiable range')
        return max(0,size-suffix),size-1,True
    start=int(first);end=min(int(last),size-1) if last else size-1
    if start>=size or end<start:raise ValueError('Unsatisfiable range')
    return start,end,True


def handler_for(root):
    root=Path(root).resolve(strict=True)
    class PreviewHandler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def _respond(self,status,body=b''):
            self.send_response(status);self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store');self.end_headers()
            if self.command!='HEAD':self.wfile.write(body)
        def _serve(self):
            if self.headers.get('Host') not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'):
                return self._respond(403)
            decoded=unquote(urlsplit(self.path).path)
            parts=decoded.strip('/').split('/') if decoded.strip('/') else []
            if '\\' in decoded or '\x00' in decoded or any(p.startswith('.') or p.casefold() in BLOCKED or ':' in p or p.casefold().split('.')[0] in DEVICES for p in parts):
                return self._respond(403)
            try:
                path=root.joinpath(*parts).resolve(strict=True)
                if path.is_dir():path=(path/'index.html').resolve(strict=True)
                if not path.is_relative_to(root) or not path.is_file():return self._respond(403)
                if any(p.startswith('.') or p.casefold() in BLOCKED for p in path.relative_to(root).parts):return self._respond(403)
                if path.suffix.lower() not in PUBLIC and path.name!='pool_manifest.json':return self._respond(403)
                with path.open('rb') as media:
                    size=path.stat().st_size
                    try:start,end,partial=byte_range(self.headers.get('Range'),size)
                    except ValueError:
                        self.send_response(416);self.send_header('Content-Range',f'bytes */{size}')
                        self.send_header('Content-Length','0');self.end_headers();return
                    length=max(0,end-start+1)
                    self.send_response(206 if partial else 200)
                    self.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
                    self.send_header('Content-Length',str(length));self.send_header('Accept-Ranges','bytes')
                    self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
                    self.send_header('Referrer-Policy','no-referrer')
                    if partial:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
                    self.end_headers()
                    if self.command=='HEAD':return
                    media.seek(start)
                    while length:
                        block=media.read(min(length,64*1024))
                        if not block:break
                        self.wfile.write(block);length-=len(block)
            except (FileNotFoundError,IsADirectoryError):self._respond(404)
            except (BrokenPipeError,ConnectionResetError):return
        def do_GET(self):self._serve()
        def do_HEAD(self):self._serve()
    return PreviewHandler


class PreviewServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,handler,max_connections=32):
        self.slots=threading.BoundedSemaphore(max_connections)
        super().__init__(address,handler)
    def get_request(self):
        request,address=super().get_request();request.settimeout(15);return request,address
    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):
            request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n');self.shutdown_request(request);return
        try:super().process_request(request,address)
        except BaseException:self.slots.release();raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=8767)
    args=parser.parse_args();server=PreviewServer(('127.0.0.1',args.port),handler_for(ROOT))
    print(f'Research preview: http://127.0.0.1:{server.server_port}/experiments/prod_palm_variants/',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
