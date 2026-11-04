# 독립 컨테이너 검사와 H.264 파생본

container_inspection.inspect_container는 OpenCV 밖의 ffprobe로 전체 stream과 제한된 packet metadata를 읽는다. 단일 video track, 크기/개수, 명시적 CFR PTS, 증가하는 DTS, duration과 허용 metadata를 검사한다. 추가 audio/subtitle/attachment/poster·불명 timing/side data는 거부한다. 하나의 primary 파일 검사이며 다른 poster/rendition 검수나 가림의 해부학적 타당성·권리/공격 승인을 뜻하지 않는다.

API는 로컬 MP4, 예상 frame_count/width/height/fps, 새 비공개 출력 폴더, 명시적 ffprobe 실행 파일을 받는다. JSON/진단·파일 해시는 비공개 출력에만 남는다. ffprobe가 없으면 검사 불가로 실패한다. [공식 ffprobe 문서](https://www.ffmpeg.org/ffprobe.html)의 show_packets/show_streams/show_format을 사용한다.

rendition.build_h264_rendition은 연구 candidate manifest의 bytes·timeline·config를 대조하고 가림 완료 영상만 libx264로 재인코딩한다. CRF18/yuv420p/B-frame0/threads1/+faststart를 기록한다. source/파생 container를 각각 검사하고, 전 frame의 mask 내부와 보이는 영역을 source와 대조한다. outside_mae_limit은 호출자가 사전에 정하는 공학 codec QA 값이다. hash별 새 경로에 video.mp4와 완료 표지 rendition.json을 게시하고 기존 결과는 덮어쓰지 않는다. state=RESEARCH_RENDITION, release_allowed=false다.

2026-11-04 자체 작성 middle_flex fixture24frame/512×420/12fps를 실행했다. primary와 H.264 모두 단일 track/24packet/2초의 PTS가 일치했다. 모든 frame의 보수적 mask 내부(허용30/255, 경계2pixel)를 통과했고 outside MAE 최대0.13952는 미리 정한2.0 이내였다. 이 값은 합성 codec QA이며 실제 보안 기준이 아니다.

사용자가 승인한 FFmpeg9.0.2 Windows 빌드를 FFmpeg 공식 다운로드 페이지가 안내하는 Gyan provider에서 받았다. 공개 archive SHA256과 대조한 뒤 프로젝트 private_tools에 ffprobe/ffmpeg를 준비했고 Python package·시스템 PATH는 바꾸지 않았다. provenance/실행 파일 해시/notice는 비공개 tool_manifest와 함께 보관한다. 실행 파일은 Git에 커밋하지 않는다. [FFmpeg 다운로드 안내](https://ffmpeg.org/download.html), [provider](https://www.gyan.dev/ffmpeg/builds/).

브라우저 시험은 기존 간이 HTTP 서버에서 seekable 범위0 때문에 중간 seek가0으로 돌아왔다. experiments.preview_server의 byte Range 응답으로 바꾼 뒤 격리 Chrome에서512×420/2초/오류없음/seek1초 및 seekable0~2초를 확인했다. 카메라를 쓰지 않은 자체 합성 영상 재생 시험이다.

권장 로컬 보기: 저장소 루트에서 `python -m experiments.preview_server --port 8767`. 이 서버는 public research asset만 제공하며 hidden/private 경로·directory listing·범위 밖 경로를 거부한다. Range/HEAD/416·정확한 byte 응답을 검사했다. registry-backed 운영 송출·세션/tenant·만료/cache 정책이 구현됐다는 뜻은 아니다.
