# 손동작 CAPTCHA V4

`usability-v3-20261118` (`3982936`)을 복사해 두 화면의 배치를 비교할 수 있게 했습니다. 원본 prod와 `experiments/prod_usability/`의 V3는 비교용입니다.

PowerShell에서 `CLI` 폴더를 기준으로 실행합니다.

```powershell
node .\usability\handcaptcha\experiments\prod_usability_v4\server.cjs 8771
```

http://127.0.0.1:8771/experiments/prod_usability_v4/

브라우저에서 카메라 접근을 허용해 주세요. 가림 영상과 문제 좌표는 저장소의 파일을 읽고, 손 인식 모델은 기존 CDN에서 읽으므로 인터넷 연결이 필요합니다. 종료는 서버 터미널에서 `Ctrl+C`입니다. V3 비교가 필요하면 `node .\usability\handcaptcha\experiments\prod_usability\server.cjs 8770`을 별도 터미널에서 실행합니다.

## 5분 점검

1. **첫 1분.** 카메라를 허용하고 손을 비춰 주세요. 기본 배치에서 ‘따라 할 손’이 크게, ‘나의 손’이 작게 보이는지 확인합니다. 시범의 손가락을 보며 따라 해 보세요.
2. **다음 2분.** 영상이 움직일 때 **내 손 크게**를 누르세요. 문제와 영상이 이어지는지 확인하고 **따라 할 손 크게**로 돌아와 두 배치에서 시범과 내 손을 얼마나 쉽게 비교할 수 있는지 살펴보세요.
3. **마지막 2분.** 창 폭을 좁혀 위아래로 배치되는지, 작은 화면에서 손끝과 움직임이 보이는지 확인하세요. 시도를 끝까지 진행하고 **결과 JSON 저장**을 눌러 보세요.

전환 버튼은 배치만 바꿉니다. 두 모드는 동일한 비디오 요소, 카메라 스트림, 손 선택과 채점 상태를 사용합니다. 두 영상은 종횡비를 유지하며 각 창 안에 들어갑니다. 다음 목표 영상이 준비될 때까지 이전 가림 프레임을 유지합니다.

## 검증 방법

`handcaptcha` 폴더에서 실행합니다.

```powershell
node .\experiments\prod_usability_v4\build.cjs
node --test .\experiments\prod_usability_v4\selection.test.cjs
node .\experiments\prod_usability_v4\browser-check.cjs
```

브라우저 검사는 V4 서버가 실행 중이어야 하며, 기존 QA 환경과 동일하게 Chrome 및 `usability/qa`의 `playwright-core`를 사용합니다. 실제 목표 영상과 모델을 로딩하고 카메라·랜드마크 입력을 합성합니다.

자동 검사 8개가 통과했습니다. Chrome에서 재생 도중 전환해 같은 스트림과 카메라 트랙, 영상 위치, 반전, 문제와 기록이 유지되는 것을 확인했습니다. 넓은 화면과 390px 화면에서 두 배치가 겹치지 않는 것과 실제 가림 영상 재생, 7개 구간 수행, 채점 및 JSON 다운로드도 확인했습니다. 실제 웹캠과 사람 손으로 하는 비교는 아직 진행하지 않았습니다.
