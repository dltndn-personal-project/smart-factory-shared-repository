# Interfaces

factory-simulator가 발행·구독하는 4개 Interface(Sensor Vibration, Product Created, Line Status, Conveyor Control), vision-inspection이 발행하는 Vision Result, predictive-maintenance가 발행하는 PdM Result·PdM Spectrum, factory-operations가 발행하는 Alarm Event는 확정이다(`schema_version` 1). 목록의 Interface는 `docs/ARCHITECTURE.md` 5.1절 Topic 구조와 7절 데이터 흐름에서 도출했으며, 현재 후보 상태로 남은 Interface는 없다. 공통 Payload 규칙(인코딩, 이름, `schema_version`, timestamp, 단위, 오류 표현)은 `docs/CONVENTIONS.md`.

## Interface 목록

| Interface | MQTT Topic | 생산자 | 소비자 | QoS | retain | 아키텍처 근거 | 상태 |
|---|---|---|---|---|---|---|---|
| Sensor Vibration | `factory/sensor/<sensor_id>/vibration` | factory-simulator | predictive-maintenance, factory-operations (Time-Series DB 적재 포함) | 0 | false | 4.1, 4.4, 5.2, 7.1 | 확정 |
| Product Created | `factory/product/created` | factory-simulator | vision-inspection, factory-operations | 1 | false | 3.3, 4.3, 7.2 | 확정 |
| PdM Result | `factory/pdm/result` | predictive-maintenance | factory-operations | 1 | false | 4.2, 7.1, 7.3 | 확정 |
| PdM Spectrum | `factory/pdm/spectrum` | predictive-maintenance | factory-operations (Dashboard FFT Spectrum 표시) | 0 | false | 4.2, 4.4 Dashboard, 17 FFT | 확정 |
| Vision Result | `factory/vision/result` | vision-inspection | factory-operations | 1 | false | 4.3, 7.2 | 확정 |
| Alarm Event | `factory/alarm/event` | factory-operations | 없음 (integration이 E2E 검증에서 관찰) | 1 | false | 4.4 Alarm Management, 17 | 확정 |
| Conveyor Control | `factory/control/conveyor` | factory-operations | factory-simulator | 1 | false (factory-simulator는 retained 메시지를 적용하지 않는다) | 4.4, 7.3 | 확정 |
| Line Status | `factory/line/status` | factory-simulator | factory-operations | 1 | true | 4.1, 4.4 | 확정 |

- 접두사 `factory`는 설정으로 바꿀 수 있지만 기본값을 쓴다. 나머지 경로는 고정이다.
- 센서는 초당 10개·약 25 KB라 QoS 0이며 유실을 허용한다(ARCHITECTURE 12절). PdM Spectrum도 표시용이라 QoS 0이며 유실을 허용한다. 이벤트와 상태는 QoS 1이다.
- factory-simulator의 MQTT 연결: MQTT 3.1.1, client_id `factory-simulator`, clean session, keepalive 30초, 인증·TLS 없음(ARCHITECTURE 13절).
- factory-simulator가 만드는 timestamp는 그 프로세스가 실행되는 호스트의 시계(UTC)로 만든다.
- 순서·중복: 재전송·중복 제거·멱등성을 구현하지 않는다(ARCHITECTURE 3.2, 12절). Topic 사이의 도착 순서는 보장하지 않는다.

Topic 이름에 `simulator`를 쓰지 않는 것은 Simulator Replacement Principle(ARCHITECTURE 15절)에 따라 내부 구현을 드러내지 않기 위해서다.

## Sensor Vibration

0.1초 chunk마다 3축 배열 하나를 발행한다. 샘플링 10 kHz.

```json
{
  "schema_version": 1,
  "sensor_id": "motor01",
  "timestamp": "2026-09-25T05:20:13.400Z",
  "seq": 1234,
  "sample_rate_hz": 10000,
  "rpm": 1800.0,
  "temperature": 37.42,
  "vibration_x": [0.0123, -0.0456, "… 1000개"],
  "vibration_y": [0.0101, 0.0022, "… 1000개"],
  "vibration_z": [-0.0031, 0.0007, "… 1000개"]
}
```

| 필드 | 형식 | 의미 |
|---|---|---|
| `sensor_id` | string | `docs/CONVENTIONS.md` ID |
| `timestamp` | string | **첫 샘플**의 시각. i번째 샘플(0부터)의 시각은 `timestamp + i / sample_rate_hz` |
| `seq` | int ≥ 0 | 프로세스 기동 후 chunk 번호. 연속이면 1씩 증가. 빈 구간(호스트 잠자기 등)이 있으면 건너뛴 만큼 증가한다. 재기동하면 0부터 다시 시작한다(감소로 재기동을 알 수 있다) |
| `sample_rate_hz` | int | 10000 |
| `rpm` | number | 이 chunk 동안의 모터 회전 속도. 가동 1800.0, 정지 0.0. 실제 설비의 타코미터 값에 해당하며 Ground Truth가 아니다 |
| `temperature` | number | 이 chunk의 베어링 하우징 온도(°C) 한 값. 소수 2자리 |
| `vibration_x/y/z` | number[1000] | 가속도(g), 소수 4자리. x 수평 반경, y 수직 반경, z 축 방향 |

- 발행 시각은 chunk 구간이 끝난 뒤다(`timestamp` + 0.1초 + 생성 시간). 약 25 KB, 초당 10개.
- chunk 하나의 `rpm`과 진동 상태(Fault Level)는 그 chunk가 **시작하는 시각**(`timestamp`)의 라인 상태다. 구간 도중의 변경은 다음 chunk부터 반영된다.
- 분석 윈도우는 소비자가 정한다. BPFO(107.5 Hz)를 인접 고조파(90·120 Hz)와 나누려면 약 1 Hz 해상도, 즉 연속 10개 chunk(1초)를 이어 붙인 윈도우가 필요하다. 이어 붙일 때 `seq`가 1씩 증가하는지 확인한다.
- 설비 기본값(참고, 설정으로 바뀜): 1,800 RPM, 베어링 SKF 6205 형상(BPFO 107.5 Hz, BPFI 162.5 Hz, 2×BSF 141.4 Hz, FTF 12.0 Hz).
- `fault_level`은 넣지 않는다. 현재 Fault Level은 Line Status에만 있다. 시계열 적재에 `fault_level` 열이 필요하면 적재자가 각 chunk에 as-of join으로 붙인다: chunk `timestamp` 이하의 `timestamp`를 가진 Line Status 중 가장 최근 것의 `fault_level`, 없으면 null. Fault Level이 바뀌면 Line Status가 즉시 발행되고 새 값으로 만든 첫 chunk는 0.1초 이상 늦게 발행되지만, Topic 사이의 도착 순서는 보장되지 않는다. 오차는 변경 경계에서 최대 chunk 하나(0.1초)와 발행 지연(수 ms)이다.
- 정지 중: Conveyor가 `STOPPED`여도 발행을 멈추지 않는다. 같은 주기로 `rpm: 0.0`과 센서 노이즈(표준편차 0.01 g)만 담긴 신호, 서서히 식는 온도를 보낸다. 소비자는 `rpm == 0` chunk를 설비 상태 판정에서 뺄 수 있다(모터가 서 있으면 베어링 결함이 진동으로 드러나지 않는다).

## Product Created

```json
{
  "schema_version": 1,
  "product_id": "P-00000113",
  "timestamp": "2026-09-25T05:20:13.425Z",
  "image_path": "products/P-00000113.jpg"
}
```

- `timestamp`: factory-simulator가 제품 이미지를 받은 시각(검사 카메라 캡처 시각에 해당).
- 발행 전제: 이미지 파일이 최종 경로에 rename으로 완성되었고 Ground Truth 기록이 끝났다(Image Reference, Ground Truth). 수신 시점에 파일은 완성되어 있다.
- 결함 여부·유형·위치, Fault Level은 넣지 않는다(ARCHITECTURE 8절).
- 시간 관계(상관분석 Time Lag 참고): 불량 여부는 투입 시점의 진동 심각도로 정해진다. 기본 설정에서 투입 → 연마·세정 장비 통과 약 6.7초, 투입 → 캡처(`timestamp`) 약 13.3초다(벨트 0.15 m/s, 장비 1.0 m, 검사 지점 2.0 m).
- 순서·중복: 발행 순서는 캡처 순서다. 재전송·중복 제거는 없다.
- 제품 이미지: JPEG(baseline, sRGB), 640 × 640 px, 품질 0.92. 검사 카메라가 칩 바로 위에서 아래를 본 원근 이미지다. 칩 윗면 높이에서 가로·세로 약 0.16 m를 담고, 이미지 오른쪽이 벨트 진행 방향이다. 한 이미지에 칩 하나가 중앙 근처에 있다(칩 긴 변이 폭의 약 69%). 주석·표시는 없다. 결함은 칩 윗면에만 있다.

## PdM Result

센서마다 분석 윈도우(1초)를 0.5초 간격으로 옮기며 윈도우마다 하나를 발행한다. 가동 중 센서당 초당 2개. QoS 1, retain false. factory-operations가 Interlock·Alarm·Dashboard·상관분석에 쓰고, integration은 검증용으로 구독한다.

```json
{
  "schema_version": 1,
  "sensor_id": "motor01",
  "timestamp": "2026-09-25T05:20:14.400Z",
  "window_start": "2026-09-25T05:20:13.400Z",
  "anomaly_score": 0.7518,
  "health_index": 24,
  "state": "CRITICAL",
  "model_version": "v1"
}
```

| 필드 | 필수 | 형식 | 의미 |
|---|---|---|---|
| `schema_version` | 예 | int, 1 | `docs/CONVENTIONS.md` |
| `sensor_id` | 예 | string | 입력 Sensor Vibration의 값 그대로. 결과는 센서마다 따로 낸다 |
| `timestamp` | 예 | string | 분석 윈도우의 **끝**(끝 시각 제외) = 윈도우 마지막 chunk의 `timestamp` + 0.1초. 판정이 가리키는 시점이다. Sensor Vibration의 `timestamp`에서만 계산하고 predictive-maintenance 호스트 시계를 쓰지 않는다(ARCHITECTURE 9, 17절) |
| `window_start` | 예 | string | 윈도우 첫 chunk의 `timestamp` 그대로. 분석 구간은 `[window_start, timestamp)`, 기본 1초 |
| `anomaly_score` | 예 | number | 0 이상 1 이하, 소수 4자리. 진동 심각도의 추정값(0 정상, 1은 학습 범위의 가장 심한 결함). Control Chart(Hotelling T²)와 Autoencoder 점수를 결합해 보정한 값이다. 클수록 이상 |
| `health_index` | 예 | int | 0~100. `floor(100 · (1 − 반올림 전 anomaly_score))`. 그래서 `100·(1 − anomaly_score)`와 최대 1 차이 |
| `state` | 예 | string | `NORMAL`(HI 80~100) \| `CAUTION`(60~79) \| `WARNING`(40~59) \| `CRITICAL`(0~39). 항상 `health_index`에서 ARCHITECTURE 4.2 Equipment State 표로 정한다 |
| `model_version` | 아니오 | string | 결과를 낸 모델 버전(예 `v1`). predictive-maintenance 구현은 항상 넣는다 |

- 발행 전제: 같은 `sensor_id`의 연속 chunk 10개(`seq`가 1씩 증가, 모두 같은 `rpm`이고 `rpm > 0`)를 받아 추론을 마쳤다.
- 발행하지 않는 조건:
  1. 윈도우의 `rpm == 0`(Conveyor 정지 중). 정지 중에는 결과가 없다. Equipment State에 "판정 불가" 값이 없고 정지 여부는 Line Status가 알린다(Sensor Vibration 정지 중 항목).
  2. 기동 뒤, 또는 연속성이 끊긴 뒤 연속 chunk 10개가 아직 모이지 않음. 끊김 = `seq`가 직전 + 1이 아님(QoS 0 유실, 빈 구간, factory-simulator 재기동), `rpm`이 바뀜(정지 ↔ 재가동). 재가동하면 재가동 chunk부터 1초 분량이 모인 뒤 첫 결과가 나오고, 그 `timestamp`는 재가동 chunk `timestamp` + 1초다. 따라서 재가동 뒤 결과의 윈도우에는 정지 전 chunk가 섞이지 않는다.
  3. 입력 Sensor Vibration이 형식을 어겨 적용되지 않음(`docs/CONVENTIONS.md` 오류 표현).
  4. 추론 중 예외(로그만 남긴다).
  5. 모델이 없거나 설정과 맞지 않으면 predictive-maintenance 프로세스가 기동하지 않는다(결과 없음).
- 결과 간격: 가동·무유실이면 0.5초. 센서 chunk 하나가 유실되면 그 뒤 최소 1초 동안 결과가 없다.
- 반응: Fault Level 변경 뒤 새 수준만 담긴 첫 결과는 약 1.0~1.6초 뒤다(윈도우 1초 + hop 격자). 그 사이 결과는 두 수준이 섞인 값이다.
- 평활화: State에 평활화·히스테리시스를 하지 않는다. State는 윈도우 하나의 `health_index`로만 정해진다.
- 중복·순서: QoS 1이라 같은 결과가 두 번 올 수 있다. 소비자는 (`sensor_id`, `timestamp`)로 구분할 수 있다. 재전송·중복 제거·멱등성은 구현하지 않는다(ARCHITECTURE 12절). 같은 센서의 `timestamp`는 발행 순서대로 커지지만 Topic 사이 도착 순서는 보장하지 않는다.
- retain false 이유: 재접속한 소비자가 오래된 판정을 현재 값으로 받지 않게 한다. 새 소비자는 다음 결과(0.5초 이내, 정지 중이면 재가동 뒤)를 기다린다.
- 오류 표현: 오류 결과 메시지는 없다. 소비자는 형식을 어긴 PdM Result(필수 필드 없음, 모르는 `state`, 범위 밖 값)를 적용하지 않고 로그로 남긴다. 모르는 필드는 무시한다.
- Ground Truth: `fault_level`, `severity` 등 Ground Truth 필드를 넣지 않는다(ARCHITECTURE 8절). predictive-maintenance는 Line Status와 `ground_truth/products.jsonl`을 읽지 않는다.
- 정상 예: 위 JSON. 거부해야 할 예: `{"schema_version":1,"sensor_id":"motor01","timestamp":"2026-09-25T05:20:14Z","anomaly_score":0.1,"health_index":85,"state":"normal"}` — timestamp 밀리초 없음, `window_start` 없음, 소문자 `state`.
- 호환성 검증: integration은 수신 메시지마다 필수 필드·타입, timestamp 정규식(`docs/CONVENTIONS.md`), `state`가 `health_index`의 4.2 구간과 맞는지, `window_start < timestamp`, Ground Truth 필드 부재를 검사할 수 있다.
- 크기 약 200 B.

## PdM Spectrum

Dashboard의 FFT Spectrum 표시용 데이터다(ARCHITECTURE 4.4 Dashboard, 17절 FFT). 센서마다 1초에 하나(PdM Result 두 개마다 하나) 발행하며, 같은 윈도우의 PdM Result를 발행한 **뒤**에 보낸다. QoS 0, retain false(표시용, 유실 허용). Interlock·Alarm 판단에는 쓰지 않는다.

```json
{
  "schema_version": 1,
  "sensor_id": "motor01",
  "timestamp": "2026-09-25T05:20:14.400Z",
  "window_start": "2026-09-25T05:20:13.400Z",
  "rpm": 1800.0,
  "freq_step_hz": 1.0,
  "rot_hz": 30.0,
  "bpfo_hz": 107.54,
  "bpfi_hz": 162.46,
  "spectrum_x": [0.0, 0.0002, "… 501개"],
  "spectrum_y": [0.0, 0.0001, "… 501개"],
  "spectrum_z": [0.0, 0.0001, "… 501개"],
  "envelope_x": [0.0, 0.0003, "… 501개"],
  "envelope_y": [0.0, 0.0004, "… 501개"],
  "envelope_z": [0.0, 0.0002, "… 501개"]
}
```

| 필드 | 형식 | 의미 |
|---|---|---|
| `schema_version`, `sensor_id`, `timestamp`, `window_start` | | PdM Result와 같은 의미. 같은 윈도우의 PdM Result와 `timestamp`가 같다 |
| `rpm` | number | 윈도우의 회전 속도(rev/min) |
| `freq_step_hz` | number | 배열 원소 간격. 배열의 k번째 원소는 주파수 `k × freq_step_hz` Hz(k = 0부터). 기본 1.0 |
| `rot_hz`, `bpfo_hz`, `bpfi_hz` | number | 이 윈도우 `rpm`에서 계산한 회전 주파수(1X), 외륜·내륜 결함 주파수(Hz, 소수 2자리). 화면에 표시선을 그리는 용도 |
| `spectrum_x/y/z` | number[] | 축별 원 신호의 단측 진폭 스펙트럼(g), 0 Hz부터 500 Hz까지(기본 501개). 평균 제거, Hann 창, 진폭 정규화 `2·|X|/Σw`(사인파 진폭 a가 a로 읽힘), 0 Hz 값은 0. 소수 4자리 |
| `envelope_x/y/z` | number[] | 축별 포락선 스펙트럼(g), 같은 주파수 축. 2,800~3,600 Hz 대역 통과 뒤 해석 신호 크기의 진폭 스펙트럼. 베어링 결함은 여기서 BPFO(107.5 Hz)와 그 고조파 봉우리로 드러난다. 소수 4자리 |

- 모든 필드가 필수다. 배열 6개는 길이가 같고 원소가 유한한 0 이상의 수다.
- 배열 길이는 `floor(500 / freq_step_hz) + 1`이다. 윈도우 설정이 기본이면 501. 소비자는 길이를 고정값으로 가정하지 말고 배열 길이와 `freq_step_hz`로 축을 그린다.
- 발행 전제·발행하지 않는 조건은 PdM Result와 같다(정지 중·윈도우 미완성이면 없음). 추가로 predictive-maintenance 설정으로 발행 간격을 바꾸거나 발행을 끌 수 있다(기본 윈도우 2개마다, 즉 1초).
- 크기: 약 21 KB(구분자 없는 JSON). 센서당 초당 약 21 KB로 Sensor Vibration(초당 약 250 KB)보다 작다.
- 중복·순서: PdM Result와 같다. QoS 0이라 유실될 수 있고 재전송하지 않는다.
- 오류 표현: 오류 결과 메시지는 없다. 소비자는 필수 필드가 없거나, 배열 길이가 서로 다르거나 `floor(500 / freq_step_hz) + 1`이 아니거나, 유한하지 않은 원소가 있는 메시지를 표시하지 않고 로그로 남긴다(직전 표시 유지). 모르는 필드는 무시한다.
- 거부해야 할 예: `envelope_z`가 빠진 메시지, `spectrum_x` 길이 500(나머지 501), `freq_step_hz: 0`.
- Ground Truth: 넣지 않는다(PdM Result와 같음).
- 호환성 검증: integration은 필드·타입, 배열 길이 규칙, 유한성, 같은 (`sensor_id`, `timestamp`)의 PdM Result가 먼저 발행되었는지(도착 순서는 보장되지 않으므로 참고), Ground Truth 필드 부재를 검사할 수 있다.
- 표시 참고(predictive-maintenance 시험 구현, Fault Level 8, y축): 원 스펙트럼 최대 봉우리 30 Hz(약 0.28 g), 포락선 봉우리 107·108 Hz(약 0.2 g), 215 Hz, 323 Hz.

## Vision Result

제품마다 한 번 발행한다. QoS 1, retain false. 현재 범위(ARCHITECTURE 4.3절 현재 범위)에서 Vision은 AI 판정을 하지 않고 Simulator 불량 정보를 옮긴다(pass-through).

```json
{
  "schema_version": 1,
  "product_id": "P-00000113",
  "timestamp": "2026-09-25T05:20:13.425Z",
  "defect": true,
  "defect_type": "scratch",
  "confidence": null,
  "bbox": null,
  "image_path": "products/P-00000113.jpg",
  "gradcam_path": null,
  "judgement_source": "PASS_THROUGH"
}
```

| 필드 | 필수 | 형식 | 의미 |
|---|---|---|---|
| `schema_version` | 예 | 1 | `docs/CONVENTIONS.md` |
| `product_id` | 예 | string | Product Created의 값 그대로 |
| `timestamp` | 예 | string | Product Created의 `timestamp`(캡처 시각)를 바꾸지 않고 싣는다(ARCHITECTURE 9, 17절). 처리 시각 필드는 두지 않는다 |
| `defect` | 예 | bool | 불량 여부. 현재 범위에서는 Simulator 불량 정보를 옮긴 값 |
| `defect_type` | 예 | string\|null | `scratch`, `dent`, `contamination`(소문자). 양품이면 null |
| `confidence` | 예 | number\|null | 판정 신뢰도(0~1). 현재 범위에서는 항상 null |
| `bbox` | 예 | [int×4]\|null | `[x_min, y_min, x_max, y_max]` px(`docs/CONVENTIONS.md` 이미지 좌표). 현재 범위에서는 항상 null |
| `image_path` | 예 | string | Product Created의 값 그대로 (Image Reference) |
| `gradcam_path` | 예 | string\|null | `gradcam/` 아래 상대 경로. 현재 범위에서는 항상 null |
| `judgement_source` | 아니오 | string | 판정 출처. 현재 범위에서는 `PASS_THROUGH`. 소비자는 무시해도 된다 |

- 값이 없는 필드도 키는 남기고 null을 넣는다. 소비자가 필드 누락으로 파싱에 실패하지 않게 하기 위해서다.
- 입력과 처리(현재 범위): Vision은 Product Created를 구독한다. 받은 `product_id`로 `ground_truth/products.jsonl`에서 같은 `product_id`의 완성된 줄(`\n`으로 끝난 줄)을 찾아 `defect`, `defect_type`만 읽는다. `product_id`, `timestamp`, `image_path`는 Product Created 값을 쓴다. 파일은 읽기 전용으로 접근한다(Image Reference, Ground Truth).
- 발행 전제: Product Created를 검증했고 Ground Truth 줄을 찾았다. Product Created는 Ground Truth 기록이 끝난 뒤 발행되므로(Product Created 발행 전제) 정상이면 수신 시점에 줄이 있다.
- 오류: Product Created가 잘못되었거나, Ground Truth 줄이 없거나, 파일을 읽지 못하면 Vision Result를 발행하지 않고 로그로 남긴다(`docs/CONVENTIONS.md` 오류 표현). 재시도나 오류 결과 메시지는 없다(ARCHITECTURE 12절).
- 순서·중복: 재전송·중복 제거는 없다. 같은 제품의 결과가 두 번 올 수 있으며 소비자는 `product_id`로 구분한다.
- Ground Truth와의 관계: `defect`, `defect_type`은 현재 범위에서 Ground Truth 파일에서 옮긴 값이다. 이 Payload는 AI 추론 입력이 아니며, `judgement_source: "PASS_THROUGH"`로 전달값임을 표시한다(ARCHITECTURE 8절 현재 범위 예외).

## Alarm Event

factory-operations가 Equipment State가 `WARNING` 또는 `CRITICAL`로 **올라갈 때** Alarm을 만들고 발행한다(ARCHITECTURE 4.4 Alarm Management, 17절). QoS 1, retain false. Runtime 소비자는 없고 integration이 E2E 검증에서 관찰한다.

```json
{
  "schema_version": 1,
  "alarm_id": "3b0f6a52-8f0e-4c55-9d7e-2f1c9a4b7e10",
  "timestamp": "2026-09-25T05:20:14.400Z",
  "raised_at": "2026-09-25T05:20:14.412Z",
  "sensor_id": "motor01",
  "severity": "CRITICAL",
  "previous_state": "WARNING",
  "health_index": 18,
  "anomaly_score": 0.82
}
```

| 필드 | 필수 | 형식 | 의미 |
|---|---|---|---|
| `schema_version` | 예 | 1 | `docs/CONVENTIONS.md` |
| `alarm_id` | 예 | string | UUID4(소문자, 하이픈 포함 36자). Alarm마다 새 값. factory-operations의 Alarm History 기록과 같은 값이다 |
| `timestamp` | 예 | string | 원인 PdM Result의 `timestamp`를 바꾸지 않고 싣는다(이벤트 발생 시각, ARCHITECTURE 9, 17절) |
| `raised_at` | 예 | string | factory-operations가 판정한 시각(factory-operations 호스트 UTC). `docs/CONVENTIONS.md` 형식 |
| `sensor_id` | 예 | string | 원인 PdM Result의 값 |
| `severity` | 예 | string | `WARNING` \| `CRITICAL`. 새 Equipment State |
| `previous_state` | 예 | string\|null | 이전 Equipment State(`NORMAL` \| `CAUTION` \| `WARNING` \| `CRITICAL`). 첫 결과이거나 재가동 뒤 첫 판정이면 null |
| `health_index` | 예 | int | 원인 PdM Result의 값(0~100) |
| `anomaly_score` | 예 | number | 원인 PdM Result의 값 |

- 발행 조건: 같은 `sensor_id`의 이전 상태보다 심각도가 높은 `WARNING`·`CRITICAL` PdM Result(첫 결과 포함). 심각도는 `NORMAL` < `CAUTION` < `WARNING` < `CRITICAL`. `CAUTION` 진입과 회복 방향 전이는 발행하지 않는다. factory-operations는 `health_index`로 State를 다시 계산하지 않고 PdM Result의 `state`를 그대로 쓴다.
- 재가동: 라인 재가동(Line Status `conveyor`가 `STOPPED`에서 `RUNNING`으로 바뀜. 사이의 `online: false` 허용)을 보면 라인 센서의 이전 상태를 비운다. 재가동 전 윈도우의 결과는 쓰지 않는다. 재가동 뒤 다시 `WARNING`·`CRITICAL`이 되면 새 Alarm이 생긴다.
- 빈도: 상태가 올라갈 때 한 번. 같은 상태가 이어지면 다시 보내지 않는다. 떨림 억제·확인(ack)·해제 이벤트는 없다.
- 발행 전제: Alarm History 기록(ARCHITECTURE 4.4 Data Persistence)을 요청한 뒤 발행한다. DB 기록 완료를 기다리지 않는다. MQTT가 끊겨 있으면 발행하지 않는다(Alarm History 기록은 한다).
- 순서: 같은 PdM Result로 Interlock STOP(Conveyor Control)도 나가면 Alarm Event를 먼저 **발행**한다. Topic이 달라 소비자의 **수신** 순서는 보장하지 않는다.
- 중복·재전송: 없다(ARCHITECTURE 12절). 소비자는 `alarm_id`로 구분한다.
- 오류 표현: 오류 이벤트는 없다. 발행 실패는 factory-operations 로그로만 남는다. 소비자는 형식을 어긴 메시지를 적용하지 않고 로그로 남긴다(`docs/CONVENTIONS.md` 오류 표현). 모르는 필드는 무시한다.
- Ground Truth: `fault_level` 등 Ground Truth 필드를 싣지 않는다(ARCHITECTURE 8절). `severity`는 Equipment State 문자열(`WARNING` \| `CRITICAL`)이며 Ground Truth의 `severity`(진동 심각도, 0~1 숫자)와 이름만 같고 뜻이 다르다. integration은 Ground Truth 필드 부재를 검사할 때 이 `severity`를 타입(문자열)으로 구분한다.
- 호환성 검증: integration은 필수 필드·타입, `alarm_id` 형식, timestamp 정규식(`docs/CONVENTIONS.md`), `severity`·`previous_state` 값, Ground Truth 필드 부재를 검사할 수 있다. 거부해야 할 예: `severity: "CAUTION"`(발행 대상 아님), `alarm_id` 없음.

## Conveyor Control

명령은 `START`와 `STOP` 두 가지다.

```json
{
  "schema_version": 1,
  "command": "STOP",
  "command_id": "9f1c2e7a-4b1d-4e0a-9a51-0f3b2c7d8e11",
  "timestamp": "2026-09-25T05:21:00.012Z",
  "reason": "INTERLOCK_CRITICAL"
}
```

| 필드 | 필수 | 형식 |
|---|---|---|
| `schema_version` | 예 | 1 |
| `command` | 예 | `START` \| `STOP` |
| `command_id` | 예 | 1~64자 문자열. 발행자가 정한다(UUID 권장). Line Status로 결과를 확인할 때 쓴다 |
| `timestamp` | 예 | 명령 발행 시각. `docs/CONVENTIONS.md` 형식을 권장하고, factory-simulator는 소수 0~6자리의 `Z` 형식도 받는다 |
| `reason` | 아니오 | 200자 이하 문자열. 기록용 |

- 발행: retain false, QoS 1.
- 처리: factory-simulator는 받은 즉시 적용하고 정지 여부를 판단하지 않는다(ARCHITECTURE 4.4, 17절). `STOP`은 모터 0 RPM, 투입 중지, 칩 이동 정지. `START`는 이어서 가동한다. 이미 그 상태면 `NO_CHANGE`.
- 결과는 Line Status의 `last_command`에 `APPLIED`, `NO_CHANGE`, `REJECTED`로 나타나고 Line Status가 즉시 발행된다. 별도 응답 Topic은 없다.
- 거부: JSON이 아니거나 필수 필드가 없거나 값이 틀리면 적용하지 않고 `REJECTED`와 `error`를 남긴다. retained 메시지는 적용하지 않고 `REJECTED`(`error: "retained_ignored"`)로 남긴다. 재기동 시 오래된 명령이 다시 적용되지 않게 하기 위해서다.
- 기동 시 상태는 항상 `RUNNING`이다. 이전 실행의 STOP은 이어지지 않는다.
- factory-simulator는 같은 처리기를 로컬 HTTP로도 연다(개발·시연 보조). 이때 `last_command.source`가 `local`이다.

## Line Status

상태가 바뀌면 즉시, 그리고 1초마다 발행한다. QoS 1, retain. 4.4절 Data Integration의 설비·생산 상태(Conveyor 동작/정지, 현재 Fault Level, 생산 진행)를 전달하고 Conveyor Control 명령의 결과 확인에도 쓴다.

```json
{
  "schema_version": 1,
  "online": true,
  "timestamp": "2026-09-25T05:21:00.020Z",
  "conveyor": "STOPPED",
  "fault_level": 8,
  "motor_rpm": 0.0,
  "sensor_id": "motor01",
  "production_active": false,
  "products": {"spawned": 120, "created": 113, "expired": 0, "in_flight": 7, "last_product_id": "P-00000113"},
  "last_command": {
    "command": "STOP",
    "command_id": "9f1c2e7a-4b1d-4e0a-9a51-0f3b2c7d8e11",
    "source": "mqtt",
    "received_at": "2026-09-25T05:21:00.015Z",
    "result": "APPLIED",
    "reason": "INTERLOCK_CRITICAL",
    "error": null
  }
}
```

| 필드 | 형식 | 의미 |
|---|---|---|
| `online` | bool | 정상 발행은 true. 연결이 비정상으로 끊기면 broker가 LWT `{"schema_version":1,"online":false}`를 retain으로 대신 발행한다. 정상 종료할 때도 같은 메시지를 발행한다. `online: false` 메시지에는 다른 필드가 없다 |
| `timestamp` | string | 발행 시각 |
| `conveyor` | string | `RUNNING` \| `STOPPED` |
| `fault_level` | int | 현재 Fault Level(0~10). Dashboard 표시와 평가용이며 AI 추론 입력이 아니다(ARCHITECTURE 8절) |
| `motor_rpm` | number | 현재 모터 회전 속도 |
| `sensor_id` | string | 이 라인 모터의 센서 |
| `production_active` | bool | 칩을 투입하고 있는지. `RUNNING`이어도 렌더러(브라우저 화면)가 없거나 숨겨져 있으면 false |
| `products.*` | int, string\|null | 프로세스 기동 후 누계. `created`는 Product Created 발행 수 |
| `last_command` | object\|null | 마지막으로 받은 제어 명령과 결과. 기동 후 없으면 null. `result`: `APPLIED` \| `NO_CHANGE` \| `REJECTED`. `source`: `mqtt` \| `local`. 거부된 명령은 알 수 없는 필드를 null로 둔다 |

즉시 발행 조건: `conveyor`, `fault_level`, `production_active`, `last_command`가 바뀔 때, MQTT 연결 직후.

## Image Reference

이미지를 참조하는 모든 Interface(Product Created의 `image_path`, Vision Result의 `image_path`·`gradcam_path`)에 적용한다.

- 저장 위치: Image Storage는 하나의 공유 Docker named volume이다. 기록하는 프로세스와 읽는 프로세스가 같은 볼륨을 마운트한다. 볼륨 정의는 `integration`이 소유한다 (ARCHITECTURE 19.1절). factory-simulator는 쓰기 권한, `gradcam/`을 쓰는 vision-inspection은 쓰기 권한, 나머지는 읽기 전용으로 마운트한다.

| 경로(루트 기준) | 기록 | 읽기 | 내용 |
|---|---|---|---|
| `products/P-XXXXXXXX.jpg` | factory-simulator | vision-inspection, factory-operations | 제품 이미지 (Product Created) |
| `products/.P-XXXXXXXX.jpg.tmp` | factory-simulator | 없음 | 기록 중 임시 파일. 소비자는 점으로 시작하는 파일을 무시한다 |
| `ground_truth/products.jsonl` | factory-simulator | 평가·검증 목적 (Ground Truth). 현재 범위에서는 vision-inspection이 pass-through 판정값 전달 목적으로도 읽는다(Vision Result) | runtime Ground Truth |
| `training/`, `evaluation/` | vision-inspection (필요하면) | vision-inspection | Vision 학습·평가 데이터. factory-simulator는 쓰지 않는다. 현재 범위(ARCHITECTURE 4.3절)에서는 쓰지 않는다 |
| `gradcam/` | vision-inspection | factory-operations | Grad-CAM 결과. 디렉터리는 유지하되 현재 범위에서는 비어 있다(Vision Result `gradcam_path`는 null) |

- 경로 표기: MQTT에는 Image Storage 루트 기준 상대 경로만 싣는다. 예: `products/P-00001024.jpg`. 절대 경로와 루트 디렉터리는 각 프로세스의 설정으로 받는다 (ARCHITECTURE 14절).
- 발행 전제: 생산자는 파일 기록을 끝낸 뒤에 이벤트를 발행한다. 같은 디렉터리의 임시 이름에 끝까지 쓰고 닫은 뒤 최종 이름으로 rename하여, 소비자가 최종 경로에서 불완전한 파일을 보지 않게 한다. 소비자는 이벤트 수신 시점에 파일이 완성되어 있다고 가정한다.
- factory-simulator는 최종 파일이 이미 있으면 덮어쓰지 않고 거부한다. 한 번 발행한 파일은 바꾸거나 지우지 않는다.
- 유지 기간: 삭제 정책을 두지 않는다 (ARCHITECTURE 12절).

## Ground Truth

factory-simulator는 `ground_truth/products.jsonl`(Image Storage)에 Product Created를 발행한 제품마다 한 줄을 추가한다. 발행하지 않은 제품은 기록하지 않는다. 한 줄은 `\n`으로 끝난다. 읽는 쪽은 `\n`으로 끝나지 않은 마지막 줄을 무시한다(기록 중일 수 있다). 기록자는 factory-simulator 하나이며 재기동해도 같은 파일에 이어 쓴다.

```json
{"schema_version":1,"product_id":"P-00000113","timestamp":"2026-09-25T05:20:13.425Z","image_path":"products/P-00000113.jpg","image_size":[640,640],"spawned_at":"2026-09-25T05:20:00.101Z","fault_level":8,"severity":0.7482,"defect_probability":0.3447,"defect":true,"defect_type":"scratch","bbox":[250,301,330,352],"defect_params":{"type":"scratch","center_m":[0.012,-0.008],"length_m":0.04,"angle_deg":35.0,"width_m":0.0009},"render_seed":123456789}
```

| 필드 | 형식 | 의미 |
|---|---|---|
| `product_id`, `timestamp`, `image_path` | | Product Created와 같은 값 |
| `image_size` | [int, int] | [폭, 높이] px |
| `spawned_at` | string | 투입(불량 결정) 시각 |
| `fault_level` | int | 투입 시점 Fault Level |
| `severity` | number | 투입 시점 진동 심각도(0~1, 소수 4자리) |
| `defect_probability` | number | 투입 시점 불량 확률(소수 4자리) |
| `defect` | bool | 실제 불량 여부 |
| `defect_type` | string\|null | `scratch`, `dent`, `contamination`. 양품은 null |
| `bbox` | [int×4]\|null | 이미지 안 결함 영역 `[x_min, y_min, x_max, y_max]` px. Vision 결과의 `bbox`와 같은 표기. 양품은 null |
| `defect_params` | object\|null | 칩 로컬 좌표의 결함 형상. 디버깅용 |
| `render_seed` | int | 렌더링 변화용 seed |

- 용도: Vision의 평가(mAP)·학습 데이터 구성, Operations의 평가, integration의 검증, 디버깅(ARCHITECTURE 3.4, 17절). **AI 추론 입력으로 읽지 않는다.** 이 파일은 MQTT로 전달하지 않는다.
- 현재 범위 예외: vision-inspection은 추론을 하지 않고, Vision Result에 판정값을 옮기려고 이 파일에서 같은 `product_id` 줄의 `defect`, `defect_type`만 읽는다(ARCHITECTURE 4.3절 현재 범위, 8절, Vision Result). 추론 입력이 아니므로 위 금지의 대상이 아니다. 나머지 필드는 읽어도 쓰지 않는다. 모델 판정으로 돌아가면 이 예외는 없어진다.
- integration은 Ground Truth가 MQTT Payload에 없는지 검사할 때 위 필드 목록을 기준으로 쓴다. 단, 현재 범위에서 Vision Result의 `defect`, `defect_type`은 pass-through 결과로 허용하는 예외다(ARCHITECTURE 8절 현재 범위 예외). 검사 대상은 AI 추론 입력 Payload(Product Created 등)와 Vision Result의 나머지 Ground Truth 필드다. vision-inspection의 Ground Truth 파일 읽기는 MQTT Payload가 아니므로 이 검사 대상이 아니다. 대신 Vision Result에 `fault_level`, `severity`, `defect_probability`, `defect_params`, `render_seed`가 없는지 확인한다.
- 파일 하나에 계속 쌓인다(시연 5분에 150줄, 약 60 KB).

## PdM 학습 진동 데이터셋

factory-simulator의 `dataset-pdm` 모드가 만든다. MQTT Interface가 아니라 파일 Interface다.

```text
<출력 폴더>/
├─ manifest.json
└─ segments/
   ├─ L00.vib.npy      # float32, shape (n, 3), 열 순서 x, y, z, 단위 g, 소수 4자리로 양자화
   ├─ L00.temp.npy     # float32, shape (n / 1000,), chunk(0.1초)당 온도 °C
   ├─ L01.vib.npy
   └─ …
```

```json
{
  "schema_version": 1,
  "kind": "factory-simulator/pdm-dataset",
  "generator": {"component": "factory-simulator", "commit": "<40자리 SHA 또는 unknown>", "config_sha256": "<병합한 설정의 sha256>"},
  "seed": 20260925,
  "sensor_id": "motor01",
  "sample_rate_hz": 10000,
  "chunk_samples": 1000,
  "units": {"vibration": "g", "temperature": "degC", "rpm": "rev/min"},
  "start_timestamp": "2026-01-01T00:00:00.000Z",
  "segments": [
    {
      "name": "L00",
      "fault_level": 0,
      "severity": 0.0,
      "rpm": 1800.0,
      "n_samples": 1200000,
      "vibration_file": "segments/L00.vib.npy",
      "temperature_file": "segments/L00.temp.npy",
      "sha256": {"vibration": "…", "temperature": "…"}
    }
  ]
}
```

- 라벨은 구간 단위 `fault_level`과 `severity`다. Equipment State(`NORMAL`~`CRITICAL`)로의 대응과 윈도우 분할은 predictive-maintenance가 정한다.
- 신호는 runtime과 같은 코드·같은 chunk 경계로 만들고, runtime JSON과 같은 소수 4자리로 양자화한다. 온도는 구간마다 그 수준의 정상 상태 온도에서 시작한다(runtime은 Fault Level 변경 뒤 약 60초에 걸쳐 따라간다).
- 기본 구성: Fault Level 0~10 각 120초, 1,800 RPM. 약 158 MB.
- 결정성: 같은 commit, 같은 설정, 같은 seed면 `.npy` 파일이 바이트 단위로 같다.
- 전달: predictive-maintenance는 factory-simulator 이미지로 직접 생성할 수 있다. `docker run --rm -v "$PWD/pdm-data:/out" <factory-simulator 이미지> dataset-pdm --out /out/<이름>`. 만든 폴더를 넘겨받아도 된다. 데이터셋은 Image Storage에 두지 않는다(runtime 볼륨과 수명이 다르다).

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
