# prod 사용성 개선 실행본

후속 피드백은 이 폴더의 같은 실행본에 누적합니다. 운영 배포·새 참가자 모집·다른 연구 백로그는 포함하지 않습니다.

## 실행 (Windows PowerShell)

Node.js가 필요합니다. 현재 PC의 Node v24.18.0으로 실행했습니다.

```powershell
Set-Location -LiteralPath 'C:\Users\조영준!\Documents\CLI\usability\handcaptcha'
node .\experiments\prod_usability\server.cjs 8770
```

기본 URL 하나: **http://127.0.0.1:8770/experiments/prod_usability/**

현재 전달 시 이 포트에서 서버를 실행해 두었습니다. 이미 실행 중이면 URL만 여세요. 종료는 서버 터미널에서 `Ctrl+C`, 재실행은 같은 명령입니다. `EADDRINUSE`면 기존 서버가 실행 중인지 URL에서 확인하세요. 다른 서비스의 프로세스를 임의로 종료하지 마세요.

Chrome/Edge에서 localhost 카메라 권한을 허용하세요. 카메라 오류는 화면에 오류 이름과 함께 표시합니다. `NotAllowedError`는 주소창 사이트 권한을 확인하고, `NotReadableError`는 카메라를 사용하는 다른 앱을 닫은 뒤 **처음부터 다시 시작**을 누르세요. `file://`로 열지 마세요.

HTML 재생성은 `node .\experiments\prod_usability\build.cjs`입니다. 실행만 할 때는 빌드할 필요가 없습니다. 변경은 `app.js`, `selector.js`, `ui.css`, prod 연결 변경은 `build.cjs`에 합니다. 생성된 `index.html`만 직접 고치지 마세요. `start.ps1`도 제공하지만 PowerShell 스크립트 실행이 차단된 PC에서는 위 Node 명령을 사용하세요.

## 5분 점검표

1. **0–3분: 혼자 따라 하기.** 중앙 안내에 맞춰 손 전체를 비춰 주세요. 초록 테두리가 생기면 내 손을 반투명 손에 겹치고, 가림 밖으로 보이는 손가락을 따라 하세요. 마지막에 **결과 JSON 저장**을 누르세요.
2. **3–4분: 여러 손 확인.** 다시 시작하고, 작은 손과 큰 손을 함께 넣으세요. 충분히 큰 손이 안정 선택되는지 보세요. 선택 후 다른 더 큰 손을 넣어도 초록 테두리가 기존 손을 따라야 합니다. 크기가 비슷하면 손 하나를 더 가까이 보여 달라는 안내가 나와야 합니다.
3. **4–5분: 소실·재시작.** 선택 손을 약 2초 빼세요. “손이 1.5초 이상 이탈해 재시작합니다” 안내가 화면 중앙에 표시됩니다. 손을 다시 넣으면 첫 자세부터 시작합니다. 따라 하기 어려웠던 장면을 알려 주세요.

## 기준과 자산

- 기준 브랜치: 두 저장소 `work/todo-consolidation-20261103`. 기존 로컬 이력과 달라 원격 기준에서 `work/ui-usability-20261118` worktree를 만들었습니다.
- prod 기준 commit: `e03bcfa602500ce7346169181a2344999a07c3d5`.
- 복사한 원본: `hand_captcha_prod.html`.
- 원본 SHA-256: `0d82dd439fe7976f8b860eb82e654e6f5637b2d7a3fcce2d02f2f99e5f5bea11` (`baseline.json`에도 기록).
- 진입: `experiments/prod_usability/index.html`. 원본 prod 변경 없음.
- 실제 저장소 `pool_manifest.json`의 8개 `custom01`–`custom08` 영상·좌표를 원래 순서 선택/미러 규칙으로 사용합니다. 점수 공식·가중치·통과 기준·문제 내용은 유지합니다.
- MediaPipe Hands `0.4.1675469240`, drawing_utils `0.3.1675466124`는 기존과 동일하게 unpkg에서 로딩하므로 인터넷이 필요합니다. 모델/CDN 오류면 서버·인터넷을 확인 후 새로고침하세요. 로컬 영상·좌표가 없으면 원격 다른 문제나 가짜 결과로 대체하지 않습니다.
- 서버는 loopback에만 바인딩하며 이 실행본과 manifest의 영상·좌표만 제공합니다. 원시 카메라 영상은 서버로 전송하지 않습니다. 원본의 `UPLOAD_URL`은 빈 값이며 결과는 명시적 JSON 다운로드로 보관합니다. JSON에는 기존 손 landmark 기록이 포함됩니다.

## 표시와 선택 정책

- 카메라 요청은 원본과 같이 이상값 640×480이며 FPS는 브라우저/장치 협상값입니다. 화면 표시 크기와 입력 해상도는 다릅니다. 추론 입력은 원본 `cameraVideo` 프레임이며 합성 canvas를 입력하지 않습니다.
- 원본 카메라의 셀피 미러 판정(장치 facingMode/라벨)을 유지합니다. 목표는 기존 좌우손 문제 규칙에 따라 미러합니다. 시각 합성을 채점 좌표에 추가 적용하지 않습니다. 장치가 facingMode를 보고하지 않는 웹캠은 미러가 적용되지 않을 수 있으므로 첫 실기에서 확인해야 합니다.
- 기존 가림 영상을 불투명도 42%로 카메라 화면 중앙에 합성합니다. 두 영상의 종횡비를 유지합니다. 안내는 손 선택 대기 중에는 카메라 중앙, 수행 중에는 화면 아래 한 곳에 표시합니다. 배경이 겹치면 대비가 낮아질 수 있습니다.
- 최대 4개 검출 손 중 유효한 21점·유한 x/y/z·프레임 내부 후보를 사용합니다. 가까움의 대용값은 **정규화 bbox 면적 `(maxX-minX)*(maxY-minY)`**이며 실제 거리나 신원은 보장하지 않습니다. 상대 landmark z를 거리로 쓰지 않습니다. 자세에 따른 면적 변화도 있습니다.
- 설정은 `selector.js`의 `DEFAULTS`: 진입 면적 **0.035 (프레임 면적의 3.5%)**, 유지 면적 **0.024 (2.4%)**, 초기 안정화 **350ms**, 유사 크기 비율 **1.12**, 누락 유예 **1500ms**입니다. 모두 임시 개발값이며 사용자의 실기 피드백으로 조정합니다.
- 반환 인덱스/손 라벨로 추적하지 않고 중심 이동·면적 비율·정규화 형태의 연속성으로 기존 손을 유지합니다. 큰 다른 손으로 자동 전환하지 않습니다. 크기 동률은 대기하고 교차 모호성은 폐기합니다. 비슷한 손이 같은 위치를 차지하는 경우를 완전히 식별할 수 없습니다.
- 짧은 누락은 `lm:null`로 기존 누락 기록을 남기며 hold를 끊습니다. 과거 좌표로 채우지 않습니다. 1500ms 초과 소실은 현재 시도를 폐기하고 hold·관문·세그먼트·sessionLog·좌우손 버퍼를 초기화한 뒤 카메라/모델을 유지하며 자동으로 손 선택 대기로 돌아갑니다. 손 교차 모호성도 즉시 새 시도로 돌아갑니다. 추론/자산 오류는 안내 후 수동 재시작이 필요합니다. 새 손이 안정 선택되면 새 문제를 처음부터 시작합니다. 200ms 이상 콜백 간격에서는 관문 hold를 초기화합니다.

다음 목표 영상의 로딩·seek 중에는 이전 가림 프레임과 그 미러 방향을 유지하고, 새 영상의 해당 프레임이 준비되면 교체합니다.

## 검증

`node --test .\experiments\prod_usability\selection.test.cjs` — 후보 유효성/최소 크기/순서 변경/동률/큰 방해 손/교차/짧고 긴 누락/크기 경계, 원본 점수 함수·상수 동일성과 고정 입력 점수 회귀를 검사합니다.

브라우저 검사는 `browser-check.cjs`로 실제 페이지·모델·문제 영상 로딩, 합성 관측으로 관문→수행→점수→결과 JSON 다운로드, 선택 손 데이터 연결과 재시작을 확인합니다. QA용 의존성은 실행본 외부 `usability/qa`에 설치했습니다. 재구성 시 `usability` 폴더에서 `npm.cmd install --prefix qa --cache qa/npm-cache playwright-core@1.65.1 --ignore-scripts --no-audit --no-fund`, 서버 실행 후 handcaptcha 루트에서 `node .\experiments\prod_usability\browser-check.cjs`를 실행합니다. 설치 버전은 QA package-lock을 기준으로 합니다. QA 브라우저는 Chrome headless에서 GPU를 끄고 합성 카메라를 사용합니다. `preview.png` 역시 합성 입력 화면입니다.

실제 카메라를 사용하는 사람의 손 선택·겹침 가독성·성공/불편 정도는 확인 대기입니다. 합성 좌표로 산출한 점수는 사용자 성능이나 보안 성능의 증거가 아닙니다. 최종 자동/브라우저 결과는 `VALIDATION.md`에 기록합니다.

## 버전 보관

- 첫 전달 버전: 로컬 Git 태그 `usability-v1-20261118`. 별도 ZIP은 `usability/backups/prod_usability_v1_20261118.zip`이며 실행 서버에 노출하지 않습니다.
- 자동 재시작과 영상 유지 버전은 로컬 Git 태그 `usability-v2-20261118`과 `usability/backups/prod_usability_v2_20261118.zip`에 저장했습니다.
- 중앙 시작 안내와 하단 통합 안내를 적용한 버전은 로컬 Git 태그 `usability-v3-20261118`과 `usability/backups/prod_usability_v3_20261118.zip`에 저장했습니다. 같은 기본 URL에서 열립니다.
