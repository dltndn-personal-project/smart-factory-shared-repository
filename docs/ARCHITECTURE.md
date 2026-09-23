# Smart Factory System Architecture

## 1. 문서 목적

본 문서는 Smart Factory System을 구성하는 모든 컴포넌트가 공통으로 참조하는 시스템 아키텍처 문서다.

각 컴포넌트의 책임 범위와 인터페이스를 명확히 정의하고, 모듈 간 결합도를 낮추며, 데이터 흐름과 공통 인프라 사용 방식을 일관되게 유지하는 것을 목적으로 한다.

시스템은 다음 4개의 핵심 컴포넌트와 공통 인프라로 구성한다.

1. **Factory Simulator**
2. **Predictive Maintenance Engine**
3. **Vision Quality Inspection**
4. **Factory Operations & Control**
5. **Shared Infrastructure**

전체 시스템은 컴포넌트 간 직접 호출을 피하고, **MQTT 기반 비동기 메시징**을 중심으로 연동한다.

---

## 2. Project Scope

본 시스템은 실제 제조 현장에 배포하기 위한 Production System이 아니라, **Smart Factory의 설비 예지보전·Vision 품질검사·통합관제 흐름을 구현하고 검증하기 위한 교육용 PoC 시스템**이다.

따라서 요구사항 충족과 핵심 기능 검증에 직접적으로 필요하지 않은 Production 수준의 비기능 요구사항은 구현 범위에서 제외한다.

### 고려하지 않는 항목

다음 항목은 본 프로젝트의 설계 및 구현 범위에 포함하지 않는다.

* Production 수준의 성능 최적화
* 대규모 트래픽 및 확장성
* 장애 자동 복구
* Retry / Recovery 전략
* 메시지 멱등성 처리
* 중복 메시지 방지
* 고가용성(High Availability)
* Failover
* 보안 및 인증/인가
* 데이터 암호화
* Secret Management
* 데이터베이스 및 파일 백업
* Disaster Recovery

따라서 시스템은 정상적인 개발 및 데모 환경에서 각 컴포넌트가 정상 동작하는 것을 기준으로 설계한다.

단, 과제에서 명시적으로 요구하는 다음 성능 기준은 평가 대상이므로 반드시 충족하고 측정한다.

* Vision Model `mAP@0.5 ≥ 0.80`
* Vision Inference `20 FPS 이상`
* PdM Model `F1-Score ≥ 0.80`
* PdM Inference `100ms 이내`
* Dashboard 데이터 `5초 이내 갱신`

즉, **과제 검증에 필요한 성능 측정은 수행하지만 Production 운영을 위한 성능·안정성 최적화는 수행하지 않는다.**

---

# 3. Architecture Principles

시스템 설계 시 다음 원칙을 공통으로 적용한다.

### 3.1 Separation of Concerns

각 컴포넌트는 하나의 명확한 책임 영역을 가진다.

* Factory Simulator: 공장 환경 및 데이터 생성
* Predictive Maintenance: 설비 상태 분석
* Vision Quality Inspection: 제품 품질 분석
* Factory Operations & Control: 데이터 통합 및 공장 제어

다른 컴포넌트가 담당하는 분석 로직을 중복 구현하지 않는다.

---

### 3.2 Event-Driven Communication

컴포넌트 간 데이터 전달은 MQTT Topic을 통한 비동기 이벤트 전달을 기본으로 한다.

컴포넌트 간 직접 함수 호출이나 내부 코드 의존성을 만들지 않는다.

```text
Publisher
    │
    ▼
MQTT Broker
    │
    ▼
Subscriber
```

MQTT 사용의 목적은 Production 수준의 신뢰성 보장이 아니라 **컴포넌트 간 인터페이스를 분리하고 과제에서 요구하는 비동기 통신 구조를 구현하는 것**이다.

메시지 재전송, 중복 제거, 멱등성 처리 등의 Production 수준 메시징 전략은 구현하지 않는다.

---

### 3.3 Data Plane과 Control Plane 분리

대용량 데이터와 제어 메시지를 가능한 한 분리한다.

대표적으로 제품 이미지는 MQTT Payload에 직접 포함하지 않는다.

```text
Image

Simulator
   ↓
Image Storage
   ↓
Vision
```

MQTT에는 이미지 자체가 아니라 이미지 위치와 메타데이터만 전달한다.

```json
{
  "product_id": "P-00001024",
  "timestamp": "2026-09-09T05:20:13Z",
  "image_path": "products/P-00001024.jpg"
}
```

---

### 3.4 Ground Truth와 Runtime Data 분리

Simulator는 데이터 생성 과정에서 실제 Fault Level이나 생성한 Defect Type을 알고 있다.

그러나 이러한 값은 AI가 추론해야 할 정답이므로 AI 추론 입력으로 전달해서는 안 된다.

Ground Truth는 다음 목적으로만 사용한다.

* 모델 학습 데이터 생성
* 모델 성능 평가
* 시뮬레이터 검증
* 디버깅

---

# 4. System Components

## 4.1 Factory Simulator

### Role

Factory Simulator는 실제 제조 공정과 설비를 대신하는 가상 공장 환경이다.

본 프로젝트에서는 Three.js 기반으로 구현하며, 과제에서 필요한 최소 공장 환경을 시각적으로 표현한다.

Simulator는 공장의 실제 상태를 흉내 내고 센서 및 제품 데이터를 생성하는 역할만 담당한다.

### Responsibilities

주요 책임은 다음과 같다.

#### Factory Visualization

* Conveyor 표현
* Motor / Bearing 표현
* Product 이동 표현
* 설비 동작 상태 표현
* 설비 정지 상태 표현

#### Fault Injection

사용자가 Fault Level을 `0~10` 범위에서 변경할 수 있도록 한다.

```text
Fault Level
    │
    ├─ Vibration 증가
    │
    └─ Product Defect Probability 증가
```

Fault Level은 내부 시뮬레이션 파라미터 및 Ground Truth로 사용한다.

#### Synthetic Sensor Generation

가상 진동 센서 데이터를 생성한다.

최소 데이터:

* timestamp
* sensor_id
* vibration_x
* vibration_y
* vibration_z
* temperature
* fault_level

진동 데이터는 필요에 따라 수학적 Fault Injection을 적용한다.

예:

* Bearing Impulse
* 1X RPM Unbalance
* 2X / 3X Harmonics
* Random Noise

#### Product Generation

컨베이어 위에서 제품을 생성한다.

Fault Level에 따라 제품 불량 생성 확률을 변경할 수 있다.

지원해야 하는 대표적인 불량:

* Scratch
* Dent
* Contamination

#### Vision Dataset Generation

Vision 모델 학습을 위한 이미지 생성 시 Domain Randomization을 적용한다.

예:

* 조명
* 카메라 각도
* 제품 위치
* 제품 회전
* 배경
* 결함 위치
* 결함 크기

#### Event Publishing

생성한 설비 데이터와 제품 이벤트를 MQTT를 통해 발행한다.

---

### Out of Scope

Factory Simulator는 다음 작업을 수행하지 않는다.

* FFT 분석
* Feature Extraction
* Autoencoder 추론
* Health Index 계산
* 설비 상태 판정
* Vision AI 추론
* Grad-CAM 생성
* 생산 라인 정지 여부 판단
* 설비-품질 통계 분석

---

# 4.2 Predictive Maintenance Engine

### Role

Predictive Maintenance Engine은 진동 센서 데이터를 분석하여 설비의 상태를 추론한다.

즉,

> Raw Sensor Data를 Equipment Health Information으로 변환한다.

---

### Input

주요 입력 데이터:

```text
vibration_x
vibration_y
vibration_z
temperature
timestamp
sensor_id
```

Fault Level은 모델 추론 입력으로 사용하지 않는 것을 원칙으로 한다.

---

### Processing Pipeline

```text
Raw Vibration
      │
      ▼
Windowing
      │
      ▼
FFT
      │
      ▼
Feature Extraction
      │
      ├─ Time Domain
      │
      └─ Frequency Domain
      │
      ▼
Anomaly Detection
      │
      ├─ Control Chart
      │
      └─ Autoencoder
      │
      ▼
Anomaly Score
      │
      ▼
Health Index
      │
      ▼
Equipment State
```

---

### Feature Extraction

시간 영역 특징을 최소 5개 이상 추출한다.

예:

* Mean
* RMS
* Peak
* Crest Factor
* Kurtosis

주파수 영역 특징을 최소 3개 이상 추출한다.

예:

* Dominant Frequency
* Spectral Energy
* BPFO Amplitude
* BPFI Amplitude

---

### Equipment State

Health Index는 `0~100` 범위로 표현한다.

| Health Index | State    |
| ------------ | -------- |
| 80~100       | Normal   |
| 60~79        | Caution  |
| 40~59        | Warning  |
| 0~39         | Critical |

---

### Output

대표적인 출력 구조:

```json
{
  "timestamp": "2026-09-09T05:20:13Z",
  "sensor_id": "motor01",
  "anomaly_score": 0.82,
  "health_index": 32,
  "state": "CRITICAL"
}
```

분석 결과는 MQTT를 통해 Factory Operations & Control에 전달한다.

---

### Out of Scope

Predictive Maintenance Engine은 다음을 담당하지 않는다.

* Product Image 분석
* 제품 불량 판단
* Conveyor 직접 제어
* Dashboard UI
* Fault Level 조작

---

# 4.3 Vision Quality Inspection

### Role

Vision Quality Inspection은 Simulator가 생성한 제품 이미지를 분석하여 제품의 품질 상태를 추론한다.

즉,

> Product Image를 Quality Information으로 변환한다.

---

### Input

Vision이 전달받는 데이터는 이미지 위치 정보다.

예:

```json
{
  "product_id": "P-00001024",
  "timestamp": "2026-09-09T05:20:13Z",
  "image_path": "products/P-00001024.jpg"
}
```

---

### Processing Pipeline

```text
Product Image
      │
      ▼
Preprocessing
      │
      ▼
YOLOv8 / EfficientDet
      │
      ▼
Defect Detection
      │
      ├─ Scratch
      ├─ Dent
      └─ Contamination
      │
      ▼
Grad-CAM
      │
      ▼
Inspection Result
```

---

### Output

대표적인 Inspection Result:

```json
{
  "product_id": "P-00001024",
  "timestamp": "2026-09-09T05:20:13Z",
  "defect": true,
  "defect_type": "scratch",
  "confidence": 0.94,
  "bbox": [120, 340, 180, 400],
  "image_path": "products/P-00001024.jpg",
  "gradcam_path": "gradcam/P-00001024.jpg"
}
```

검사 결과는 MQTT를 통해 Factory Operations & Control로 전달한다.

---

### Out of Scope

Vision Quality Inspection은 다음을 담당하지 않는다.

* 진동 분석
* Health Index 계산
* Fault Level 판단
* 컨베이어 제어
* 설비 상태 결정
* 전체 불량률 관리
* 시스템 Dashboard 관리

---

# 4.4 Factory Operations & Control

### Role

Factory Operations & Control은 Smart Factory System의 중앙 운영 컴포넌트다.

PdM과 Vision에서 생성된 분석 결과를 수집하고, 공장 운영 상태를 관리하며 생산라인 제어 권한을 가진다.

주요 역할은 다음과 같다.

> Integration + Monitoring + Decision + Control

---

### Data Integration

다음 데이터를 통합한다.

#### Simulator

* 설비 상태
* 센서 데이터
* 생산 상태
* 제품 생성 이벤트

#### Predictive Maintenance

* Anomaly Score
* Health Index
* Equipment State

#### Vision Quality Inspection

* Defect Detection Result
* Defect Type
* Confidence
* BBox
* Image Reference
* Grad-CAM Reference

---

### Time Synchronization

OT 데이터와 품질 데이터를 시간 기준으로 연결한다.

모든 이벤트의 timestamp는 다음 정책을 따른다.

```text
UTC ISO 8601
```

예:

```text
2026-09-09T05:20:13.425Z
```

제품과 설비 데이터를 연결할 때 다음 식별 정보를 활용한다.

* timestamp
* sensor_id
* product_id
* production sequence

---

### Correlation Analysis

설비 진동과 제품 불량 빈도의 관계를 분석한다.

분석 가능한 방법:

* Pearson Correlation
* Spearman Correlation
* Time Lag Analysis

이 결과는 Dashboard를 통해 시각화한다.

---

### Interlock Control

설비 상태가 `CRITICAL`에 도달하면 생산라인을 자동 정지한다.

기본 제어 흐름:

```text
PdM Engine
     │
     │ Equipment State
     ▼
Operations & Control
     │
     │ state == CRITICAL
     ▼
Interlock Trigger
     │
     ▼
STOP Command
     │
     ▼
MQTT
     │
     ▼
Factory Simulator
     │
     ▼
Conveyor Stop
```

라인 정지 여부에 대한 최종 제어 권한은 Factory Operations & Control만 가진다.

---

### Alarm Management

다음 상태 변화에서 Alarm을 생성할 수 있다.

```text
NORMAL
  ↓
CAUTION
  ↓
WARNING
  ↓
CRITICAL
```

특히 다음 상태는 반드시 알람 대상으로 취급한다.

* Warning
* Critical

Alarm History는 데이터베이스에 저장한다.

---

### Dashboard

실시간 통합 관제 Dashboard를 제공한다.

최소 표시 정보:

* Conveyor Status
* Current Fault Level
* 실시간 진동 데이터
* FFT Spectrum
* Anomaly Score
* Health Index
* Equipment State
* 최근 Vision Inspection
* Defect Type
* Confidence
* Grad-CAM Result
* Defect Rate
* 설비-품질 상관관계
* Alarm History

Dashboard 데이터는 최대 5초 이내 간격으로 갱신한다.

---

### Data Persistence

Factory Operations & Control은 Shared Infrastructure 데이터베이스의 테이블 스키마(DDL)를 소유하고, 데이터베이스에 기록하는 유일한 Component다.

* Time-Series DB(5.2절)와 Relational DB(5.3절)의 테이블 정의
* 센서 데이터의 Time-Series DB 적재: Simulator가 발행한 진동 이벤트를 MQTT로 구독하여 기록한다
* Relational DB 기록: Inspection History, Defect Result, Alarm History, Equipment State History, Control History를 MQTT로 수신한 결과와 자신의 판단으로부터 기록한다. `health_index_at_time`처럼 PdM과 Vision 결과를 결합한 필드도 여기서 채운다

다른 Component는 데이터베이스에 접근하지 않고 결과를 MQTT로만 발행한다.

---

# 5. Shared Infrastructure

4개 핵심 컴포넌트는 다음 공통 인프라를 공유한다.

```text
Shared Infrastructure
│
├─ MQTT Broker
├─ TimescaleDB
├─ PostgreSQL
└─ Image Storage
```

---

## 5.1 MQTT Broker

MQTT는 컴포넌트 간 비동기 메시지 전달의 중심 역할을 한다.

권장 구현:

```text
Eclipse Mosquitto
```

대표적인 Topic 구조:

```text
factory/
│
├─ sensor/
│   └─ motor01/
│       └─ vibration
│
├─ product/
│   └─ created
│
├─ pdm/
│   └─ result
│
├─ vision/
│   └─ result
│
├─ alarm/
│   └─ event
│
└─ control/
    └─ conveyor
```

정확한 Topic 명세와 Payload Schema는 별도 Interface 문서(`docs/INTERFACES.md`)에 정의한다.

본 프로젝트에서는 MQTT 메시지의 멱등성, 중복 처리, 재전송 보장, 장애 복구 전략은 별도로 구현하지 않는다.

---

## 5.2 Time-Series Database

센서 시계열 데이터 저장에 사용한다.

권장:

```text
TimescaleDB
```

최소 데이터 구조:

```text
timestamp
sensor_id
vibration_x
vibration_y
vibration_z
temperature
fault_level
```

Factory Operations & Control이 센서 이벤트를 MQTT로 구독하여 적재하며, 테이블 스키마(DDL)를 소유한다 (4.4절 Data Persistence).

Production 수준의 Replication, Failover, Backup 전략은 고려하지 않는다.

---

## 5.3 Relational Database

품질 검사와 운영 데이터를 저장한다.

권장:

```text
PostgreSQL
```

주요 데이터:

* Inspection History
* Defect Result
* Alarm History
* Equipment State History
* Control History

Vision Inspection 최소 필드:

```text
id
timestamp
product_id
image_path
defect_type
confidence
bbox
health_index_at_time
```

Factory Operations & Control만 기록하며 테이블 스키마(DDL)를 소유한다 (4.4절 Data Persistence).

Production 수준의 데이터 복구 및 백업 정책은 구현하지 않는다.

---

## 5.4 Image Storage

다음 이미지 데이터를 저장한다.

```text
Product Image
Vision Training Dataset
Inspection Image
Grad-CAM Result
```

개발 환경에서는 Docker Volume 기반 Shared Storage를 사용할 수 있다.

예:

```text
/data/
├─ products/
├─ training/
├─ gradcam/
└─ evaluation/
```

이미지 자체를 MQTT Message에 포함하지 않는다.

MQTT에서는 이미지 경로 또는 참조 정보만 전달한다.

경로 표기와 파일 기록 완료 보장은 `docs/INTERFACES.md`의 Image Reference 규칙을 따른다.

별도의 파일 이중화, 원격 백업 및 Object Storage 가용성 구성은 고려하지 않는다.

---

# 6. Overall Data Flow

전체 Runtime 데이터 흐름은 다음과 같다.

```text
                       ┌────────────────────┐
                       │ Factory Simulator  │
                       │                    │
                       │ Three.js           │
                       │ Fault Injection    │
                       │ Product Generation │
                       │ Sensor Generation  │
                       └───────┬─────┬──────┘
                               │     │
                      Sensor   │     │ Product
                       Data    │     │ Image/Event
                               │     │
                               ▼     ▼
                         ┌───────────────┐
                         │  MQTT Broker  │
                         └─────┬───┬─────┘
                               │   │
                     Vibration │   │ Product Event
                               │   │
                               ▼   ▼
                     ┌───────────┐ ┌───────────────┐
                     │ PdM       │ │ Vision Quality│
                     │ Engine    │ │ Inspection    │
                     └─────┬─────┘ └───────┬───────┘
                           │               │
                    Health │               │ Inspection
                    Result │               │ Result
                           │               │
                           └───────┬───────┘
                                   ▼
                         ┌─────────────────────┐
                         │ Factory Operations  │
                         │ & Control           │
                         │                     │
                         │ Integration         │
                         │ Monitoring          │
                         │ Correlation         │
                         │ Alarm               │
                         │ Interlock           │
                         └──────────┬──────────┘
                                    │
                              Control Command
                                    │
                                    ▼
                               MQTT Broker
                                    │
                                    ▼
                         ┌────────────────────┐
                         │ Factory Simulator  │
                         │                    │
                         │ Conveyor Control   │
                         └────────────────────┘
```

---

# 7. 주요 데이터 흐름

## 7.1 Sensor Data Flow

```text
Simulator
   ↓
Vibration Event
   ↓
MQTT
   ├─→ Operations ─→ Time-Series DB
   └─→ PdM Engine
             ↓
       Health Analysis
             ↓
           MQTT
             ↓
       Operations
```

---

## 7.2 Vision Inspection Flow

```text
Simulator
     │
     ├─→ Image Storage
     │
     └─→ Product Created Event
                ↓
              MQTT
                ↓
              Vision
                ↓
          Image Retrieval
                ↓
             Inference
                ↓
            Grad-CAM
                ↓
     Vision Inspection Event
                ↓
              MQTT
                ↓
            Operations
```

---

## 7.3 Production Control Flow

```text
PdM Engine
    ↓
Equipment State
    ↓
MQTT
    ↓
Operations
    ↓
Critical State Detection
    ↓
Interlock
    ↓
STOP Command
    ↓
MQTT
    ↓
Simulator
    ↓
Conveyor Stop
```

---

# 8. Ground Truth Policy

Simulator는 데이터 생성 과정에서 실제 정답을 가지고 있다.

예:

```text
Fault Level = 7
Generated Defect = Scratch
```

하지만 Runtime AI 입력에는 이러한 Ground Truth를 전달하지 않는다.

---

## Vision

금지:

```json
{
  "product_id": "P-00000100",
  "image_path": "products/P-00000100.jpg",
  "defect_type": "scratch"
}
```

Inference 입력:

```json
{
  "product_id": "P-00000100",
  "image_path": "products/P-00000100.jpg"
}
```

Ground Truth는 Evaluation Dataset에서 별도로 관리한다.

---

## Predictive Maintenance

PdM 모델은 Fault Level을 직접 이용하여 Health Index를 산출해서는 안 된다.

기본적으로 다음 센서 데이터를 통해 상태를 추론한다.

```text
vibration_x
vibration_y
vibration_z
temperature
```

Fault Level은 다음 용도로 제한한다.

* Simulator Control
* Ground Truth
* Training Label
* Evaluation
* Debugging

---

# 9. Timestamp Policy

모든 컴포넌트는 동일한 시간 정책을 사용한다.

표준:

```text
UTC
ISO 8601
```

예:

```text
2026-09-09T05:20:13.425Z
```

로컬 시스템 시간이 아닌 이벤트 발생 시각을 기준으로 기록한다.

OT Sensor 데이터와 Vision 데이터의 결합에서도 해당 timestamp를 사용한다.

---

# 10. Component Dependency Rules

컴포넌트 사이에 직접 코드 Dependency를 만들지 않는다.

잘못된 구조:

```text
Simulator
   ↓
visionService.detect()
```

또는:

```text
Operations
   ↓
pdm.calculateHealth()
```

권장 구조:

```text
Simulator
   ↓
MQTT
   ↓
Vision
```

```text
PdM
 ↓
MQTT
 ↓
Operations
```

컴포넌트 간 공유되어야 하는 것은 코드가 아니라 **Interface Contract**다.

공통으로 관리해야 할 계약:

* MQTT Topic
* JSON Schema
* Timestamp Policy
* ID Policy

---

# 11. ID Policy

데이터 연결을 위해 최소한 다음 ID를 명시적으로 사용한다.

### sensor_id

설비 또는 센서를 식별한다.

예:

```text
motor01
```

### product_id

생산된 개별 제품을 식별한다.

예:

```text
P-00001024
```

모든 Vision 결과는 가능한 한 `product_id`를 포함한다.

---

# 12. Non-Production Constraints

본 시스템은 데모 및 과제 검증 환경에서 정상적인 Happy Path를 중심으로 구현한다.

따라서 각 컴포넌트는 정상적인 통신 및 실행을 전제로 하며, 다음과 같은 장애 상황을 위한 별도의 설계는 요구하지 않는다.

```text
MQTT Broker 장애
Database 장애
AI Component 장애
Network 단절
Message 중복
Message 유실
Process Crash
Storage 손실
```

이러한 상황에 대한:

* 자동 Retry
* 재처리 Queue
* Dead Letter Queue
* Transactional Messaging
* Idempotency Key
* Circuit Breaker
* 자동 Restart
* Failover
* Backup / Restore

등은 구현하지 않는다.

개발 과정에서 필요한 최소 수준의 오류 로그 및 예외 처리는 적용할 수 있으나, Production 수준의 복구 체계를 구축하는 것을 목표로 하지 않는다.

---

# 13. Security Policy

본 프로젝트는 로컬 개발 및 데모 환경을 전제로 한다.

따라서 Production 수준의 보안 요구사항은 구현 범위에서 제외한다.

다음 항목은 별도로 구현하지 않는다.

* 사용자 인증
* API 인증/인가
* MQTT Client 인증
* TLS 통신
* Database 접근 제어 고도화
* 데이터 암호화
* Secret Vault
* Network Segmentation
* Security Monitoring

단, 비밀번호나 연결 정보 등 환경에 따라 변경되는 값은 코드에 직접 하드코딩하지 않고 설정 파일 또는 환경 변수로 분리한다.

---

# 14. Configuration Policy

다음 값은 코드에 하드코딩하지 않는다.

* IP
* Hostname
* Port
* MQTT Broker URL
* Database URL
* Image Directory
* Model Path
* Sampling Rate
* FFT Window Size
* Fault Parameters
* Threshold
* Topic Name

환경 변수 또는 설정 파일을 사용한다.

예:

```text
.env
config.yaml
```

이는 Production 수준의 Secret Management 목적이 아니라 **컴포넌트 간 환경 설정을 분리하고 개발 편의성을 확보하기 위한 것**이다.

---

# 15. Simulator Replacement Principle

Factory Simulator는 실제 공장 환경을 대체하는 Adapter 역할을 한다.

현재 구조:

```text
Three.js Simulator
       ↓
      MQTT
```

Simulator의 내부 구현이 다른 컴포넌트에 직접 노출되지 않도록 인터페이스를 분리한다.

이는 실제 Production 설비로의 전환을 이번 프로젝트에서 구현하기 위한 것이 아니라, 각 컴포넌트의 책임 경계를 명확히 유지하기 위한 설계 원칙이다.

---

# 16. Implementation Note — Simulator

본 프로젝트의 원 요구사항에서는 Gazebo 또는 NVIDIA Isaac Sim 사용을 요구하지만, 본 프로젝트에서는 과제 출제자의 승인을 받아 Three.js 기반 Custom Simulator를 사용한다.

Three.js Simulator는 전체 제조 공정의 물리적 정확성을 재현하는 것이 목적이 아니다.

다음 프로젝트 요구사항을 충족하는 최소 공장 환경을 제공하는 것을 목표로 한다.

* Conveyor Visualization
* Product Movement
* Fault Level Control
* Synthetic Vibration Generation
* Product Defect Generation
* Domain Randomization
* Image Generation
* MQTT Communication
* Conveyor Start / Stop Control

베어링 진동 데이터는 필요에 따라 Python 기반 Mathematical Fault Injection을 통해 생성한다.

---

# 17. Responsibility Summary

| 영역                     | Factory Simulator | PdM Engine   | Vision Inspection | Operations & Control |
| ---------------------- | ----------------- | ------------ | ----------------- | -------------------- |
| Factory Visualization  | O                 | X            | X                 | Dashboard Only       |
| Fault Injection        | O                 | X            | X                 | X                    |
| Sensor Generation      | O                 | X            | X                 | X                    |
| Product Generation     | O                 | X            | X                 | X                    |
| FFT                    | X                 | O            | X                 | X                    |
| Feature Extraction     | X                 | O            | X                 | X                    |
| Autoencoder            | X                 | O            | X                 | X                    |
| Health Index           | X                 | O            | X                 | Consume              |
| Defect Detection       | X                 | X            | O                 | Consume              |
| Grad-CAM               | X                 | X            | O                 | Consume              |
| Correlation Analysis   | X                 | X            | X                 | O                    |
| Alarm Management       | X                 | State Event  | X                 | O                    |
| Conveyor Stop Decision | X                 | X            | X                 | O                    |
| Conveyor Physical Stop | O                 | X            | X                 | Command              |
| Dashboard              | X                 | X            | X                 | O                    |
| Time Synchronization   | Timestamp 생성      | Timestamp 유지 | Timestamp 유지      | O                    |
| Ground Truth 생성        | O                 | X            | X                 | Evaluation Only      |
| DB Schema (DDL)        | X                 | X            | X                 | O                    |
| Time-Series DB 적재      | X                 | X            | X                 | O                    |
| Relational DB 기록       | X                 | X            | X                 | O                    |

---

# 18. Final Architecture Definition

전체 시스템은 다음 원칙으로 요약한다.

```text
Factory Simulator
= Reality & Data Generation

Predictive Maintenance Engine
= Equipment Intelligence

Vision Quality Inspection
= Quality Intelligence

Factory Operations & Control
= Integration, Monitoring & Control

Shared Infrastructure
= Communication, Storage & Persistence
```

각 컴포넌트는 자신의 책임 영역만 담당하며, MQTT 기반 Interface Contract를 통해 서로 통신한다.

본 프로젝트의 목표는 Production 수준의 Smart Factory Platform을 구축하는 것이 아니라, 다음 핵심 흐름을 명확하게 구현하고 검증하는 것이다.

```text
Fault Injection
      ↓
Sensor / Product Data Generation
      ↓
PdM & Vision AI Analysis
      ↓
Operations Integration
      ↓
Monitoring / Alarm / Interlock
```

따라서 **성능 최적화, 장애 복구, 멱등성, 보안, 백업 등의 Production Engineering은 의도적으로 범위에서 제외하고**, 과제에서 요구하는 기능적 요구사항과 AI 분석 과정의 정확한 구현에 집중한다.

---

# 19. Repository & Governance

아키텍처 컴포넌트와 저장소의 대응, 계약 운영 정보다. `미정` 항목은 첫 운영 Issue를 게시해 초기화 기간을 끝내기 전에 채운다.

| 아키텍처 컴포넌트 | Component 이름 (`SHARED_CONFIG.json`) | 아키텍처 절 | 소유자 |
|---|---|---|---|
| Factory Simulator | `factory-simulator` | 4.1, 16 | 미정 |
| Predictive Maintenance Engine | `predictive-maintenance` | 4.2 | 미정 |
| Vision Quality Inspection | `vision-inspection` | 4.3 | 미정 |
| Factory Operations & Control | `factory-operations` | 4.4 | 미정 |
| (Runtime 컴포넌트 아님) Integration | `integration` | 19.1 | 미정 |

- 공용 계약 저장소: 이 저장소. 계약 문서는 `docs/ARCHITECTURE.md`, `docs/INTERFACES.md`, `docs/CONVENTIONS.md`이다.
- 계약 변경 승인 책임자: 미정 (`.github/CODEOWNERS`에도 같은 책임자를 지정)
- 통합·릴리스 조건: 2절의 성능 기준 측정 결과와 7절 주요 데이터 흐름의 End-to-End 동작을 `integration`이 고정된 Component 조합에서 확인한다. 세부 조건은 미정.
- 복구 방법: 마지막으로 검증된 Component commit 조합과 계약 commit으로 되돌린다.

## 19.1 Integration

`integration`은 Shared Infrastructure 실행 정의와 Component 조합 검증을 맡는 저장소다. Runtime 데이터 흐름(6, 7절)에 참여하지 않으므로 1절의 4개 핵심 컴포넌트에 포함하지 않는다.

Factory Operations & Control의 Integration(4.4절)은 Runtime 데이터 통합이고, 이 절의 Integration은 저장소 조합·호환성 검증이다. 두 책임을 한 저장소에 두지 않는다. 검증 대상이 자신의 조합을 판정하지 않도록 하고, 구현 변경과 조합 검증 변경이 한 task에 섞이지 않게 하기 위해서다. 같은 사람이 두 저장소의 소유자를 맡는 것은 허용한다.

담당:

* Shared Infrastructure(5절) 실행 정의: MQTT Broker, TimescaleDB, PostgreSQL, Image Storage 볼륨의 구성 파일과 설정 예시. DB 초기화에는 `COMPOSITION.json`에 고정한 `factory-operations` commit의 DDL을 사용한다
* 검증 조합 고정(`COMPOSITION.json`)과 검증 기록(`VALIDATION.md`)
* 7절 주요 데이터 흐름의 End-to-End 시나리오 검증
* Interface 준수 검사: Payload Schema, ID 형식(`docs/CONVENTIONS.md`), AI 추론 입력의 Ground Truth 미포함(8절)
* 시스템 수준 성능 측정: Dashboard 5초 이내 갱신, 통합 환경에서의 Vision FPS와 PdM Inference 시간(2절)
* 교차 Component 문제의 관찰·재현 근거 기록과 Shared MESSAGE 게시

담당하지 않음:

* 모델 지표(mAP@0.5, F1-Score) 산출. 평가 데이터셋을 가진 각 Component가 측정하고 `integration`은 결과를 수집한다
* 다른 Component의 구현 수정과 Runtime 로직
* 계약 결정 (계약 변경 승인 책임자가 결정한다)
* DB 테이블 스키마(DDL) 작성과 데이터베이스 기록 (Factory Operations & Control 소유, 4.4절 Data Persistence)

Integration은 다른 Component와 동일한 원격 조회·로컬 처리 기록 방식을 사용한다. 통합 검증은 각 Component의 commit 또는 이미지 digest와 계약 기준을 고정한 조합을 대상으로 한다. 개별 Issue 처리 여부만으로 전체 호환성을 선언하지 않는다.
