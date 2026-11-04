from pathlib import Path
import shutil
import tempfile
import unittest

import cv2
import numpy as np

from dataset_pipeline.rendition import validate_raster_pair


class RenditionRasterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source.mp4';self.output=self.root/'out.mp4'
        self.masks=[((16.,16.),8.)]*3
        self.write(self.source,'masked')

    def write(self,path,mode):
        writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),12.,(32,32))
        self.assertTrue(writer.isOpened())
        try:
            for _ in range(3):
                image=np.full((32,32,3),0 if mode=='black' else 180,np.uint8)
                if mode=='masked':cv2.circle(image,(16,16),8,(0,0,0),-1)
                writer.write(image)
        finally:writer.release()

    def test_identical_masked_pixels_pass_codec_comparison(self):
        shutil.copyfile(self.source,self.output)
        report=validate_raster_pair(self.source,self.output,self.masks,32,32,outside_mae_limit=2.)
        self.assertEqual(report['decoded_frames'],3);self.assertEqual(report['max_frame_outside_mae'],0.)

    def test_unmasked_output_cannot_pass(self):
        self.write(self.output,'unmasked')
        with self.assertRaises(ValueError):validate_raster_pair(self.source,self.output,self.masks,32,32,outside_mae_limit=2.)

    def test_all_black_output_cannot_hide_loss_of_visible_cues(self):
        self.write(self.output,'black')
        with self.assertRaises(ValueError):validate_raster_pair(self.source,self.output,self.masks,32,32,outside_mae_limit=2.)

    def test_wrong_expected_count_cannot_pass(self):
        shutil.copyfile(self.source,self.output)
        with self.assertRaises(ValueError):validate_raster_pair(self.source,self.output,self.masks[:2],32,32,outside_mae_limit=2.)
