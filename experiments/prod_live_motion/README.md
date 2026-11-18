# 손동작 CAPTCHA 실시간 생성 체험

공개 V4의 복제본입니다. [실시간 생성 체험](https://mukgore.github.io/handcaptcha/experiments/prod_live_motion/)을 열고 카메라를 허용한 다음, 손을 화면 중앙에 비추고 시범을 따라 합니다. 실시간 3D와 2D는 시도 중에도 같은 동작을 다른 표현으로 보여줍니다. 촬영 영상 모드로 들어가거나 나오면 새 시도가 시작됩니다.

- **실시간 3D**는 공통 3차원 골격에 맞춰 손가락 표면을 변형하고 깊이와 조명을 적용합니다.
- **실시간 2D**는 같은 골격을 같은 카메라에서 투영한 좌표로, 손을 단색 도형으로 그립니다. 두 모드에서 손가락은 굽힘과 옆 벌림을 함께 수행합니다.
- **기존 촬영 영상**은 공개 V4에서 사용하는 MP4 문제 풀을 재생합니다.

생성 모드는 네 가지 동작 중 서로 다른 두 가지를 고르고 진폭·속도·손목 회전량을 조금씩 바꿉니다. 기존 자세 관문, 채점, 두 렌더러는 같은 프레임 좌표를 사용합니다. 중심을 30px 내린 반지름 90px 원을 적용합니다. 각 프레임에서 중지 PIP 주변과 앞 두 마디의 표면이 가려지고, 다른 손끝 단서가 두 개 이상 남는지 검사합니다. 자세 전환마다 화면에 남는 손끝 중 하나 이상이 움직여야 합니다. 검사에 실패한 동작은 표시 전에 제외합니다. 생성 영상은 브라우저에서 바로 그리며 결과 JSON은 직접 내려받을 수 있습니다.

관절 모델은 Cobos 등의 MCP 옆 벌림·굽힘과 PIP·DIP 굽힘 구분을 따릅니다. Mentzel 등의 주먹 쥐기 실측에서 관찰된 손가락별 DIP/PIP 굽힘 비율을 작은 굽힘의 근사에 사용하고, Häger-Ross와 Schieber가 관찰한 중지·약지의 동반 움직임을 반영했습니다. 적용 각도, 속도, 패턴 구성은 체험용 공학 선택입니다. 실제 사람의 모방 가능성과 운영 인증 성능은 별도 검증 대상입니다. [Cobos 외 (2008)](https://oa.upm.es/4040/) · [Mentzel 외 (2011)](https://pubmed.ncbi.nlm.nih.gov/21452110/) · [Häger-Ross와 Schieber (2000)](https://pmc.ncbi.nlm.nih.gov/articles/PMC6773164/)

## 로컬 실행

저장소 루트에서 실행하고 출력된 localhost 주소로 접속합니다. 손 인식 모델을 불러오려면 인터넷 연결이 필요합니다.

```powershell
node experiments/prod_live_motion/server.cjs 18872
```

V4 기준본은 `79f6fef`의 `experiments/prod_usability_v4/index.html`입니다. `node experiments/prod_live_motion/build.cjs`로 복제본을 다시 만듭니다. `browser-check.cjs`는 Playwright와 Chrome으로 카메라 초기화, 세 모드와 영상 전환, 가림 픽셀, 채점 함수 일치를 확인합니다. 개발 환경에서는 합성 카메라 장치를 사용합니다.
