# 비공개 송출 연결 기반

`PrivateDelivery(registry, separate_private_database)`는 실제 등록부의 `eligible_for_serving`을 발급·읽기·소비 시 확인한다. 기본적으로 승인 자산이 없으므로 송출할 수 없다. 실제 검토 증거를 생성하거나 연구용 자산을 운영 승인하지 않는다.

신뢰하는 gateway가 `provision_session(tenant, subject, ttl_seconds=...)`을 호출한다. 최대3600초이며 무작위 세션 bearer의 SHA256만 저장한다. 브라우저가 tenant를 주장하는 공개 발급 endpoint는 없다. `issue(session, artifact, action, operation=..., ttl_seconds=...)`는 최대600초/세션 만료 이하의 grant를 만들고 조직·세션·자산·행위·개별 operation에 묶는다.

`media(grant, session)`는 매 요청 등록부/권리/현재 bytes를 재검사한다. 최대128MiB 파일을 메모리에 읽고 **보낼 동일 bytes**의 SHA256을 확인한 후 grant를 다시 검사한다. 파일을 해시한 뒤 다시 열어 교체된 다른 bytes를 보내지 않는다. 이미 전달된 bytes의 회수나 응답 중 철회를 보장하지 않는다. 다음 요청은 철회를 반영한다. 세션 소유자가 자료를 저장하는 것도 막지 못한다.

`handler_for(delivery)`는 loopback `PreviewServer`와 함께 사용하는 GET/HEAD adapter다. `/media/<grant>`와 `Authorization: Bearer <session>`을 모두 요구하고 Host/Range/HEAD/416/no-store/Vary/Referrer-Policy를 처리한다. 파일 경로나 디렉터리 열람/공개 PASS 제출 route는 없다. 브라우저 video는 Authorization header를 직접 지정할 수 없으므로 실제 UI 연결에는 인증된 same-origin gateway 또는 별도 적절한 전달 전략이 필요하다. 현재 prod에 무리하게 token query/cookie를 추가하지 않는다.

신뢰하는 evaluator의 `record_verdict`는 한 번만 PASS/FAIL과 evidence_ref를 기록한다. 이 함수 자체가 평가자 신원·공격 성능·카메라 진위를 증명하지 않는다. 웹 클라이언트가 verdict를 제출하는 endpoint로 노출하면 안 된다.

`consume(grant, session, action=..., operation=...)`는 PASS/일치/만료/현재 등록부를 확인한 뒤 actions 테이블과 consumed를 한 SQLite transaction으로 기록한다. 등록부 write lock을 local action commit까지 유지해 철회와 직렬화한다. 조직·사용자·operation의 unique 제약으로 여러 grant/동시 소비를 통한 중복도 거부한다. 반환 receipt를 사용하는 외부 부수효과는 별도 transactional outbox/idempotency가 필요하다. 이 코드는 외부 결제/계정 작업을 실행하지 않는다.

합성 review는 임시 테스트에만 존재한다. 실제 운영 reviewer 인증/IdP·TLS·비밀 보관/회전·rate limiting·운영 모니터링·신뢰할 평가·대규모 streaming·deployment는 남는다. 본 구현을 운영 배포 완료로 표시하지 않는다.
