from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from experiments.preview_server import PreviewServer, handler_for


class PreviewRangeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'video.mp4').write_bytes(b'0123456789')
        self.server=PreviewServer(('127.0.0.1',0),handler_for(self.root))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop);self.base=f'http://127.0.0.1:{self.server.server_port}'
    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
    def test_full_and_partial_bytes_match_exactly(self):
        for header,expected,code in ((None,b'0123456789',200),('bytes=2-5',b'2345',206),('bytes=-3',b'789',206),('bytes=7-',b'789',206)):
            request=Request(self.base+'/video.mp4',headers={'Range':header} if header else {})
            with urlopen(request) as response:
                self.assertEqual(response.status,code);self.assertEqual(response.read(),expected)
                self.assertEqual(response.headers['Accept-Ranges'],'bytes')
    def test_head_and_unsatisfiable_range(self):
        with urlopen(Request(self.base+'/video.mp4',method='HEAD',headers={'Range':'bytes=2-5'})) as response:
            self.assertEqual(response.status,206);self.assertEqual(response.headers['Content-Length'],'4');self.assertEqual(response.read(),b'')
        for value in ('bytes=100-','bytes=1-0','bytes=0-1,3-4','bytes=-0'):
            with self.subTest(value=value),self.assertRaises(HTTPError) as error:
                urlopen(Request(self.base+'/video.mp4',headers={'Range':value}))
            self.assertEqual(error.exception.code,416);self.assertEqual(error.exception.headers['Content-Range'],'bytes */10')
    def test_private_hidden_traversal_and_listing_are_not_served(self):
        (self.root/'pipeline_output').mkdir();(self.root/'pipeline_output'/'private.mp4').write_bytes(b'private')
        (self.root/'.git').mkdir();(self.root/'.git'/'config').write_bytes(b'private')
        (self.root/'folder').mkdir()
        for path in ('/pipeline_output/private.mp4','/PIPELINE_OUTPUT/private.mp4','/pipeline_output./private.mp4','/.git/config','/%2e%2e/secret.mp4','/CON.mp4','/folder/'):
            with self.subTest(path=path),self.assertRaises(HTTPError) as error:urlopen(self.base+path)
            self.assertIn(error.exception.code,(403,404))
