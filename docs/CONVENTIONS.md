# Conventions

모든 Component가 따르는 공통 규칙이다. 근거는 `docs/ARCHITECTURE.md`의 해당 절이다. `미정` 항목은 결정 후 채운다.

## Timestamp (ARCHITECTURE 9절)

- 형식: UTC, ISO 8601, `Z` 접미사, 밀리초 3자리 고정. 예: `2026-09-09T05:20:13.425Z`. 정규식 `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$`
- 밀리초 미만은 버린다(반올림하지 않음)
- 기준: 로컬 시스템 시간이 아닌 이벤트 발생 시각. 각 Payload의 timestamp 의미는 `docs/INTERFACES.md`의 해당 Interface에 적는다
- Simulator가 생성한 timestamp를 하위 Component가 변경 없이 유지한다 (17절)

## ID (ARCHITECTURE 11절)

| ID | 대상 | 예 | 생성 | 형식·유일성 범위 |
|---|---|---|---|---|
| `sensor_id` | 설비 또는 센서 | `motor01` | Factory Simulator | 정규식 `^[a-z][a-z0-9_]{0,31}$`. 시스템 안에서 유일. Topic 경로와 Payload에 같은 값을 쓴다 |
| `product_id` | 생산된 개별 제품 | `P-00001024` | Factory Simulator | `P-` + 0으로 채운 8자리 10진수 (정규식 `^P-[0-9]{8}$`). 유일성 범위: Image Storage 볼륨 하나의 수명. 번호는 투입 순서로 커진다. 발행된 번호 사이에 빈 번호가 있을 수 있다. 볼륨을 지우면 1부터 다시 시작한다 |
| production sequence | 제품 생산 순서 | `1024` | Factory Simulator | `product_id`의 숫자 부분. 별도 필드를 두지 않는다 |

모든 Vision 결과는 가능한 한 `product_id`를 포함한다.

## Ground Truth (ARCHITECTURE 3.4, 8절)

`fault_level`, 생성한 defect type 등 Ground Truth는 AI Runtime 추론 입력에 포함하지 않는다. 학습 데이터 생성, 평가, 시뮬레이터 검증, 디버깅에만 사용한다. runtime Ground Truth의 위치와 형식은 `docs/INTERFACES.md` Ground Truth. 예외: 현재 범위의 Vision은 추론 없이 판정값을 전달하려고 `ground_truth/products.jsonl`의 `defect`, `defect_type`을 읽어 Vision Result로 옮긴다(ARCHITECTURE 4.3절 현재 범위, 8절). AI 추론 입력이 아니므로 위 원칙과 충돌하지 않는다.

## Payload·이름·단위·오류 표현

- Payload: UTF-8 JSON 객체 하나
- 이름: Payload 필드는 소문자 snake_case, Topic은 `/`로 구분한 소문자
- 버전: 모든 Payload에 `schema_version`(정수)을 둔다. 필드 삭제·이름 변경·의미 변경만 버전을 올린다. 선택 필드 추가는 버전을 올리지 않는다. 소비자는 모르는 필드를 무시한다
- 열거값: 대문자(예: `RUNNING`, `STOP`, `APPLIED`). 단, 결함 유형은 소문자(`scratch`, `dent`, `contamination`)
- Equipment State 값: `NORMAL`, `CAUTION`, `WARNING`, `CRITICAL` (4.2, 4.4절)
- 물리 단위: 진동 가속도 g(표준 중력가속도 배수), 온도 °C, 회전 속도 rev/min, 길이 m, 이미지 좌표 px(왼쪽 위 원점, x 오른쪽, y 아래)
- 오류 표현: 오류 응답 Topic을 두지 않는다. 수신자는 잘못된 메시지를 적용하지 않고 로그로 남긴다. Conveyor Control의 거부는 Line Status `last_command`로 알린다 (`docs/INTERFACES.md`). Production 수준의 Retry·복구 규칙은 두지 않는다 (12절)

## 실행 환경과 설정 (ARCHITECTURE 13, 14절)

- IP, Hostname, Port, MQTT Broker URL, Database URL, Image Directory, Model Path, Sampling Rate, FFT Window Size, Fault Parameters, Threshold, Topic Name은 코드에 하드코딩하지 않는다
- 환경 변수 또는 설정 파일(`.env`, `config.yaml`)을 사용한다. 실제 값이 든 `.env`는 commit하지 않는다
- Image Storage: 하위 디렉터리는 `products/`, `ground_truth/`, `training/`, `gradcam/`, `evaluation/` (5.4절). 루트 경로는 각 프로세스가 설정(`IMAGE_ROOT` 등)으로 받으며, MQTT에는 루트 기준 상대 경로만 싣는다 (`docs/INTERFACES.md` Image Reference)
- 공통 실행 방식: Docker Compose. 시스템 compose 정의는 `integration`이 소유한다 (19.1절). Image Storage는 Docker named volume이며 호스트 폴더 bind mount를 쓰지 않는다

## Shared Issue 메타데이터

Shared Issue 메타데이터의 `created_at`도 UTC ISO-8601을 사용한다.
