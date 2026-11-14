# 자체 작성한 3D 동작 연결 시험

**2026-11-14 표면/깊이 단서:** `surface_passes.py`가 capsule/구의 실제 앞뒤 표면을 계산하고 `depth_cue_audit.py`가 물체 표시/제거 × 단색/고정 조명의 네 조건을 비교한다. 12개 깊이 제어·48개 모드 사례 중 접촉 실패 16개는 격리했고, 32개 H.264·768프레임을 검사했다. pipeline 118개 통과. 두 뼈 proxy의 가림 밖 표면도 검사하되 전체 해부학을 보장하지 않는다. palm mesh·그림자·반사·물리/인체 검증은 없다.

```powershell
python -m experiments.motion_fixture.depth_cue_audit --output ../private_artifacts/NEW_SURFACE_RUN --ffmpeg ../private_tools/ffmpeg-9.0.2/ffmpeg.exe --ffprobe ../private_tools/ffmpeg-9.0.2/ffprobe.exe
```

실제 실험은 codex의 `validation_v03.execution_record`로 위 명령을 감싸 새 비공개 기록/결과 폴더를 사용한다. 실행 ID `G04-G05-SURFACE-CUES-20261114`는 코드 `43e809a`로 수행했다. [결과/해석/실행 기록](https://github.com/mukgore/codex/blob/work/todo-consolidation-20261103/docs/deliveries/2026-11-14_surface_depth_cues.md). 물체 없이도 조명 단서가 생기며, 다른 모형은 최종 가림 영상이 같은 유효 깊이 대안을 갖는다. 픽셀 차이를 사람/AI 성능이나 단일 정답의 증거로 쓰지 않는다. raw/depth/owner/좌표는 비공개이고 release_allowed=false다.

**2026-11-13 접촉 모형:** `grasp_contacts.py`와 `grasp_counterexamples.py`에 두 capsule–sphere 접촉 proxy와 깊이 반전 대조를 추가했다. 12개 대조 중 4개는 격리했고 8개·H.264 192프레임을 검증했다. 전체 pipeline 111개 통과. 정사영 선 그림이며 depth buffer/표면 가림/그림자·안정적 grasp·해부학·중력·마찰은 검증하지 않았다. 실제 물체 깊이를 아는 조건과 영상만 아는 조건을 구분한다. 같은 픽셀의 복수 3D 설명을 단일 정답이나 공격 저항성으로 해석하지 않는다.

```powershell
python -m experiments.motion_fixture.grasp_counterexamples --output ../private_artifacts/NEW_CONTACT_RUN --ffmpeg ../private_tools/ffmpeg-9.0.2/ffmpeg.exe --ffprobe ../private_tools/ffmpeg-9.0.2/ffprobe.exe
```

새 폴더에서만 실행한다. 출력·좌표는 비공개이며 release_allowed=false다. [결과·분모·한계·남은 입력](https://github.com/mukgore/codex/blob/work/todo-consolidation-20261103/docs/deliveries/2026-11-13_grasp_contact_counterexamples.md). 실행 코드 기준 `7f86a97`; 뒤의 문서는 실행 당시 snapshot을 대체하지 않는다. 원래 촬영·사람 비교 단계의 우선순위를 유지한다.

**2026-11-13 MANO 검토:** 기존 2026-11-05 로컬 변경을 현재 작업 브랜치에 통합하고, 모델 유래로 기록된 기존 12개 산출물을 다시 검사했다. 모든 프레임의 반경 교집합이 있는 4개만 Stage7/변경 없는 Stage6와 H.264 96프레임을 통과했다. [최신 검사/거부/한계 보고서](https://github.com/mukgore/codex/blob/work/todo-consolidation-20261103/docs/deliveries/2026-11-13_mano_artifact_review.md). 새 모델 추론이나 동작 생성은 실행하지 않았다. 원본 모델·좌표·표면·영상은 공개하지 않는다.

`load_bound_pilot`/`verify_pilot`은 완료된 모든 원본의 영상·참조·표면·보고서 연결을 확인한다. 기하에서 거부될 자료도 검사를 생략하지 않으며, 검사 도중 파일이 바뀌면 완료 보고서를 쓰지 않는다. `mask_feasibility`는 모든 프레임의 가림/단서 조건 교집합을 계산하고 유효한 유한 구간에만 중간값을 제안한다. 계산 범위를 넘는 유한 좌표도 거부한다. 제안은 source별 생성 제약이며 실제 gate/래스터 재검사가 필요하다. gate를 약화시키거나 데이터셋의 운영 weight를 보정한 것이 아니다.

[자체 작성 합성 H.264 예시](previews/authored_middle_flex_h264.mp4)를 볼 수 있다. 24frame/2초이며 실제 사람 촬영이나 보안 challenge가 아니다. 컨테이너·가림/visible raster·Chrome 재생/seek 검사를 했고 [검사 범위](../../dataset_pipeline/CONTAINER_RENDITION.md)를 기록했다.

사용자는 별도로 제공할 원본 동작/대응 자료가 **없음**을 확인했다. 이후 기존 저장소 ZIP에서 관찰 영상1개와 추정 좌표를 확인했지만 정밀 3D 정답이나 독립 평가 자료는 아니다. 이 모듈은 직접 작성한 단순21점 골격으로 코드 연결을 시험하며, 숨긴 관절의 추정값을 실제 정답으로 쓰지 않는다. 자체 생성 코드는 촬영 자료 없이 진행할 수 있고, 실측 비교·물체 접촉·사람 수행 가능성 검증은 계속 남아 있다.

`index_flex`, `middle_flex`, `alternating`의 세 가지 정해진 동작을 forward kinematics로 만든다. seed는 굽힘 진폭을 바꾸고, 정사영으로 512×420 영상을 렌더한다. 원본 영상의 decoder 시각을 다시 기록한 다음 Stage7 v2와 **수정하지 않은 Stage6**를 거쳐 연구 후보 MP4를 만든다. 동일 recipe는 같은 좌표를 만들지만 영상 인코딩 byte의 환경 간 동일성은 보장하지 않는다.

```powershell
python -m experiments.motion_fixture.generate --output ../private_artifacts/authored_fixture_run1 --template middle_flex --seed 7 --w3 2.5 --frames 24 --fps 12
```

새 폴더만 사용하며 기존 출력은 덮어쓰지 않는다. `w3=2.5`, 12fps, 24frame은 연결 시험 예시로, 실제 연구 조건이나 사람에게 검증된 기준이 아니다. FPS는 1~60, frame 수는 3~240으로 제한한다. 기존 NumPy/OpenCV 외에 모델·데이터·패키지를 설치하지 않는다.

출력은 `authored_source.avi`, 자체 작성 좌표/시각 `private_reference.json`, `preview.png`, recipe·코드 해시·검사 결과 `fixture_report.json`이다. 기하 gate를 통과하면 `candidates/<hash>/masked.mp4`와 artifact manifest가 추가된다. 기하 실패 시 artifact는 null이다. 중간 실행 실패로 남은 폴더는 완료 결과로 사용하지 않는다. 완료 report와 artifact manifest를 확인해야 한다. 출력 폴더는 Git에서 제외되며 좌표·영상은 커밋하지 않는다.

보고서는 항상 `RESEARCH_FIXTURE_ONLY`, `release_allowed=false`, `human_feasibility_tested=false`다. 후보 manifest도 운영 release를 허용하지 않는다. 관절 범위는 검증되지 않은 공학 파라미터이며, 단순 뼈 그림에는 표면·충돌·물체 접촉·잡기 물리가 없다. 사람이 따라 할 수 있는지, 동작이 모호한지, 공격에 강한지는 시험하지 않았다. seed나 동작 이름을 독립 source family 또는 참여자 수로 세지 않는다. Text2HOI/GRAB/MANO 재현이나 완성된 실측 P1이 아니다.

검사는 seed 재현·진폭 변화, 뼈 길이 보존·작성 범위, 잘못된 recipe, 실제 영상→가림 출력, 덮어쓰기 거부, 잘못된 mask 배율의 무출력 처리를 확인한다.

## 물체 접촉 fixture 추가 (2026-11-05)

`--template middle_touch_sphere`는 기존 middle_flex에 정적 구형 물체를 두고 중지 끝이 접근·접촉·후퇴하도록 배치한다. 같은 원본/가림 출력 경로를 사용한다. 손가락/손목 연결의 20개 선분을 반지름0.025 capsule로 간주하고 구 반지름0.10과 모든 프레임의 최소 거리를 검사한다. 접촉 허용0.003과 길이 단위는 미검증 공학값이다. 고정 bone 길이·전체 frame 순서·비관통·시작/끝 이격·중간 접촉을 모두 요구하며 실패하면 후보 출력하지 않는다.

fixture_report.json의 object_contact_model에 분모/접촉 frame/관통 frame/최소 간격이 기록된다. 물체는 정사영 wireframe circle로 표시하며 실제 depth occlusion을 표현하지 않는다. palm mesh/손 자체 충돌/역학/실제 사람 타당성/정밀3D 정답을 검증한 결과가 아니다. 기존 skeleton/seed를 독립 family로 늘려 세지 않으며 release_allowed=false를 유지한다.
