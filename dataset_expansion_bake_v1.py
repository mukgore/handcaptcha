# -*- coding: utf-8 -*-
"""dataset_expansion_bake_v1.ipynb

가림(occlusion) CAPTCHA 데이터셋 확장 — 굽기 단계 (Colab용)

dataset_expansion_filter_v1.py 가 산출한 adopted_clips.json (최종 채택된
소수 클립 + 프레임별 마스크 파라미터)만 대상으로 실제 영상을 읽어
Stage4(역재생 길이 보정) + Stage6(원 그리기)를 적용한 최종 mp4를 만든다.

Jester 전체(14만+)가 아니라 필터링을 통과한 클립만 처리하므로 훨씬 빠르다.
레벨1/2는 만들지 않음 (명세서 결정: 레벨3만 사용).

기존 손가림및테스트_handtest1.py 의 generate_occluded_video 를
adopted_clips.json에 이미 계산되어 있는 (cx,cy,r)을 그대로 사용하도록
바꿔서 재사용한다 (반경 재계산 없음 — 필터링 단계와 100% 동일한 값 보장).
"""

#셀 1
!pip install opencv-python-headless numpy

#셀 2
import cv2
import numpy as np
import json
import os
import glob

# 필터링 단계 산출물
ADOPTED_CLIPS_JSON = 'adopted_clips.json'   # TODO: 필터링 단계 출력 경로로 교체
JESTER_ROOT = ''                            # TODO: 필터링 단계와 동일한 Jester 클립 상위 경로
OUTPUT_DIR = 'baked_level3_clips'
os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(ADOPTED_CLIPS_JSON, encoding='utf-8') as f:
    adopted_clips = json.load(f)
print(f"채택된 클립 수: {len(adopted_clips)} (이 개수만 굽는다 — Jester 전체를 굽지 않음)")

#셀 3
# ─────────────────────────────────────────────
# Stage 4 — 역재생 길이 보정 ([0..N] + [N-1..0])
# ─────────────────────────────────────────────

def load_clip_frames(clip_source):
    """클립 원본 프레임 전체를 메모리에 로드 (jpg 폴더 또는 영상 파일)."""
    frames = []
    if os.path.isdir(clip_source):
        for p in sorted(glob.glob(os.path.join(clip_source, "*.jpg"))):
            img = cv2.imread(p)
            if img is not None:
                frames.append(img)
    else:
        cap = cv2.VideoCapture(clip_source)
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        cap.release()
    return frames


def mirror_pad_frames(frames, frames_mask):
    """[0..N] + [N-1..0] 이어붙임. 마스크 파라미터도 좌표 그대로 재사용(역순).
    역재생 구간은 원본과 동일한 ndarray 객체를 그대로 참조하지만, 거울 대칭
    위치의 마스크 값이 원본과 항상 동일해서(같은 frame_idx) 중복으로 원을
    그려도 결과는 달라지지 않는다 — 별도 복사본을 만들 필요 없음."""
    if len(frames) < 2:
        return frames, frames_mask
    padded_frames = frames + frames[-2::-1]

    n = len(frames)
    mask_by_idx = {m["frame_idx"]: m["mask"] for m in frames_mask}
    padded_mask = []
    for i in range(len(padded_frames)):
        src_idx = i if i < n else (2 * n - 2 - i)
        if src_idx in mask_by_idx:
            padded_mask.append({"frame_idx": i, "mask": mask_by_idx[src_idx]})
    return padded_frames, padded_mask


print("Stage 4 (역재생 길이 보정) 로드 완료")

#셀 4
# ─────────────────────────────────────────────
# Stage 6 — 마스크 굽기 (기존 generate_occluded_video 방식, 반경은 재계산하지 않고
# 필터링 단계가 이미 계산해둔 값을 그대로 사용 — 판정과 굽기의 반경이 어긋나지 않게 함)
# ─────────────────────────────────────────────

def reencode_h264(path):
    """OpenCV 'mp4v'(MPEG-4 Part 2) 출력은 브라우저 <video>에서 디코딩되지 않아
    검은 화면이 된다 -- ffmpeg로 H.264(yuv420p, +faststart)로 재인코딩해 같은
    경로에 덮어쓴다. 프레임 수는 1:1로 유지되므로 랜드마크 정렬에 영향 없음.
    (Colab에는 ffmpeg가 기본 설치되어 있음.)"""
    import shutil, subprocess
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg is None:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            print(f"  [경고] ffmpeg 없음 -- {path}는 mp4v 그대로라 브라우저에서 재생 불가")
            return
    tmp = path + '.h264tmp.mp4'
    subprocess.run([ffmpeg, '-y', '-v', 'error', '-i', path,
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '21',
                    '-movflags', '+faststart', '-an', tmp], check=True)
    os.replace(tmp, path)


def bake_occluded_video(frames, frames_mask, fps, output_path):
    if not frames:
        return
    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    mask_by_idx = {m["frame_idx"]: m["mask"] for m in frames_mask}
    last_c, last_r = None, None
    for i, frame in enumerate(frames):
        m = mask_by_idx.get(i)
        if m is not None:
            last_c = (m["center"]["x"], m["center"]["y"])
            last_r = m["radius"]
        if last_c and last_r:
            cv2.circle(frame, last_c, last_r, (0, 0, 0), -1)
        out.write(frame)
    out.release()
    reencode_h264(output_path)


print("Stage 6 (마스크 굽기) 로드 완료")

#셀 5
# ─────────────────────────────────────────────
# 전체 굽기 실행 — 채택된 클립만 대상
# ─────────────────────────────────────────────

DEFAULT_FPS = 12.0  # info에 fps가 없을 때만 쓰는 폴백값

baked_count = 0
for clip_id, rec in adopted_clips.items():
    clip_source = os.path.join(JESTER_ROOT, clip_id)
    if not os.path.exists(clip_source):
        print(f"  [스킵] 원본을 찾을 수 없음: {clip_source}")
        continue

    frames = load_clip_frames(clip_source)
    if not frames:
        print(f"  [스킵] 프레임 로드 실패: {clip_id}")
        continue

    padded_frames, padded_mask = mirror_pad_frames(frames, rec["frames_mask"])

    # 필터링 단계(rec["info"]["fps"])가 실제 소스 fps를 이미 정확히 기록해뒀으므로 그대로 사용
    fps = rec.get("info", {}).get("fps") or DEFAULT_FPS
    out_path = os.path.join(OUTPUT_DIR, f"{clip_id}_level3_DIP.mp4")
    bake_occluded_video(padded_frames, padded_mask, fps, out_path)
    baked_count += 1
    if baked_count % 20 == 0:
        print(f"  {baked_count}/{len(adopted_clips)} 완료")

print(f"\n완료: {baked_count}개 클립을 {OUTPUT_DIR}/ 에 저장 (레벨3, 역재생 길이 보정 포함)")
print("주의: 가려지지 않은 원본 클립은 여기 출력 폴더에 포함되지 않음 — 배포 시에도 이 폴더 산출물만 올릴 것.")

#셀 6
# ─────────────────────────────────────────────
# (선택) 결과 압축 다운로드
# ─────────────────────────────────────────────
# from google.colab import files
# import zipfile
# zip_name = OUTPUT_DIR + '.zip'
# with zipfile.ZipFile(zip_name, 'w') as zf:
#     for root, _, fnames in os.walk(OUTPUT_DIR):
#         for fname in fnames:
#             zf.write(os.path.join(root, fname))
# files.download(zip_name)
