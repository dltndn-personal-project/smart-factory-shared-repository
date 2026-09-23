# Interfaces

아직 승인된 Interface는 없다. 아래 목록은 `docs/ARCHITECTURE.md` 5.1절 Topic 구조와 7절 데이터 흐름에서 도출한 후보이며, Payload Schema는 미정이다.

## Interface 후보

| Interface | MQTT Topic (후보) | 생산자 | 소비자 | 아키텍처 근거 | 상태 |
|---|---|---|---|---|---|
| Sensor Vibration | `factory/sensor/<sensor_id>/vibration` | factory-simulator | predictive-maintenance, factory-operations (Time-Series DB 적재 포함) | 4.1, 4.4, 5.2, 7.1 | 미정 |
| Product Created | `factory/product/created` | factory-simulator | vision-inspection, factory-operations | 3.3, 4.3, 7.2 | 미정 |
| PdM Result | `factory/pdm/result` | predictive-maintenance | factory-operations | 4.2, 7.1, 7.3 | 미정 |
| Vision Result | `factory/vision/result` | vision-inspection | factory-operations | 4.3, 7.2 | 미정 |
| Alarm Event | `factory/alarm/event` | factory-operations | 미정 | 4.4 | 미정 |
| Conveyor Control | `factory/control/conveyor` | factory-operations | factory-simulator | 4.4, 7.3 | 미정 |
| Line Status | `factory/line/status` | factory-simulator | factory-operations | 4.1, 4.4 | 미정 |

Line Status는 4.4절 Data Integration의 설비·생산 상태(Conveyor 동작/정지, 현재 Fault Level, 생산 진행)를 전달하고, Conveyor Control 명령의 결과 확인에도 쓴다. Topic 이름에 `simulator`를 쓰지 않는 것은 Simulator Replacement Principle(ARCHITECTURE 15절)에 따라 내부 구현을 드러내지 않기 위해서다. 여기의 Fault Level은 Dashboard 표시와 평가용이며 AI 추론 입력이 아니다(ARCHITECTURE 8절).

## Image Reference

이미지를 참조하는 모든 Interface(Product Created의 `image_path`, Vision Result의 `image_path`·`gradcam_path`)에 적용한다.

- 저장 위치: Image Storage는 하나의 공유 Docker Volume이다. 기록하는 프로세스와 읽는 프로세스가 같은 볼륨을 마운트한다. 볼륨 정의는 `integration`이 소유한다 (ARCHITECTURE 19.1절).

| 디렉터리 | 기록 | 읽기 |
|---|---|---|
| `products/` | factory-simulator | vision-inspection, factory-operations |
| `training/`, `evaluation/` | factory-simulator | vision-inspection (학습·평가) |
| `gradcam/` | vision-inspection | factory-operations |

- 경로 표기: MQTT에는 Image Storage 루트 기준 상대 경로만 싣는다. 예: `products/P-00001024.jpg`. 절대 경로와 루트 디렉터리는 각 프로세스의 설정으로 받는다 (ARCHITECTURE 14절).
- 발행 전제: 생산자는 파일 기록을 끝낸 뒤에 이벤트를 발행한다. 임시 이름으로 기록한 뒤 최종 이름으로 rename하여, 소비자가 최종 경로에서 불완전한 파일을 보지 않게 한다. 소비자는 이벤트 수신 시점에 파일이 완성되어 있다고 가정한다.
- 유지 기간: 삭제 정책을 두지 않는다 (ARCHITECTURE 12절).

## 작성 항목

다음 항목을 실제 통신 단위마다 작성한다.

- 이름과 계약 버전, 생산자와 소비자
- 채널·endpoint·topic 및 payload의 필수/선택 필드와 단위
- 발행 전제와 수신 시 보장되는 상태
- 중복·순서·실패·재시도·시간 제한의 책임. 이 프로젝트는 멱등성·재전송·중복 제거를 구현하지 않으므로(ARCHITECTURE 3.2, 12절) 해당 없음과 그 전제를 명시한다
- 파일 등 외부 자원의 접근 위치와 유지 기간
- Ground Truth 필드가 AI 추론 입력 Payload에 들어가지 않는지 (ARCHITECTURE 8절)
- 정상·오류 예제와 호환성 검증 방법

Breaking change에서는 구·신 계약 공존 또는 검증된 전체 조합 동시 전환 중 실제 전략을 명시한다. 전환 조건·폐기 조건·실패 시 복구 방법이 없는 상태에서 기존 계약을 즉시 대체하지 않는다.

Component의 `contract_ref`는 문서를 읽을 기준 commit이며 호환성을 증명하는 테스트 결과가 아니다. 계약 채택 변경은 관련 구현·검증 결과와 함께 기록한다.
