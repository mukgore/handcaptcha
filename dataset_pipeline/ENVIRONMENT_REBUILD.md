# Windows CPython3.10 격리 재현환경

기존 환경에는 MediaPipe0.10.9/protobuf5.29.6의 metadata 충돌과 복수 cv2 distribution이 있었다. 기존 Python/venv/PATH를 바꾸지 않고 새 private 환경을 구성했다. 새 기준은 MediaPipe0.10.14, NumPy1.26.4, protobuf4.25.3, OpenCV-contrib4.10.0.84, JAX/JAXLIB0.4.30, SciPy1.14.1, Matplotlib3.9.4다. 새 환경의 pip check와 legacy Hands import 및 실제113frame 추출이 통과했다.

공식 metadata: [MediaPipe0.10.14](https://pypi.org/project/mediapipe/0.10.14/), [OpenCV-contrib4.10.0.84](https://pypi.org/project/opencv-contrib-python/4.10.0.84/), [JAX0.4.30](https://pypi.org/project/jax/0.4.30/). OpenCV 안내의 단일 cv2 distribution 원칙을 따른다. 최신 version으로 자동 교체하지 않는다.

`requirements-win-py310.txt`는 직접 요구 버전이며 완전한 lock이 아니다. 실제 resolution에서 받은26개 wheel/230783583byte의 filename·version·SHA256은 `locks/windows-cp310-20261105.wheels.json`, 설치 lock은 `locks/windows-cp310-20261105.lock`이다. wheel binary와 실제 env는 private_artifacts에만 있다. lock SHA256은70aad5637c73ebd5e3065bad04c7f07e6567991a89662f685df0de7b57c88633다.

새 경로에서 온라인 wheel 수집·새 env 검증:

```text
<python3.10> tools/rebuild_environment.py --output <new_private_output> --download
```

기존 wheelhouse와 저장소 lock으로 새 env를 **네트워크 없이** 재설치:

```text
<python3.10> tools/rebuild_environment.py --output <another_new_private_output> --offline-wheelhouse <existing_private_wheels>
```

기존 경로를 덮어쓰지 않으며 --no-index/--no-deps/--require-hashes로 고정 wheel을 설치한 뒤 pip check/import를 수행한다. Python interpreter/Windows 시스템 binary 자체의 공급과 과거 실험 build 복원·Linux/다른 Python의 동작은 이 lock의 검증 범위 밖이다. codex의 기존 requirements/연구 환경도 바꾸지 않는다.

통합 pipeline 검사: `<new_env_python> tools/run_pipeline_tests.py`. unittest class와 이전 no-argument 함수17개를 모두 실행한다.
