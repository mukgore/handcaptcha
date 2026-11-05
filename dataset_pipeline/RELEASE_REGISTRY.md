# 비공개 검토 상태 등록부

`ReleaseRegistry(database, private_root)`는 SQLite transaction과 expected_revision으로 동시 승격을 제어한다. 모든 자료와 DB는 저장소 웹 루트 밖에 둔다.

`register(relative_media, source_hashes, purpose='RESEARCH_ONLY')`는 실제 출력 bytes를 해시해 INGESTED로 등록한다. `transition(id, expected_revision, next_state, evidence)`의 순서는 INGESTED → RIGHTS_CLEARED → QUALITY_CHECKED → MASKED → ARTIFACT_VERIFIED → HUMAN_REVIEWED → SECURITY_EVALUATED → RELEASED다. 건너뛰기·오래된 revision·다른 bytes의 증거를 거부한다. RESEARCH_ONLY는 RELEASED가 될 수 없다. SERVICE_CANDIDATE 등록도 권리나 출하 승인이 아니다.

각 review는 해당 state의 kind, status=PASS, artifact_sha256, reviewer_id, protocol_version, timezone 있는 reviewed_at, private root 안의 report_file 및 실제 보고서 bytes와 일치하는 report_sha256을 요구한다. state별 요구는 release_registry.validate_review에 명시돼 있다. 권리는 모든 source hash와 서비스/파생 사용 승인·권리 대장·유효기간을 확인하고, 최종 출력은 전체 frame/PTS/track/rendition 검사와 실패/불명 frame=0을 요구한다. 사람 검수·사전 기준을 둔 공격 검토·최종 출하 승인은 별도 review다.

기하 gate/manifest 값을 근거로 사람/보안 승인 증거를 자동 생성하지 않는다. 등록부는 보고서의 실제 주장이나 검토자 신원을 독립적으로 증명하지 않는다. 신뢰하는 검토자가 실제 결과에 근거해 기록해야 한다. 현재 실제 승인 자료를 등록하거나 운영 출하한 결과는 없다.

QUARANTINED/RETIRED는 사유를 남기는 종료 상태다. 이 버전에서 재승격은 허용하지 않는다. serving 경로는 임의 JSON의 release_allowed 대신 eligible_for_serving(id)를 호출해야 한다. 이 함수는 RELEASED·서비스 목적·현재 권리 유효성·현재 파일 해시를 확인한다. 철회 시 QUARANTINED/RETIRED 처리하고 앞으로의 발급을 막아야 한다.

기존 prod/GitHub Pages가 자동으로 이 등록부를 참조하는 것은 아니다. 비공개 실제 송출 서버 연결·검토자 인증/권한·외부 CDN의 이미 전달된 사본·요청 중 권리 철회 정책은 별도다. 합성 contract 검사가 실제 보안 평가를 대신하지 않는다.

2026-11-05: [비공개 송출 연결 기반](PRIVATE_DELIVERY.md)에 실제 registry 조회·세션/조직/만료·Range·철회·한 번의 operation 소비를 추가했다. 운영 gateway/검토자 인증·prod 연결/배포는 아직 별도이며 위 기존 경계를 유지한다.

## 비공개 경로

candidate·batch·legacy ingest/bake·motion fixture의 출력은 저장소 웹 루트 내부 또는 그 상위 디렉터리를 지정하면 거부한다. run CLI 기본 출력은 `../private_artifacts/pipeline_output`이다. Git ignore는 HTTP 접근 제어가 아니다. 원본/추정 좌표·후보·등록부를 정적 웹 폴더에 두지 않는다.
