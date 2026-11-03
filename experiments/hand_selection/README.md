# 큰 손 선택 · 분리/중첩 화면 실험

기존 prod와 분리된 개발용 시연이다. 점수·관문·인증·자동 저장·업로드를 하지 않는다. MediaPipe Hands의 기존 고정 CDN 버전을 로드하고 원본 카메라에서 최대 2개 손을 검출한다. 원본 카메라 입력과 가린 문제 영상의 화면 합성을 분리한다.

저장소 루트에서 `python -m http.server 8765 --bind 127.0.0.1`을 실행하고 `http://127.0.0.1:8765/experiments/hand_selection/`를 연다. 가림 완료 영상 MP4/WebM을 로컬 파일 선택기로 고른다. 분리/중첩, 투명도, 문제 반전 조건을 정하고 카메라 시작을 누른다. 카메라 허용은 사용자가 수행한다. 영상은 브라우저의 blob URL로 읽고 전송하지 않는다. 검출기 모델 다운로드에는 네트워크가 필요하다.

가장 큰 유효 bbox를 8 callback 동안 안정화한 뒤 위치·크기·상대 형태의 연속성으로 유지한다. 유효한 21개 x/y/z 좌표와 화면 안 x/y, 양의 면적을 요구한다. 비슷한 면적의 두 손은 초기 선택을 미루며, 선택 후 소실/모호성은 즉시 중단한다. 재선택은 전체 페이지·시도를 초기화한다. 가까운 다른 사람의 손이 선택되거나 유사한 손으로 오연결될 가능성은 남으므로 신원 확인으로 쓰지 않는다.

`selection.js`의 모든 기본값은 공학 초기값이며 검증된 연구/운영 기준이 아니다. 손가락 펼침·부분 잘림·fps·빠른 동작에 민감할 수 있다. 짧은 자동 재연결과 prod timer/coverage/채점 통합은 구현하지 않았다. 실제 카메라·기기/레이아웃·사용성 검증 전이다.

```powershell
node --test experiments/hand_selection/selection.test.cjs experiments/hand_selection/demo.test.cjs
```

전체 요구사항과 평가 카드는 [codex 통합 목록](https://github.com/mukgore/codex/blob/work/todo-consolidation-20261103/docs/backlog_2026-11-03.md)에 있다.
