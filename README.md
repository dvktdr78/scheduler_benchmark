# 스케줄러 벤치마크 시스템

3가지 CPU 스케줄러(Basic Priority, MLFQS, CFS)를 목표 기반 테스트로 비교 분석하는 벤치마크 시스템입니다.

## 📋 목차

- [개요](#개요)
- [아키텍처](#아키텍처)
- [설치 및 실행](#설치-및-실행)
- [스케줄러 상세](#스케줄러-상세)
- [테스트 카테고리](#테스트-카테고리)
- [워크로드](#워크로드)
- [파일 구조](#파일-구조)
- [주요 발견사항](#주요-발견사항)
- [설계 결정사항](#설계-결정사항)

## 개요

### 프로젝트 목적

실제 운영체제에서 사용되는 3가지 CPU 스케줄링 알고리즘을 공정하게 비교하고, 각각의 장단점을 정량적으로 측정합니다.

### 주요 특징

- ✅ **목표 기반 테스트**: 스케줄러에 중립적인 목표로 테스트 정의
- ✅ **선택적 비교**: 각 테스트마다 의미있는 스케줄러 조합만 비교
- ✅ **실시간 시각화**: Streamlit 웹 UI로 즉시 결과 확인
- ✅ **검증된 구현**: 각 스케줄러는 실제 OS 구현을 기반으로 검증됨

### 비교 대상 스케줄러

1. **Basic Priority** - 정적 우선순위 스케줄러 (Baseline)
2. **MLFQS (64-Queue)** - 동적 우선순위, O(1) 스케줄링
3. **CFS** - Linux 커널의 공정성 스케줄러

## 아키텍처

### 목표 기반 테스트 설계

기존의 "모든 테스트에서 3개 스케줄러를 항상 비교" 방식 대신, **각 테스트의 목표에 맞는 스케줄러만 선택적으로 비교**합니다.

#### 설계 원칙

1. **테스트는 "목표"로 정의** (scheduler-neutral)
   - 예: "Interactive 응답성", "공정한 CPU 배분", "Nice 효과 측정"

2. **각 테스트마다 적절한 스케줄러만 비교**
   - 일반 워크로드: Basic + MLFQS + CFS (3-way)
   - 공정성 테스트: MLFQS + CFS만 (Basic은 starvation 위험)
   - Nice 효과: MLFQS + CFS만 (Basic의 nice는 정적 우선순위)

3. **각 스케줄러가 자신의 방식으로 목표 달성**
   - Basic: 정적 우선순위
   - MLFQS: 동적 우선순위 조정
   - CFS: 공정한 CPU 시간 배분

### 시스템 구성

```
┌─────────────────────────────────────────────┐
│           Streamlit Web UI (app.py)         │
│  - 테스트 선택 (카테고리별)                       │
│  - 실시간 진행상황 표시                          │
│  - 결과 시각화 (그래프, 메트릭)                   │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│     Benchmark Tests (benchmark/tests.py)    │
│  - 13개 테스트 정의                            │
│  - 5개 카테고리 분류                            │
│  - 스케줄러 조합 명시                           │
└─────────────────┬───────────────────────────┘
                  │
         ┌────────┴────────┐
         │                 │
┌────────▼──────┐  ┌──────▼─────────┐
│  Workload     │  │   Simulator    │
│  Generator    │  │  (simulator/   │
│ (workload/)   │  │   simulator.py)│
│               │  │                │
│ - 8가지 패턴    │  │ - Time slice   │
│ - Seed 고정    │  │ - Context SW   │
└───────────────┘  │ - I/O 처리      │
                   └────────┬────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
┌────────▼──────┐  ┌────────▼──────┐  ┌───────▼───────┐
│ Basic         │  │    MLFQS      │  │     CFS       │
│ Priority      │  │  (64-Queue)   │  │ (vruntime)    │
│ (scheduler/   │  │  (scheduler/  │  │ (scheduler/   │
│  basic_*.py)  │  │   mlfqs.py)   │  │   cfs.py)     │
└───────────────┘  └───────────────┘  └───────────────┘
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
                   ┌────────▼────────┐
                   │   Analysis      │
                   │  (analysis/     │
                   │   insights.py)  │
                   │                 │
                   │ - Metrics 계산   │
                   │ - 승자 결정       │
                   │ - Insight 생성   │
                   └─────────────────┘
```

## 설치 및 실행

### 요구사항

- Python 3.8 이상
- Linux 환경 권장 (Ubuntu 20.04+)

### 설치

```bash
# 저장소 클론
git clone https://github.com/dvktdr78/scheduler_benchmark.git
cd scheduler-benchmark/python_webapp

# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 실행

```bash
# 가상환경 활성화 (필요시)
source venv/bin/activate

# Streamlit 앱 실행
streamlit run app.py
```

웹 브라우저에서 `http://34.47.105.226/:8501` 접속

### 빠른 실행 스크립트

```bash
# 프로젝트 루트에서
./run.sh
```

## 스케줄러 상세

### Nice 값 한눈에 보기
- 개념: 사용자가 주는 “양보도” 힌트. 낮을수록 우선순위 ↑, 높을수록 우선순위 ↓ (반비례).
- 범위: -20(가장 높은 우선순위) ~ +19(가장 낮은 우선순위), 기본 0.
- 적용 방식: Basic은 `priority = 31 - nice`로 정적 변환, MLFQS는 `priority = PRI_MAX - (recent_cpu/4) - 2*nice`에 반영, CFS는 가중치 테이블로 변환해 CPU 시간 비율을 조정.

### 1. Basic Priority Scheduler

**개요**: 정적 우선순위 기반 선점형 스케줄러 (Baseline)

**핵심 알고리즘**:
- Nice 값을 정적 우선순위로 변환: `priority = PRI_DEFAULT(31) - nice`
- 우선순위 범위: 0-63 (63이 최고 우선순위)
- 같은 우선순위 내에서 FIFO 방식

**구현 특징**:
- Round-robin 방식 (time slice = 4 ticks)
- Preemptive (높은 우선순위 스레드가 도착하면 선점)
- Aging 미지원 (starvation 위험 존재)

**장점**:
- 단순하고 예측 가능
- 오버헤드 최소
- 실시간 시스템에 적합

**단점**:
- Starvation 위험 (낮은 우선순위 스레드)
- 동적 조정 불가
- I/O bound 스레드에 불리

**코드 위치**: [scheduler/basic_priority.py](python_webapp/scheduler/basic_priority.py)

### 2. MLFQS (Multi-Level Feedback Queue Scheduler)

**개요**: 64개 독립 큐를 사용하는 동적 우선순위 스케줄러 (FreeBSD 방식)

**핵심 알고리즘**:
```
priority = PRI_MAX - (recent_cpu / 4) - (nice * 2)

recent_cpu = (2 * load_avg) / (2 * load_avg + 1) * recent_cpu + nice

load_avg = (59/60) * load_avg + (1/60) * ready_threads
```

**구현 특징**:
- 64개 독립 큐 (우선순위 0-63)
- O(1) pick_next (기존 O(n) → O(64) = O(1))
- O(1) thread_yield (기존 O(n log n) → O(1))
- 17.14 고정소수점 연산 (F = 1 << 14 = 16384)

**업데이트 주기**:
- `recent_cpu++`: 매 tick (실행 중인 스레드만)
- `priority 재계산`: 4 ticks마다
- `load_avg, recent_cpu 재계산`: 100 ticks마다

**장점**:
- I/O bound 스레드 자동 우대
- Starvation 방지 (recent_cpu가 시간에 따라 감소)
- 동적 부하 조정

**단점**:
- Nice 효과가 약함 (nice는 priority에 -2배만 기여)
- 복잡한 계산 (고정소수점)
- 공정성이 CFS보다 낮음

**코드 위치**:
- [scheduler/mlfqs.py](python_webapp/scheduler/mlfqs.py)
- [scheduler/fixed_point.py](python_webapp/scheduler/fixed_point.py)

### 3. CFS (Completely Fair Scheduler)

**개요**: Linux 커널의 공정성 스케줄러 (vruntime 기반)

**핵심 알고리즘**:
```
delta_vruntime = delta * (NICE_0_WEIGHT / weight)
weight = PRIO_TO_WEIGHT[nice + 20]

최소 vruntime 스레드를 선택 (Red-Black Tree 대신 SortedList 사용)
```

**구현 특징**:
- Linux 커널 가중치 테이블 100% 동일 사용
- vruntime으로 자동 정렬 (SortedList)
- 1000배 스케일 증가로 정밀도 향상 (`(delta * 1024 * 1000) // weight`)

**가중치 테이블 예시**:
- nice -20 → weight 88761 (최고 우선순위)
- nice 0 → weight 1024 (기본)
- nice 19 → weight 15 (최저 우선순위)

**이론적 CPU 시간 비율**:
- nice -20 vs nice 19: 88761 / 15 ≈ 5917:1

**장점**:
- 완벽한 공정성 (Jain Index > 0.95)
- Nice 효과가 강함 (가중치 기반)
- Starvation 완전 방지

**단점**:
- I/O bound 스레드에 특별한 우대 없음
- 약간의 오버헤드 (SortedList 관리)

**코드 위치**: [scheduler/cfs.py](python_webapp/scheduler/cfs.py)

## 테스트 카테고리

총 **13개 테스트**, **5개 카테고리**로 구성

### 1. 일반 워크로드 (3개 테스트, 3-way 비교)

**목적**: 다양한 일반적인 워크로드 패턴 비교

| 테스트 | 워크로드 | 주요 메트릭 | 비교 대상 |
|--------|---------|------------|-----------|
| 일반 혼합 워크로드 | mixed | avg_wait | Basic + MLFQS + CFS |
| CPU 집약적 워크로드 | cpu_bound | avg_turnaround | Basic + MLFQS + CFS |
| I/O 집약적 워크로드 | io_bound | avg_wait | Basic + MLFQS + CFS |

**특징**:
- Nice 값은 0 또는 약한 차이 (-5~5)로 설정
- 순수 스케줄링 알고리즘 효율성 비교

### 2. 실제 응용 (4개 테스트, 3-way 비교)

**목적**: 실제 시스템 패턴 시뮬레이션

| 테스트 | 워크로드 | 패턴 | 비교 대상 |
|--------|---------|------|-----------|
| 웹 서버 패턴 | web_server | 90% 짧은 요청 + 10% 긴 요청 | Basic + MLFQS + CFS |
| 데이터베이스 패턴 | database | 70% SELECT + 30% 트랜잭션 | Basic + MLFQS + CFS |
| 배치 처리 패턴 | batch | CPU-heavy, 순차 도착 | Basic + MLFQS + CFS |
| 게임/실시간 패턴 | gaming | 30% 렌더링 + 70% AI | Basic + MLFQS + CFS |

**특징**:
- 실제 애플리케이션 동작 모방
- Nice 0으로 통일 (애플리케이션 스레드는 보통 동일 우선순위)

### 3. 공정성 (2개 테스트, MLFQS vs CFS)

**목적**: CPU 시간 배분의 공정성 측정

| 테스트 | 워크로드 | 주요 메트릭 | 비교 대상 |
|--------|---------|------------|-----------|
| 공정성: CPU 시간 배분 | cpu_bound | fairness | MLFQS + CFS |
| 공정성: 혼합 워크로드 | mixed | fairness | MLFQS + CFS |

**왜 Basic을 제외하는가?**
- Basic Priority는 정적 우선순위 기반으로 starvation 위험 존재
- 공정성 측정에 부적합 (애초에 공정성을 목표로 하지 않음)

**메트릭**: Jain's Fairness Index (1.0에 가까울수록 공정)

### 4. Nice 효과 (1개 테스트, MLFQS vs CFS)

**목적**: Nice 값의 실제 효과 검증

| 테스트 | 워크로드 | 주요 메트릭 | 비교 대상 |
|--------|---------|------------|-----------|
| Nice 값 효과 검증 | extreme_nice | cpu_time_ratio | MLFQS + CFS |

**왜 Basic을 제외하는가?**
- Basic의 nice는 정적 우선순위로 변환 (다른 의미)
- MLFQS/CFS는 nice로 CPU 시간 비율 조정 (가중치 기반)

**테스트 방법**:
- 절반: nice -20 (최고 우선순위)
- 절반: nice 19 (최저 우선순위)
- burst_time = 10,000 ticks (충분히 긴 시간)
- **50% 시간에 중단** (일부만 완료하여 CPU 시간 비율 측정)

**메트릭**: CPU 시간 비율 (nice -20 그룹 / nice 19 그룹)

**측정 결과**:
- MLFQS: 약 62,499:1 (nice 효과 매우 강함)
- CFS: 약 2,499:1 (이론값 5917:1의 42%)

### 5. 확장성 (3개 테스트, 3-way 비교)

**목적**: 스레드 수에 따른 성능 변화

| 테스트 | 스레드 수 | 주요 메트릭 | 비교 대상 |
|--------|----------|------------|-----------|
| 확장성: 10 스레드 | 10 | context_switches | Basic + MLFQS + CFS |
| 확장성: 100 스레드 | 100 | avg_wait | Basic + MLFQS + CFS |
| 확장성: 500 스레드 | 500 | avg_wait | Basic + MLFQS + CFS |

**목표**: 스케일링 능력 및 오버헤드 측정

## 워크로드

### 기본 워크로드 (3개)

#### 1. Mixed (혼합)
- CPU burst: 100-500 ticks
- I/O: 다양 (빈도 0-500, 지속 0-200)
- Nice: -5 ~ 5
- 용도: 일반적인 멀티태스킹 환경

#### 2. CPU-bound (CPU 집약)
- CPU burst: 300-800 ticks
- I/O: 없음
- Nice: 0
- 용도: 과학 계산, 컴파일

#### 3. I/O-bound (I/O 집약)
- CPU burst: 50-200 ticks (짧음)
- I/O: 잦음 (빈도 50-200, 지속 50-150)
- Nice: 0
- 용도: Interactive 애플리케이션, 에디터

### 실제 응용 워크로드 (5개)

#### 4. Web Server (웹 서버)
- 90% 짧은 요청: 10-50 ticks
- 10% 긴 요청: 200-600 ticks
- Nice: 0
- 모방: Nginx, Apache

#### 5. Database (데이터베이스)
- 70% SELECT 쿼리: 30-150 ticks
- 30% 트랜잭션: 200-600 ticks
- Nice: 0
- 모방: PostgreSQL, MySQL

#### 6. Batch Processing (배치 처리)
- CPU burst: 400-800 ticks
- 순차 도착 (i * 10 ticks)
- Nice: 0
- 모방: 대용량 데이터 처리, 빌드 시스템

#### 7. Gaming (게임/실시간)
- 30% 렌더링: 50-150 ticks, 16ms 간격 도착
- 70% AI/물리: 200-500 ticks
- Nice: 0
- 목표: 60 FPS 유지

#### 8. Extreme Nice (Nice 극단 테스트)
- 절반: nice -20, burst_time 10,000
- 절반: nice 19, burst_time 10,000
- I/O: 없음
- 용도: Nice 효과 검증

**코드 위치**: [workload/generator.py](python_webapp/workload/generator.py)

## 파일 구조

```
standalone_scheduler/
├── python_webapp/
│   ├── app.py                      # Streamlit 메인 UI
│   ├── requirements.txt            # Python 의존성
│   │
│   ├── scheduler/                  # 스케줄러 구현
│   │   ├── thread.py               # Thread 데이터 클래스
│   │   ├── basic_priority.py       # Basic Priority 스케줄러
│   │   ├── mlfqs.py                # MLFQS 스케줄러
│   │   ├── cfs.py                  # CFS 스케줄러
│   │   └── fixed_point.py          # 17.14 고정소수점 연산
│   │
│   ├── workload/                   # 워크로드 생성
│   │   └── generator.py            # 8가지 워크로드 생성기
│   │
│   ├── simulator/                  # 시뮬레이션 엔진
│   │   └── simulator.py            # 단일 CPU 시뮬레이터
│   │
│   ├── analysis/                   # 분석 도구
│   │   └── insights.py             # 메트릭 계산 및 Insight 생성
│   │
│   └── benchmark/                  # 벤치마크 정의
│       └── tests.py                # 13개 테스트 정의
│
├── run.sh                          # 빠른 실행 스크립트
└── README.md                       # 이 파일
```

## 주요 발견사항

### 버그 수정 과정에서 발견한 6가지 주요 이슈

#### 1. Time Slice 미구현 (초기)
**증상**: 결과가 즉시 나오고 모든 메트릭이 동일 (tie)

**원인**: 스레드가 완료될 때까지 계속 실행 (선점 없음)

**해결**:
- Simulator에 `time_slice=4` 추가
- `current_slice_remaining` 추적
- Time slice 만료 시 `thread_yield()` 호출

**위치**: [simulator/simulator.py:94-137](python_webapp/simulator/simulator.py#L94-L137)

#### 2. Basic Priority FIFO 버그
**증상**: Basic이 거의 항상 승리

**원인**: `max(key=lambda t: (t.priority, -t.tid))`가 항상 최소 TID 선택 (FIFO가 아님)

**해결**:
```python
# 최고 우선순위 찾기
max_priority = max(t.priority for t in self.ready_queue)

# 같은 우선순위 중 첫 번째 스레드 선택 (진짜 FIFO)
for thread in self.ready_queue:
    if thread.priority == max_priority:
        self.ready_queue.remove(thread)
        return thread
```

**위치**: [scheduler/basic_priority.py:41-67](python_webapp/scheduler/basic_priority.py#L41-L67)

#### 3. MLFQS Nice 덮어쓰기 버그
**증상**: MLFQS에서 모든 스레드의 nice가 0이 됨

**원인**: `add_thread()`에서 `thread.nice = 0` 실행

**해결**: 해당 라인 제거, 워크로드에서 설정한 nice 값 유지

**위치**: [scheduler/mlfqs.py:99-109](python_webapp/scheduler/mlfqs.py#L99-L109)

#### 4. CFS vruntime 정밀도 문제 (Critical!)
**증상**: CFS vruntime이 항상 0

**원인**: 정수 나눗셈 `(delta * 1024) // weight`에서 weight=88761일 때 결과가 0

**분석**:
```
delta = 1
1024 / 88761 = 0.0115... → 정수 나눗셈으로 0
```

**해결**: 1000배 스케일 증가
```python
return (delta * 1024 * 1000) // weight
# nice -20 (weight 88761): delta_vruntime = 11
# nice 19 (weight 15): delta_vruntime = 68266
```

**위치**: [scheduler/cfs.py:52-64](python_webapp/scheduler/cfs.py#L52-L64)

#### 5. Nice 효과 측정 불가 문제
**증상**: CPU 시간 비율이 1:1로 나옴 (예상: 수천:1)

**원인**: 모든 스레드가 완료 → 각자 정확히 burst_time만큼 CPU 사용 → 비율 1:1

**해결**:
1. `extreme_nice` 워크로드의 burst_time: 300 → 10,000 (충분히 긴 시간)
2. Nice 효과 테스트만 **50% 시간에 시뮬레이션 중단** (일부만 완료)

```python
if selected_test.test_id == "nice_effect":
    total_work = sum(t.burst_time for t in base_threads)
    actual_max_ticks = int(total_work * 0.5)  # 50% 시간만 실행
```

**결과**:
- MLFQS: 62,499:1 (매우 강한 nice 효과)
- CFS: 2,499:1 (이론값 5917:1의 42%)

**위치**:
- [workload/generator.py:296-338](python_webapp/workload/generator.py#L296-L338)
- [app.py:122-133](python_webapp/app.py#L122-L133)

#### 6. 컨텍스트 스위치 수 측정 불가 (확장성 테스트 무효화)
**증상**: 확장성 테스트의 주요 메트릭 `context_switches`가 항상 0으로 나와 개선율이 0% 고정

**원인**:
- 컨텍스트 스위치 카운트가 스레드에 전달되지 않음
- 마지막 실행 스레드 ID를 추적하지 않아 카운트가 누락

**해결**:
- `prev_running_tid`로 컨텍스트 스위치 시점을 정확히 파악
- 시뮬레이션 종료 시 모든 스레드에 `context_switches` 기록
- 메트릭 계산에서 `context_switches`를 지원

**위치**:
- [simulator/simulator.py:16-137](python_webapp/simulator/simulator.py#L16-L137)
- [analysis/insights.py:95-219](python_webapp/analysis/insights.py#L95-L219)

### 최종 테스트 결과 (13개 테스트)

| 스케줄러 | 승리 | 승률 |
|---------|------|------|
| Basic | 5 | 38% |
| MLFQS | 5 | 38% |
| CFS | 3 | 23% |

**결론**: 유의미한 편향 없음 (각 스케줄러가 자신의 강점에서 승리)

## 설계 결정사항

### 1. Burst Time은 정적이어야 함

**질문**: "bursttime을 vruntime 같은 변수에 맞게 동적으로 늘려야 하나?"

**답변**: **NO**

**이유**:
- `burst_time`은 "실제로 필요한 작업량"을 나타냄
- 프로세스가 완료하려면 burst_time만큼의 CPU가 필요
- 스케줄러는 이를 어떻게 배분할지 결정할 뿐, 작업량 자체는 변하지 않음
- 동적으로 변경하면 "스케줄러 성능" 대신 "워크로드 자체"가 달라짐

**Nice 효과 측정 시**:
- 긴 burst_time 사용 (10,000)
- 50% 시간에 중단하여 부분 완료 관찰
- 이것이 올바른 방법

### 2. Nice 값의 의미는 스케줄러마다 다름

**Basic Priority**:
- Nice → 정적 우선순위 변환
- `priority = 31 - nice`
- 우선순위 자체가 변경됨

**MLFQS**:
- Nice → 동적 우선순위 계산에 기여
- `priority = PRI_MAX - (recent_cpu/4) - (nice*2)`
- nice는 -2배로만 기여 (약한 효과)

**CFS**:
- Nice → 가중치 변환
- `weight = PRIO_TO_WEIGHT[nice + 20]`
- CPU 시간 비율 결정 (강한 효과)

**결론**: Nice가 포함된 워크로드는 스케줄러마다 다르게 해석되므로, 공정한 비교를 위해 대부분의 테스트에서 nice=0 사용

### 3. 공정성/Nice 테스트는 MLFQS vs CFS만

**이유**:
- Basic Priority는 정적 우선순위 기반 (starvation 위험)
- 공정성을 목표로 설계되지 않음
- Nice의 의미가 다름 (우선순위 vs 가중치)

**결과**:
- 의미 있는 비교만 수행
- 각 스케줄러의 강점을 공정하게 평가

### 4. Simulation Time: 35,000 ticks

**이유**:
- 50개 스레드 완료에 필요한 시간: ~30,000 ticks
- 여유를 두고 35,000 ticks로 설정
- Nice 효과 테스트는 예외 (50% 시간에 중단)

### 5. Time Slice: 4 ticks

**이유**:
- 너무 짧으면: Context switch 오버헤드 증가
- 너무 길면: 응답성 저하
- 4 ticks는 일반적인 Round-robin 설정

## 참고 문헌

### 학술 자료
- **MLFQS**: 4.4BSD Scheduler, FreeBSD Implementation
- **CFS**: "Inside the Linux 2.6 Completely Fair Scheduler" (IBM DeveloperWorks)
- **Fixed Point Arithmetic**: Pintos Documentation (17.14 format)

### 코드 참조
- Linux 커널 `kernel/sched/core.c` (PRIO_TO_WEIGHT 테이블)
- FreeBSD `sys/kern/sched_4bsd.c` (MLFQS 구현)

### 메트릭
- **Jain's Fairness Index**: "Quantitative Measure of Fairness" (Jain et al., 1984)
- **Context Switch**: Operating System Concepts (Silberschatz et al.)

## 라이선스
이 프로젝트는 교육 목적으로 작성되었습니다.
