# 자체 작성한 3D 동작 연결 시험

**2026-11-05 MANO 후속:** 별도 CPU runtime에서 실제 MANO 표면12조건을 생성하고, 해석적 반경 교집합이 있는4개만 Stage7/변경 없는Stage6 및 H264로 검사했다. [실행/거부/한계 보고서](https://github.com/mukgore/codex/blob/work/todo-consolidation-20261103/docs/deliveries/2026-11-05_mano_cpu_pilot.md). `accept_mano_pilot.py`, `mask_feasibility.py`, `mask_mano_sweep.py`가 비공개 모델 출력의 hash binding/전-frame 구간/실제 가림을 연결한다. 운영 weight/calibration이나 사람/공격 승인으로 쓰지 않는다. 원본 모델·생성 표면/영상은 공개하지 않는다.

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
