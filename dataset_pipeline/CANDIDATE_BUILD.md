# 프레임 대응과 연구 후보 영상 생성

Stage6 수식/파일은 유지한다. `timeline.py`와 `candidate.py`가 필터링·역재생된 프레임을 명시적으로 재배열한 뒤, 이와 같은 순서의 좌표를 기존 Stage6에 전달한다.

## 실행

```powershell
python -m dataset_pipeline.cli run "private_clips/*.mp4" --w3 1.95 --output pipeline_output/run_001
```

`1.95`는 예시 값이며 검증된 공통 기준이 아니다. 연구자가 고정한 값을 사용하거나 개발 자료만으로 추정한다. CLI 기본 실행은 Stage7 통과 후보의 실제 MP4를 만든다. 기존 보고서만 필요하면 `--report-only`를 사용한다. Python API `run_batch`는 호환성을 위해 `render_candidates=False`가 기본이다.

## 대응과 검증

- Stage1에서 decode 후 `source_pts_ms`를 기록한다. 타임스탬프가 없거나 원본 인덱스에 따라 증가하지 않으면 렌더를 거부한다. 배열 번호/FPS로 시간 정보를 몰래 채우지 않는다.
- 출력마다 원본 frame index·decoder 시간·reference index와 새 출력 frame index·시간을 기록한다. 같은 원본 frame을 역재생에 재사용할 때 좌표/시간이 달라지면 거부한다.
- 필터링/역재생 이후 출력은 **명시적 CFR 재타이밍**이다. VFR 원본의 원래 duration을 그대로 보존하는 모드가 아니다. 예를 들어 source 0/2/0을 선택하면 source 시간 0/200/0ms가 output 0/100/200ms가 될 수 있다.
- 원본을 다시 decode해 크기·FPS·개수·선택한 frame의 decoder 시간을 추출 기록과 대조한다. 선택 frame의 디코딩 캐시는 기본 256MiB, 출력은 기본 20,000 frame 이내로 제한한다.
- 임시 비공개 FFV1 영상에 선택/역재생 순서대로 프레임을 넣는다. 같은 순서로 좌표를 재배치해 변경 없는 Stage6을 호출한다. 무가림 중간 파일은 임시 디렉터리에서 정리한다.
- Stage6의 출력 개수/크기/가림 내부 검사를 거친 최종 MP4를 다시 읽어 출력 CFR 시간열도 대조한다. FFV1·인코더·시간 검증이 실패하면 다른 경로로 조용히 대체하지 않는다.
- 파일명은 최종 MP4 해시를 사용하며 기존 후보는 덮어쓰지 않는다. `artifact.json`을 완료 표식으로 마지막에 게시한다. 소비자는 이 파일과 MP4 해시를 확인해야 한다.

결과는 `artifacts/<hash>/masked.mp4`와 `artifact.json`이다. manifest에 출력 해시·대응표·Stage7 정책·가림 수식 버전·설정·frame count를 남긴다. batch는 생성 실패를 `quarantined_render`로 기록하고 artifact 목록에서 제외한다. 같은 basename의 입력은 혼동을 막기 위해 거부한다. CLI는 렌더 오류가 있으면 종료 코드 1, 입력이 없으면 2를 반환한다.

## 판정 범위

이 산출물은 `RESEARCH_CANDIDATE`, `release_allowed=false`, `rights_status=UNREVIEWED`다. 기하 통과만으로 운영 승인 풀을 만들지 않는다. 공개 정적 폴더에 출력 경로를 두지 않는다. batch의 `manifest_scope`는 `geometry_only` 또는 `research_artifacts`로 구분한다.

OpenCV의 [video I/O 속성 문서](https://docs.opencv.org/4.10.0/d4/d15/group__videoio__flags__base.html)는 POS_MSEC를 영상 위치(ms)로 정의하며 backend 계층의 영향을 설명한다. 이 구현은 그 decoder 시간열을 왕복 대조하지만 독립 container PTS·모든 track·VFR 의미 보존을 입증하지 않는다. 원본/파생본 권리, 해부학적 가림, 사람 수행·강한 공격, poster/다른 rendition, 실제 운영 승격은 별도 후속 검사다.
