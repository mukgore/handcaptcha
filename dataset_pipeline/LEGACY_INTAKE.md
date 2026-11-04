# Notebook 원본의 비공개 연구 편입

기존 ingest의 누락 export_pool 의존성을 제거했다. 예전 level3_DIP 영상은 검사 없이 복사하지 않고 baseline_original.mp4를 현재 Stage1~7 및 candidate renderer로 다시 처리한다.

`ingest_experiment_folder(folder, 'clip01', new_private_output, w3_new=weight, config=config)` 또는 `ingest_many([(folder, 'clip01', label)], new_private_output, w3_new=weight, config=config)`를 사용한다. 영상 원본과 명시적 가림 배율, 새 비공개 출력 폴더가 필요하다. 기존 공개 pool export 계약을 변경했으므로 예전 호출자는 이 계약으로 전환해야 한다.

성공은 RESEARCH_CANDIDATE, 검사 거부는 QUARANTINED다. rights_status=UNREVIEWED, release_allowed=false다. 폴더별 완료 표지는 intake.json, 전체 완료 표지는 intake_manifest.json이며 예외로 남은 중간 폴더는 완료 결과가 아니다. 기존 출력과 운영 pool_manifest.json을 덮어쓰지 않는다. 여러 notebook의 같은 baseline 파일명은 clip ID별 하위 폴더로 구분한다.

원본 해시·label·연구 영상이 있는 출력은 Git에 올리지 않는다. 독립 PTS/권리/사람/공격 검증과 운영 승격은 별도다. Stage6 수식은 유지한다.

## 기존 별도 bake 경로

root의 dataset_expansion_bake_v1.py도 같은 연구 파이프라인을 사용하도록 전환했다. import 시 설치·파일 읽기·렌더를 실행하지 않는다. `python dataset_expansion_bake_v1.py --adopted adopted_clips.json --source-root PRIVATE_ROOT --output ../private_artifacts/new_bake --w3 실제값`으로 실행한다.

mapping의 각 key는 원본 video 상대 경로이며 info.fps를 명시해야 한다. 실제 영상 FPS와 대조하고 기존 circle만 재사용하지 않는다. 원본을 다시 추출·검사해 현재 Stage6 수식으로 굽는다. 결과는 연구 후보이며 운영 배포 승인이 아니다. 이전 출력의 비검증 H264 재인코딩/자동 배포 안내도 제거했다. 브라우저용 rendition은 별도 검사·승격 대상이다.

예전 JPEG 폴더만 있는 입력은 프레임별 시각 근거를 제공하지 않으므로 거부한다. 12fps로 추정해 대신 넣지 않는다. 파일/프레임 시각과 대응 자세가 확보된 후 지원을 확장해야 한다. 기존 notebook 셀을 그대로 실행하던 사용자는 위 명령과 새 입력 계약으로 전환해야 한다.
