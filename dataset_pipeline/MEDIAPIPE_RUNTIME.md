# Windows resource 경로 처리

Stage1 extract_landmarks의 resource_mode 기본값은 auto다. Windows에서 설치 MediaPipe 경로에 ASCII 밖 문자가 있으면 별도 Python 프로세스로 추출한다. 이미 설치된 graph·손/손바닥 full TFLite·handedness label을 저장소 밖 private_artifacts/mediapipe_worker에 해시별로 복사한다. 설치 파일을 수정하거나 모델을 다운로드하지 않는다. 필요한 설치 asset이 없으면 실패한다.

worker 안에서만 legacy SolutionBase의 resource 경로를 ASCII 상대 경로로 조정한다. 부모 프로세스의 global resource 값이나 현재 디렉터리는 바꾸지 않는다. 동시 호출도 서로 다른 request 폴더를 쓰고 asset cache의 실제 bytes를 대조한다. native 모드로 기존 직접 실행을 선택할 수도 있다.

기본 worker 상한은300초이며 extract_landmarks의 worker_timeout_seconds로 명시할 수 있다. 실패/timeout의 request·stderr는 비공개 failures에 보존한다. batch는 해당 clip을 quarantined_extraction으로 분모에 남기고 후보에서 제외한다. CLI는 추출/렌더 격리 실패가 있으면0이 아닌 종료 코드를 반환한다.

batch 출력은 새 폴더 또는 비어 있는 비공개 폴더만 허용한다. .pipeline_owner를 배타 생성하고 보고서를 x 모드로 써서 예전 결과·동시 실행 결과를 덮어쓰지 않는다. 실패 후 부분 폴더는 완료 결과로 취급하지 말고 진단용으로 보존한다.

2026-11-04 실제 기존 영상113frame을 일반 auto API로 추출해113검출/단조 decoder 시간열을 확인했다. legacy 편입 진단은 명시적 공학값 w3=2.5와 기존 config로 실행했고 Stage3에서 거부돼 QUARANTINED였다. 채택되도록 기준을 변경하지 않았다. 이 결과는 사람/3D 정답/권리 검증이 아니다. MediaPipe0.10.9와 protobuf5.29.6의 설치 metadata 충돌은 남아 있으며 깨끗한 재현환경이 확보됐다는 뜻은 아니다.
