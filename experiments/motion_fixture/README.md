# 자체 작성한 3D 동작 연결 시험

사용자는 가림 없는 원본 동작과 대응 자세·시간 자료가 **없음**을 확인했다. 따라서 실측 기반 P1 파일럿은 대기 상태다. 이 모듈은 직접 작성한 단순 21점 골격으로 코드 연결을 시험하며, 숨긴 관절을 영상에서 추정해 정답으로 쓰지 않는다.

`index_flex`, `middle_flex`, `alternating`의 세 가지 정해진 동작을 forward kinematics로 만든다. seed는 굽힘 진폭을 바꾸고, 정사영으로 512×420 영상을 렌더한다. 원본 영상의 decoder 시각을 다시 기록한 다음 Stage7 v2와 **수정하지 않은 Stage6**를 거쳐 연구 후보 MP4를 만든다. 동일 recipe는 같은 좌표를 만들지만 영상 인코딩 byte의 환경 간 동일성은 보장하지 않는다.

```powershell
python -m experiments.motion_fixture.generate --output pipeline_output/authored_fixture_run1 --template middle_flex --seed 7 --w3 2.5 --frames 24 --fps 12
```

새 폴더만 사용하며 기존 출력은 덮어쓰지 않는다. `w3=2.5`, 12fps, 24frame은 연결 시험 예시로, 실제 연구 조건이나 사람에게 검증된 기준이 아니다. FPS는 1~60, frame 수는 3~240으로 제한한다. 기존 NumPy/OpenCV 외에 모델·데이터·패키지를 설치하지 않는다.

출력은 `authored_source.avi`, 자체 작성 좌표/시각 `private_reference.json`, `preview.png`, recipe·코드 해시·검사 결과 `fixture_report.json`이다. 기하 gate를 통과하면 `candidates/<hash>/masked.mp4`와 artifact manifest가 추가된다. 기하 실패 시 artifact는 null이다. 중간 실행 실패로 남은 폴더는 완료 결과로 사용하지 않는다. 완료 report와 artifact manifest를 확인해야 한다. 출력 폴더는 Git에서 제외되며 좌표·영상은 커밋하지 않는다.

보고서는 항상 `RESEARCH_FIXTURE_ONLY`, `release_allowed=false`, `human_feasibility_tested=false`다. 후보 manifest도 운영 release를 허용하지 않는다. 관절 범위는 검증되지 않은 공학 파라미터이며, 단순 뼈 그림에는 표면·충돌·물체 접촉·잡기 물리가 없다. 사람이 따라 할 수 있는지, 동작이 모호한지, 공격에 강한지는 시험하지 않았다. seed나 동작 이름을 독립 source family 또는 참여자 수로 세지 않는다. Text2HOI/GRAB/MANO 재현이나 완성된 실측 P1이 아니다.

검사는 seed 재현·진폭 변화, 뼈 길이 보존·작성 범위, 잘못된 recipe, 실제 영상→가림 출력, 덮어쓰기 거부, 잘못된 mask 배율의 무출력 처리를 확인한다.
