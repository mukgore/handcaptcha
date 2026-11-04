# Notebook 원본의 비공개 연구 편입

기존 ingest의 누락 export_pool 의존성을 제거했다. 예전 level3_DIP 영상은 검사 없이 복사하지 않고 baseline_original.mp4를 현재 Stage1~7 및 candidate renderer로 다시 처리한다.

`ingest_experiment_folder(folder, 'clip01', new_private_output, w3_new=weight, config=config)` 또는 `ingest_many([(folder, 'clip01', label)], new_private_output, w3_new=weight, config=config)`를 사용한다. 영상 원본과 명시적 가림 배율, 새 비공개 출력 폴더가 필요하다. 기존 공개 pool export 계약을 변경했으므로 예전 호출자는 이 계약으로 전환해야 한다.

성공은 RESEARCH_CANDIDATE, 검사 거부는 QUARANTINED다. rights_status=UNREVIEWED, release_allowed=false다. 폴더별 완료 표지는 intake.json, 전체 완료 표지는 intake_manifest.json이며 예외로 남은 중간 폴더는 완료 결과가 아니다. 기존 출력과 운영 pool_manifest.json을 덮어쓰지 않는다. 여러 notebook의 같은 baseline 파일명은 clip ID별 하위 폴더로 구분한다.

원본 해시·label·연구 영상이 있는 출력은 Git에 올리지 않는다. 독립 PTS/권리/사람/공격 검증과 운영 승격은 별도다. Stage6 수식은 유지한다.
