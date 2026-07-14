# -*- coding: utf-8 -*-
"""Stage 1 (spec §3): load a clip, run MediaPipe Hands in video mode, extract
per-frame 21-point landmarks in BOTH coordinate spaces -- 3D world landmarks
(used for all Stage 2-5 geometry per spec §1's "항상 3D" rule) and 2D pixel
landmarks (needed later in Stage 6 to actually draw a mask on the frame).
"""
import cv2
import mediapipe as mp

from dataset_pipeline.common import LANDMARK_NAMES


def extract_landmarks(video_path, confidence=0.5):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"영상을 열 수 없음: {video_path}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    info = {"width": width, "height": height, "fps": fps, "total_frames": total, "source": video_path}

    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=confidence,
        min_tracking_confidence=confidence,
    )

    frames = []
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        entry = {"frame_idx": idx, "detected": False, "confidence": None}
        if result.multi_hand_landmarks and result.multi_hand_world_landmarks:
            image_lm = result.multi_hand_landmarks[0]
            world_lm = result.multi_hand_world_landmarks[0]
            entry["detected"] = True
            entry["landmarks_px"] = {
                LANDMARK_NAMES[i]: {"x": lm.x * width, "y": lm.y * height, "z": lm.z}
                for i, lm in enumerate(image_lm.landmark)
            }
            entry["landmarks_world"] = {
                LANDMARK_NAMES[i]: {"x": lm.x, "y": lm.y, "z": lm.z}
                for i, lm in enumerate(world_lm.landmark)
            }
            if result.multi_handedness:
                entry["confidence"] = result.multi_handedness[0].classification[0].score
                entry["handedness"] = result.multi_handedness[0].classification[0].label
        frames.append(entry)
        idx += 1

    cap.release()
    hands.close()
    return frames, info


def frame_points(frame, space="world"):
    """Return this frame's 21 landmarks as a list of (x,y,z) tuples, or None
    if undetected. space: 'world' or 'px'."""
    key = "landmarks_world" if space == "world" else "landmarks_px"
    if not frame.get("detected") or key not in frame:
        return None
    lm = frame[key]
    return [(lm[n]["x"], lm[n]["y"], lm[n]["z"]) for n in LANDMARK_NAMES]
