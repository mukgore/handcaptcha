# -*- coding: utf-8 -*-
"""Stage 6 (spec §3/§0): apply the occlusion circle using the Stage 5
re-estimated weight.

Note on §9's asset-reuse mapping: §9 says to reuse handtest1.py's
occlusion_params() "코드 그대로", but that function centers the circle on the
average of all 5 MCP landmarks -- whereas §0/Stage 6 explicitly define
center=midpoint(P0,P9), diameter=dist(P0,P9)*w3_new. Since w3_new is
calibrated in Stage 5 specifically against dist(P0,P9), plugging it into the
5-point-average formula would use a different, inconsistent baseline
distance. We follow the explicit Stage 6 formula here and only reuse
generate_occluded_video()'s cv2 I/O loop from handtest1.py, not its math.
"""
import math
import os
import tempfile

import cv2
import numpy as np

from dataset_pipeline.common import P0, P9
from dataset_pipeline.stage1_extract import frame_points


def project_occlusion_circle(image_lm_px, w3_new):
    """image_lm_px: this frame's 2D pixel-space landmarks (list of (x,y,z)).
    w3_new: unitless PIP/DIP ratio pre-computed in 3D world space by Stage 5.
    Always projects using this same frame's 2D image landmarks -- never a 3D
    world -> 2D pixel reprojection via a camera model -- since MediaPipe
    returns both landmark sets from the same detection call."""
    if not math.isfinite(w3_new) or w3_new <= 0:
        raise ValueError("w3_new must be finite and positive")
    w, mcp9 = image_lm_px[P0][:2], image_lm_px[P9][:2]
    if not all(math.isfinite(v) for v in (*w, *mcp9)):
        raise ValueError("Mask landmarks must be finite")
    diameter = math.dist(w, mcp9) * w3_new
    if not math.isfinite(diameter) or diameter <= 0:
        raise ValueError("Occlusion circle is degenerate")
    center = tuple((float(a) + float(b)) / 2 for a, b in zip(w, mcp9))
    return center, diameter / 2.0


def generate_occluded_video(video_path, frames, info, w3_new, output_path):
    """Diagnostic renderer for unfiltered, un-reversed one-to-one source frames.

    Fail closed for missing masks or frame index/count mismatches. A successful
    return checks count, dimensions and an eroded mask interior after encoding.
    It does not prove anatomical coverage, rights or human/security suitability.
    """
    # This renderer has no source/output timeline remapping. Refuse filtered or
    # reversed arrays rather than applying a mask to a different source frame.
    if os.path.abspath(video_path) == os.path.abspath(output_path):
        raise ValueError("Output must differ from the original video")
    if os.path.exists(output_path):
        raise FileExistsError("Refusing to overwrite an existing masked artifact")
    if not frames or not math.isfinite(info["fps"]) or info["fps"] <= 0:
        raise ValueError("Frames and a positive finite FPS are required")
    if info["width"] <= 0 or info["height"] <= 0:
        raise ValueError("Invalid video dimensions")
    masks = []
    for idx, record in enumerate(frames):
        if record.get("frame_idx") != idx:
            raise ValueError("Frames must match consecutive source frame indices")
        pts = frame_points(record, "px")
        if pts is None:
            raise ValueError(f"No mask landmarks at frame {idx}")
        center, radius = project_occlusion_circle(pts, w3_new)
        if not (0 <= center[0] < info["width"] and 0 <= center[1] < info["height"]):
            raise ValueError(f"Mask center outside video at frame {idx}")
        if int(radius) < 1:
            raise ValueError(f"Mask radius too small at frame {idx}")
        masks.append((center, radius))

    output_dir = os.path.dirname(os.path.abspath(output_path))
    fd, tmp_path = tempfile.mkstemp(prefix=".masked-", suffix=".mp4", dir=output_dir)
    os.close(fd)
    cap = out = None
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("Could not open source video")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(tmp_path, fourcc, info["fps"], (info["width"], info["height"]))
        if not out.isOpened():
            raise ValueError("Could not open masked video writer")
        count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if count >= len(masks):
                raise ValueError("Source has more frames than masks")
            if frame.shape[:2] != (info["height"], info["width"]):
                raise ValueError(f"Source dimensions changed at frame {count}")
            center, radius = masks[count]
            cv2.circle(frame, (int(center[0]), int(center[1])), int(radius), (0, 0, 0), -1)
            out.write(frame)
            count += 1
        if count != len(masks):
            raise ValueError("Source has fewer frames than masks")
        out.release()
        out = None
        # Container/encoder failures can produce a missing or undecodable file.
        check = cv2.VideoCapture(tmp_path)
        try:
            if not check.isOpened():
                raise ValueError("Masked video cannot be decoded")
            decoded = 0
            while True:
                ok, decoded_frame = check.read()
                if not ok:
                    break
                if decoded >= count or decoded_frame.shape[:2] != (info['height'], info['width']):
                    raise ValueError('Masked video frame count or dimensions changed')
                center, radius = masks[decoded]
                # Ignore the codec-sensitive boundary, inspect every interior pixel.
                # Tolerance 30/255 is an engineering diagnostic, not a security target.
                cx, cy = int(center[0]), int(center[1])
                inner = max(0, int(radius) - 2)
                y0, y1 = max(0, cy-inner), min(info['height'], cy+inner+1)
                x0, x1 = max(0, cx-inner), min(info['width'], cx+inner+1)
                yy, xx = np.ogrid[y0:y1, x0:x1]
                disk = (xx-cx)**2 + (yy-cy)**2 <= inner**2
                if not disk.any() or (decoded_frame[y0:y1, x0:x1][disk] > 30).any():
                    raise ValueError(f'Masked video interior check failed at frame {decoded}')
                decoded += 1
            if decoded != count:
                raise ValueError("Masked video frame count changed during encoding")
        finally:
            check.release()
        # Atomic no-clobber publication: a competing writer must not be replaced.
        os.link(tmp_path, output_path)
        os.unlink(tmp_path)
    finally:
        if cap is not None:
            cap.release()
        if out is not None:
            out.release()
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
