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
import cv2

from dataset_pipeline.common import P0, P9
from dataset_pipeline.geometry import dist, midpoint
from dataset_pipeline.stage1_extract import frame_points


def project_occlusion_circle(image_lm_px, w3_new):
    """image_lm_px: this frame's 2D pixel-space landmarks (list of (x,y,z)).
    w3_new: unitless PIP/DIP ratio pre-computed in 3D world space by Stage 5.
    Always projects using this same frame's 2D image landmarks -- never a 3D
    world -> 2D pixel reprojection via a camera model -- since MediaPipe
    returns both landmark sets from the same detection call."""
    w, mcp9 = image_lm_px[P0], image_lm_px[P9]
    diameter = dist(w, mcp9) * w3_new
    center = midpoint(w, mcp9)
    # Keep center in the same (x,y,z) shape as the landmark points so
    # downstream dist() calls (Stage 7) don't hit a shape mismatch; only
    # x/y are used when actually drawing the mask (cv2.circle is 2D).
    return tuple(float(c) for c in center), diameter / 2.0


def generate_occluded_video(video_path, frames, info, w3_new, output_path):
    """cv2 read/draw/write loop ported from handtest1.py's
    generate_occluded_video(); circle math replaced per
    project_occlusion_circle() above."""
    cap = cv2.VideoCapture(video_path)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, info["fps"], (info["width"], info["height"]))

    last_center, last_radius = None, None
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx < len(frames):
            pts = frame_points(frames[idx], "px")
            if pts is not None:
                last_center, last_radius = project_occlusion_circle(pts, w3_new)
        if last_center and last_radius:
            cv2.circle(frame, (int(last_center[0]), int(last_center[1])), int(last_radius), (0, 0, 0), -1)
        out.write(frame)
        idx += 1

    cap.release()
    out.release()
