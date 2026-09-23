# Conventions

모든 Component가 따르는 공통 규칙이다. 근거는 `docs/ARCHITECTURE.md`의 해당 절이다. `미정` 항목은 결정 후 채운다.

## Timestamp (ARCHITECTURE 9절)

- 형식: UTC, ISO 8601, `Z` 접미사. 예: `2026-09-09T05:20:13.425Z`
- 기준: 로컬 시스템 시간이 아닌 이벤트 발생 시각
- Simulator가 생성한 timestamp를 하위 Component가 변경 없이 유지한다 (17절)
- 소수점 이하 자릿수(밀리초 고정 여부): 미정

## ID (ARCHITECTURE 11절)

| ID | 대상 | 예 | 생성 | 형식·유일성 범위 |
|---|---|---|---|---|
| `sensor_id` | 설비 또는 센서 | `motor01` | Factory Simulator | 미정 |
| `product_id` | 생산된 개별 제품 | `P-00001024` | Factory Simulator | `P-` + 0으로 채운 8자리 10진수 (정규식 `^P-[0-9]{8}$`). 유일성 범위: 미정 |
| production sequence | 제품 생산 순서 | 미정 | 미정 | 미정 |

모든 Vision 결과는 가능한 한 `product_id`를 포함한다.

## Ground Truth (ARCHITECTURE 3.4, 8절)

`fault_level`, 생성한 defect type 등 Ground Truth는 AI Runtime 추론 입력에 포함하지 않는다. 학습 데이터 생성, 평가, 시뮬레이터 검증, 디버깅에만 사용한다.

## 이름·단위·오류 표현

- Topic·Payload 필드 이름 규칙: 미정 (아키텍처 예시는 소문자 snake_case 필드, `/` 구분 소문자 topic)
- Equipment State 값: `NORMAL`, `CAUTION`, `WARNING`, `CRITICAL` (4.2, 4.4절). 대소문자 표기 확정은 INTERFACES에서 한다
- 물리 단위(진동, 온도, bbox 좌표계): 미정
- 오류 표현: 미정. Production 수준의 Retry·복구 규칙은 두지 않는다 (12절)

## 실행 환경과 설정 (ARCHITECTURE 13, 14절)

- IP, Hostname, Port, MQTT Broker URL, Database URL, Image Directory, Model Path, Sampling Rate, FFT Window Size, Fault Parameters, Threshold, Topic Name은 코드에 하드코딩하지 않는다
- 환경 변수 또는 설정 파일(`.env`, `config.yaml`)을 사용한다. 실제 값이 든 `.env`는 commit하지 않는다
- Image Storage: 하위 디렉터리는 `products/`, `training/`, `gradcam/`, `evaluation/` (5.4절). 루트 경로는 각 프로세스가 설정(`IMAGE_ROOT` 등)으로 받으며, MQTT에는 루트 기준 상대 경로만 싣는다 (`docs/INTERFACES.md` Image Reference)
- 공통 실행 방식(Docker Compose 등): 미정

## Shared Issue 메타데이터

Shared Issue 메타데이터의 `created_at`도 UTC ISO-8601을 사용한다.
