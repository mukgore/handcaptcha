# 기존 prod를 바탕으로 한 손바닥 안내 수정안

사용자가 원한 것은 `hand_captcha_prod.html` 기반의 여러 수정안이다. 앞서 만든 hand_selection 독립 시연은 이 목적에 맞는 수정안이 아니었다. 이 폴더는 원본 prod를 복제하고 안내만 추가한 세 버전과 비교 화면이다.

- A `a_copy.html`: 원래 상단 배너의 손금 문구와 카메라 패널 바로 위의 짧은 안내.
- B `b_compare.html`: 원래 카메라 패널 위에 손바닥/손등 비교 그림.
- C `c_guide.html`: 원래 회색 손 가이드의 손바닥 면을 강조하고 그 안에 손금 세 줄, 짧은 카메라 모서리 설명.

세 버전 모두 기존 헤더·목표/카메라 패널·진행 점·상태/결과 화면을 사용한다. 카메라 자동 실행, 첫 실제 목표의 표시, 기존 매칭/타이머/채점/미러·handedness 동작은 원본 inline JS 그대로다. 별도 준비 화면이나 확인 단계를 추가하지 않는다. C는 원래 가이드 렌더 함수를 호출한 뒤 기존 generic 손바닥 다각형과 고정 손금을 같은 canvas transform/fade로 덧그린다. 손금은 정답/사용자 좌표에서 만들지 않는다. 안내는 첫 자세를 지난 후 접히고 카메라 헤더의 버튼으로 다시 볼 수 있다. 손바닥 자동 검출로 해석하지 않는다.

## 보기

저장소 루트에서 `python -m experiments.preview_server --port 8767`을 실행하고 아래 주소를 연다. 새 서버는 영상 Range/seek를 지원한다.

`http://127.0.0.1:8767/experiments/prod_palm_variants/`

비교 화면의 기존/A/B/C 버튼은 실제 prod의 HTML/CSS와 렌더러로 정적 예시를 보여 준다. 카메라/모델 시작과 8초 배너 닫기만 생략해 비교한다. 예시 손은 촬영/실제 문제 결과가 아니다. “이 버전 직접 열기”는 카메라를 쓰는 실제 수정본이다. 카메라 허용은 사용자가 수행한다. 직접 연 버전은 기존 prod처럼 모델/문제 자료를 네트워크로 읽는다.

## 캡처

카메라를 실행하지 않은 UI 비교용 캡처다. 손 그림과 목표는 고정 예시다.

| 기존 | A 문구 | B 비교 그림 | C 기존 가이드 |
|---|---|---|---|
| [PC](previews/prod-original-1280.png) | [PC](previews/prod-a_copy-1280.png) | [PC](previews/prod-b_compare-1280.png) · [모바일](previews/prod-b_compare-390.png) | [PC](previews/prod-c_guide-1280.png) |

## 생성과 변경 검토

`python experiments/prod_palm_variants/build.py`는 현재 root prod에서 세 HTML을 다시 만든다. 생성 HTML에는 기준 source 해시와 root 상대 경로를 보존하는 base가 들어간다. 원본 inline 코드와 CSS를 변경하지 않고 stylesheet와 후행 script만 추가한다. 원본 `hand_captcha_prod.html` 파일은 수정하지 않는다. 공통 추가는 guidance.css/js에서 관리한다. build 뒤 생성 diff를 검토한다.

이번 선택은 기존 흐름과의 호환성을 우선한 설계 판단이다. 실제 카메라/기기·사람의 손바닥 제시 성공률·완료시간 효과는 검증이 필요하다. 기존 prod의 연구/보안 한계와 자동 손 방향 판정 문제를 UI 수정으로 해결했다고 주장하지 않는다.

검증: 세 생성본의 원본 inline JS/CSS 전체가 기준 prod와 동일하며 build 출력과 일치함을 확인했다. Chrome 1280/390 폭의 기존/A/B/C 8개 화면에서 가로 넘침·두 패널 보존·안내 표시, 안내 접기/재열기·첫 자세 뒤 접기, C의 원래 fade 종료/globalAlpha 보존을 확인했다. 브라우저 JS 예외는 없었다. 실제 카메라/모델/참여자 검사는 수행하지 않았다.
