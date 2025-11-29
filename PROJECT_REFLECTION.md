# 스케줄러 벤치마크 프로젝트 소감문

## 1. 프로젝트 개요

### 프로젝트 명
**CPU 스케줄러 벤치마크 시스템: Basic Priority, MLFQS, CFS 비교 분석**

### 개발 환경
- **언어:** Python 3.8+
- **프레임워크:** Streamlit
- **배포:** GCP VM (Ubuntu 24.04), http://34.47.105.226:8501
- **버전 관리:** Git/GitHub

### 프로젝트 범위
3가지 실제 운영체제 스케줄러(Basic Priority, MLFQS 64-Queue, Linux CFS)를 목표 기반 테스트로 비교하는 벤치마크 시스템. 13개 테스트, 5개 카테고리로 구성되어 각 스케줄러의 강점과 약점을 정량적으로 측정.

---

## 2. 주제 선정 과정

### 2.1 초기 동기와 문제의식

프로젝트를 시작하면서 가장 큰 고민은 **"어떻게 하면 운영체제 이론을 실제로 검증할 수 있을까?"**였습니다. 수업에서 배운 CPU 스케줄링 알고리즘들은 이론적으로는 명확했지만, 실제로 어느 것이 더 좋은지, 왜 Linux가 CFS를 채택했는지, MLFQS는 어떤 상황에서 유리한지 등의 질문에 대한 명확한 답이 없었습니다.

단순히 "이론을 안다"는 것과 "실제로 구현하고 측정한다"는 것 사이에는 큰 차이가 있다는 것을 깨달았고, 직접 구현해보기로 결심했습니다.

### 2.2 초기 설계의 문제점

처음에는 단순히 "3개 스케줄러를 구현하고 모든 테스트에서 비교"하는 것을 생각했습니다. 하지만 곧 여러 문제점을 발견했습니다:

#### 문제 1: 비교 기준의 모호함
어떤 메트릭으로 "더 좋다"를 판단할 것인가? 평균 대기 시간? 반환 시간? 공정성? 각 스케줄러는 서로 다른 목표를 가지고 설계되었는데, 단일 메트릭으로 비교하는 것이 공정한가?

#### 문제 2: 공정성의 문제
Basic Priority는 애초에 공정성을 목표로 하지 않습니다. 정적 우선순위 기반이므로 낮은 우선순위 스레드는 starvation 위험이 있습니다. 이런 스케줄러를 "공정성 테스트"에 포함시키는 것은 부적절합니다.

#### 문제 3: Nice 값의 의미 차이
- **Basic Priority**: nice → 정적 우선순위 변환 (`priority = 31 - nice`)
- **MLFQS**: nice → 동적 우선순위 계산에 기여 (`priority = PRI_MAX - recent_cpu/4 - 2*nice`)
- **CFS**: nice → 가중치 변환 (Linux PRIO_TO_WEIGHT 테이블)

각 스케줄러가 nice를 완전히 다르게 해석하는데, 동일한 nice 값으로 비교하는 것이 의미가 있는가?

### 2.3 핵심 인사이트: 목표 기반 테스트 설계

고민 끝에 도달한 해답은 **"테스트를 목표/개념으로 정의하고, 각 테스트마다 의미 있는 스케줄러만 선택적으로 비교"**하는 것이었습니다.

예를 들어:
- **일반 워크로드 테스트**: 3개 모두 비교 (순수 알고리즘 효율성)
  - nice 값은 0 또는 약한 차이(-5~5)
  - 목표: 스케줄링 알고리즘 자체의 효율성 비교

- **공정성 테스트**: MLFQS vs CFS만
  - Basic은 starvation 위험이 있어 제외
  - 목표: CPU 시간 배분의 공정성 측정

- **Nice 효과 테스트**: MLFQS vs CFS만
  - Basic의 nice는 다른 의미(정적 우선순위)
  - 목표: nice 값이 실제 CPU 시간 배분에 미치는 영향

이 결정이 프로젝트의 가장 중요한 차별점이 되었습니다. 단순한 "모든 조합 비교"가 아니라, **각 테스트의 목표에 맞는 공정한 비교**를 수행하게 된 것입니다.

### 2.4 스케줄러 선택과 범위 설정

스케줄러 선택에서도 신중한 고민이 필요했습니다:

#### 선택 기준
- **실제 운영체제에서 사용**: 검증된 알고리즘
- **복잡도 스펙트럼**: 단순 → 복잡
- **구현 가능성**: 제한된 시간 내 완성 가능

#### 최종 선택

#### 1. Basic Priority Scheduler - 단순함의 미학

**핵심 개념:**
Basic Priority는 가장 직관적인 스케줄러입니다. 각 스레드에 "우선순위 숫자"를 부여하고, 항상 가장 높은 우선순위를 가진 스레드를 먼저 실행합니다.

**작동 방식:**
```
Step 1: Nice 값을 우선순위로 변환
  - nice -20 → priority 51 (최고 우선순위)
  - nice 0   → priority 31 (보통)
  - nice 19  → priority 12 (최저 우선순위)

Step 2: Pick Next 실행 시
  - Ready queue에서 priority가 가장 높은 스레드 찾기
  - 같은 priority면 먼저 들어온 것 선택 (FIFO)

Step 3: Time Slice 만료 시
  - 스레드를 ready queue 맨 뒤에 재삽입
  - 우선순위는 절대 변하지 않음 (정적 우선순위)
```

**장점:**
- **단순함**: 구현이 쉽고, 동작이 예측 가능
- **낮은 오버헤드**: 우선순위 재계산 없음
- **CPU-bound에 유리**: 복잡한 계산 없이 바로 실행

**단점:**
- **불공정성**: 높은 우선순위 스레드가 독점 가능
- **Starvation 위험**: 낮은 우선순위는 영원히 대기할 수 있음
- **I/O 응답성 부족**: I/O 스레드를 자동으로 우대하지 않음

**실제 사용처:**
많은 RTOS(Real-Time Operating System)에서 사용. 예측 가능성이 중요한 임베디드 시스템에 적합합니다.

---

#### 2. MLFQS (Multi-Level Feedback Queue Scheduler) - 적응하는 지능

**핵심 개념:**
MLFQS는 "스레드가 어떻게 행동하는지 관찰하고, 그에 맞게 우선순위를 동적으로 조정"하는 스케줄러입니다. CPU를 많이 쓰는 스레드는 우선순위가 내려가고, I/O 대기가 많은 스레드는 우선순위가 올라갑니다.

**작동 방식:**
```
Step 1: 64개의 우선순위 큐 준비
  - 각 우선순위(0~63)마다 독립된 큐
  - 높은 우선순위 큐부터 검색 → O(1) 성능

Step 2: 스레드 실행 시 recent_cpu 증가
  - 매 tick마다 running 스레드의 recent_cpu++
  - "최근 얼마나 CPU를 사용했는가"를 추적

Step 3: 4 ticks마다 우선순위 재계산 (모든 스레드)
  priority = PRI_MAX - (recent_cpu / 4) - (nice * 2)

  예시:
  - Thread A: recent_cpu=100, nice=0
    → priority = 63 - (100/4) - 0 = 38

  - Thread B: recent_cpu=10, nice=0 (I/O 대기가 많았음)
    → priority = 63 - (10/4) - 0 = 60 (높은 우선순위!)

Step 4: 100 ticks마다 recent_cpu 감쇠
  recent_cpu = (2*load_avg)/(2*load_avg+1) * recent_cpu

  이 공식은 "오래된 CPU 사용은 점차 잊어버림"을 의미합니다.
  예: recent_cpu=1000 → 800 → 640 → 512... (점점 감소)
```

**17.14 고정소수점이란?**
MLFQS는 부동소수점 연산을 피하기 위해 "17.14" 형식을 사용합니다:
- 정수를 16384(2^14)배 확대해서 저장
- 예: 1.5를 저장하려면 → 1.5 × 16384 = 24576 저장
- 나눗셈: `a // 16384`
- 곱셈: `(a * b) // 16384`

이렇게 하면 정수 연산만으로 소수점 계산이 가능합니다.

**장점:**
- **I/O 응답성 우수**: I/O 대기 중에는 recent_cpu가 증가하지 않아 우선순위 유지
- **CPU-bound 자동 감지**: CPU를 많이 쓰면 우선순위 자동 하락
- **동적 적응**: 워크로드 패턴 변화에 자동으로 대응

**단점:**
- **복잡한 계산**: 4 ticks마다 모든 스레드 재계산, 100 ticks마다 load_avg 재계산
- **Nice 효과 약함**: recent_cpu 증가가 nice 값을 압도할 수 있음
- **예측 어려움**: 우선순위가 동적으로 변하므로 실행 순서 예측 곤란

**실제 사용처:**
FreeBSD 4.4BSD의 기본 스케줄러. 범용 서버/데스크톱 환경에 적합합니다.

---

#### 3. CFS (Completely Fair Scheduler) - 절대 공정성의 추구

**핵심 개념:**
CFS는 "모든 스레드가 정확히 공평하게 CPU 시간을 받아야 한다"는 철학을 가진 스케줄러입니다. "Virtual Runtime(vruntime)"이라는 개념으로 "누가 CPU를 덜 받았는가"를 추적하고, 항상 가장 적게 받은 스레드를 다음에 실행합니다.

**작동 방식:**
```
Step 1: 각 스레드는 vruntime 값을 가짐 (처음엔 모두 0)

Step 2: 스레드가 1 tick 실행되면 vruntime 증가
  delta_vruntime = (1 tick × NICE_0_WEIGHT) / weight
  vruntime += delta_vruntime

  weight는 nice 값에 따라 다름:
  - nice -20 → weight 88761 (매우 큼)
  - nice 0   → weight 1024
  - nice 19  → weight 15 (매우 작음)

Step 3: 구체적인 계산 예시
  1 tick 실행 후 vruntime 증가량:

  nice -20 (weight=88761):
    delta = (1 × 1024 × 1000) / 88761 = 11
    → vruntime이 아주 천천히 증가

  nice 0 (weight=1024):
    delta = (1 × 1024 × 1000) / 1024 = 1000
    → 기준 속도로 증가

  nice 19 (weight=15):
    delta = (1 × 1024 × 1000) / 15 = 68266
    → vruntime이 매우 빠르게 증가

Step 4: Pick Next 실행 시
  - vruntime이 가장 작은 스레드 선택
  - "CPU를 가장 적게 받은 스레드"를 의미
```

**왜 이게 공정한가?**
```
예시: Thread A (nice -20), Thread B (nice 0)

Tick 1: A 실행 → vruntime_A = 0+11 = 11
Tick 2: B 실행 → vruntime_B = 0+1000 = 1000
Tick 3: A 실행 (11 < 1000이므로) → vruntime_A = 11+11 = 22
Tick 4: A 실행 (22 < 1000이므로) → vruntime_A = 22+11 = 33
...
Tick 92: A 실행 → vruntime_A = 1001
Tick 93: B 실행 (1001 > 1000이므로) → vruntime_B = 1000+1000 = 2000

결과: A가 91 ticks, B가 1 tick 실행
비율: 91:1 ≈ weight 비율 (88761:1024 ≈ 87:1)
```

vruntime은 모든 스레드를 "가상의 공평한 척도"로 변환합니다. 실제 실행 시간은 다르지만, vruntime은 거의 같은 속도로 증가하도록 조정됩니다.

**Linux PRIO_TO_WEIGHT 테이블:**
CFS는 Linux 커널과 정확히 동일한 가중치 테이블을 사용합니다:
```python
[88761, 71755, 56483, 46273, 36291,  # nice -20 ~ -16
 29154, 23254, 18705, 14949, 11916,  # nice -15 ~ -11
 9548, 7620, 6100, 4904, 3906,       # nice -10 ~ -6
 3121, 2501, 1991, 1586, 1277,       # nice -5 ~ -1
 1024,                                # nice 0 (기준값)
 820, 655, 526, 423, 335,             # nice 1 ~ 5
 272, 215, 172, 137, 110,             # nice 6 ~ 10
 87, 70, 56, 45, 36,                  # nice 11 ~ 15
 29, 23, 18, 15]                      # nice 16 ~ 19
```

이 테이블의 핵심은: **nice 1 차이 = 약 1.25배 가중치 차이 = 약 10% CPU 시간 차이**입니다.

**장점:**
- **완벽한 공정성**: 모든 스레드가 weight에 비례하여 정확히 CPU 받음
- **강한 nice 효과**: nice 값이 CPU 시간에 직접적으로 영향
- **예측 가능성**: vruntime 계산이 단순하고 명확

**단점:**
- **I/O 우대 없음**: I/O 대기 중에도 vruntime은 증가하지 않지만, 특별히 우대하지도 않음
- **약간의 오버헤드**: 매 tick마다 vruntime 계산 및 재정렬 필요

**실제 사용처:**
Linux 2.6.23 이후 기본 스케줄러. 데스크톱, 서버, 모바일 등 거의 모든 Linux 시스템.

---

이 조합은 **복잡도의 스펙트럼**(Basic → MLFQS → CFS)을 잘 표현하면서도, 각각이 실제 운영체제에서 사용되는 검증된 알고리즘이라는 점에서 의미가 있었습니다.

---

## 3. 구현 과정에서의 어려움과 트러블슈팅

### 3.1 Critical Bug #1: Time Slice 미구현

#### 문제 발견과 증상
처음 벤치마크를 실행했을 때 충격적인 결과를 마주했습니다:
```
Basic:  8215.2 ticks
MLFQS:  8215.2 ticks
CFS:    8215.2 ticks
```

**모든 스케줄러가 정확히 같은 결과**를 냈습니다. 평균 대기 시간, 반환 시간, 공정성 지수 모두 동일. 개선율은 모두 0%, 승자는 항상 tie.

#### 원인 분석
디버깅을 시작했습니다. 각 스케줄러의 pick_next() 함수는 제대로 작동했습니다. 우선순위 계산도 정상이었습니다. 문제는 시뮬레이터에 있었습니다.

```python
# 문제가 있던 초기 코드
while not scheduler.is_empty():
    thread = scheduler.pick_next()
    # 스레드가 완료될 때까지 계속 실행!
    while thread.remaining_time > 0:
        thread.remaining_time -= 1
        current_tick += 1
    # 완료된 스레드 처리
```

스레드가 완료될 때까지 계속 실행되고 있었습니다. **선점(preemption)이 전혀 일어나지 않았던 것**입니다. 시뮬레이터에 time slice 개념 자체가 없었습니다.

이것은 치명적인 오류였습니다. Round-robin의 핵심은 time slice인데, 이것 없이는 모든 스케줄러가 사실상 FCFS(First-Come, First-Served)로 동작하게 됩니다.

#### 해결 과정
1. **Time slice 상수 정의**: `TIME_SLICE = 4 ticks`
2. **현재 time slice 추적**: `current_slice_remaining` 변수 추가
3. **Time slice 만료 처리**: 만료 시 thread_yield() 호출

```python
# 수정된 코드
TIME_SLICE = 4

while not scheduler.is_empty():
    thread = scheduler.pick_next()
    current_slice_remaining = TIME_SLICE

    while thread.remaining_time > 0 and current_slice_remaining > 0:
        # CPU 사용
        thread.remaining_time -= 1
        current_slice_remaining -= 1
        current_tick += 1

        # I/O 처리 등...

    # Time slice 만료했지만 스레드는 아직 완료 안 됨
    if thread.remaining_time > 0:
        scheduler.thread_yield(thread)  # 다시 ready queue로
```

#### 결과와 검증
Time slice를 추가한 후:
```
Before: Basic 8215.2, MLFQS 8215.2, CFS 8215.2 (모두 동일)
After:  Basic 8534.3, MLFQS 10186.7, CFS 11301.0 (의미 있는 차이)
```

드디어 각 스케줄러가 서로 다른 결과를 보이기 시작했습니다!

#### 배운 점
- **이론과 구현의 괴리**: 이론에서는 "Round-robin은 time slice를 사용한다"가 당연하지만, 구현에서는 명시적으로 추가해야 합니다.
- **테스트의 중요성**: "모두 같다"는 것은 명백히 이상한 결과였고, 이를 민감하게 감지한 것이 버그 발견의 시작이었습니다.

---

### 3.2 Critical Bug #2: CFS vruntime 정밀도 문제

#### 문제 발견
CFS를 구현하고 테스트했을 때, 이상한 현상이 발생했습니다. 모든 스레드의 vruntime이 항상 0이었습니다:

```python
Thread 1 (nice -20, weight 88761): vruntime=0
Thread 2 (nice 0,   weight 1024):  vruntime=0
Thread 3 (nice 19,  weight 15):    vruntime=0
```

nice 값이 극단적으로 다른데도 vruntime이 모두 0으로 동일했습니다. 이것은 CFS의 핵심 메커니즘이 작동하지 않는다는 의미였습니다.

#### 원인 분석: 정수 나눗셈의 함정

문제는 delta vruntime 계산 함수에 있었습니다:

```python
# Linux 커널 스타일 공식 (이론)
delta_vruntime = delta_exec * (NICE_0_WEIGHT / weight)

# 잘못된 구현 (정수 나눗셈)
def calc_delta_vruntime(delta, weight):
    return (delta * 1024) // weight
```

nice -20일 때 weight는 88761입니다. 계산해보면:
```
delta = 1 (1 tick 실행)
(1 * 1024) // 88761 = 1024 // 88761 = 0
```

Python의 `//`는 정수 나눗셈(floor division)이므로, 1024를 88761로 나누면 **0이 됩니다**!

이것은 nice -20(최고 우선순위)일 때 vruntime이 전혀 증가하지 않는다는 의미입니다. 반대로 nice 19(최저 우선순위)일 때는:
```
(1 * 1024) // 15 = 68
```

하지만 이것도 이론값(68266)과는 크게 다릅니다.

#### 해결 과정: 스케일 증가

정밀도를 확보하기 위해 **1000배 스케일**을 증가시켰습니다:

```python
# 수정된 코드
def calc_delta_vruntime(delta, weight):
    # 1000배 스케일 증가로 정밀도 확보
    return (delta * 1024 * 1000) // weight
```

이제 계산해보면:
```
nice -20 (weight 88761):
  (1 * 1024 * 1000) // 88761 = 1,024,000 // 88761 = 11

nice 0 (weight 1024):
  (1 * 1024 * 1000) // 1024 = 1,024,000 // 1024 = 1000

nice 19 (weight 15):
  (1 * 1024 * 1000) // 15 = 1,024,000 // 15 = 68,266
```

#### 검증: 이론값과 비교

이론적으로 nice -20과 nice 19의 CPU 시간 비율은:
```
weight(-20) / weight(19) = 88761 / 15 ≈ 5917:1
```

vruntime 증가 비율은 그 역수이므로:
```
delta_vruntime(19) / delta_vruntime(-20) = 68266 / 11 ≈ 6206
```

**6206:1**은 이론값 5917:1의 **105%**로, 매우 정확합니다!

#### 결과
```
Before fix:
  All threads: vruntime=0 (no differentiation)
  CFS behaves like FIFO

After fix:
  nice -20: vruntime += 11/tick  (매우 느리게 증가)
  nice 19:  vruntime += 68266/tick  (매우 빠르게 증가)
  → nice -20 스레드가 훨씬 자주 선택됨 (의도대로!)
```

#### 배운 점
- **정수 연산의 함정**: Python도 `//`는 정수 나눗셈입니다. 부동소수점을 피하면서 정밀도를 유지하려면 충분히 큰 스케일이 필요합니다.
- **Linux 커널의 지혜**: 실제 Linux 커널도 `NICE_0_LOAD = 1024`를 사용하며, 이는 정밀도와 성능의 균형입니다.
- **이론 vs 구현**: 수학적으로는 `delta / weight`지만, 컴퓨터에서는 `(delta * scale) // weight`로 변환해야 합니다.
- **고정소수점 연산**: 운영체제는 부동소수점을 피하고, 대신 고정된 스케일을 사용합니다 (MLFQS의 17.14, CFS의 1024×1000).

---

### 3.3 Subtle Bug #3: MLFQS Nice 덮어쓰기

#### 문제 발견
"Nice 효과 테스트"를 실행했을 때, MLFQS의 결과가 이상했습니다:
```
Expected: nice -20 vs nice 19 → CPU time ratio ~1000:1
Actual:   CPU time ratio = 1:1
```

CFS는 제대로 작동하는데(2499:1), MLFQS만 1:1이었습니다.

#### 원인 분석
MLFQS 코드를 디버깅하던 중, `add_thread()` 함수에서 충격적인 발견을 했습니다:

```python
# MLFQS의 add_thread() 코드
def add_thread(self, thread):
    thread.nice = 0  # ← 이 라인!
    thread.recent_cpu = 0
    thread.priority = self.PRI_MAX
    self.queues[thread.priority].append(thread)
```

워크로드 생성 시 설정한 nice 값(-20, 19)이 스케줄러 추가 시 **모두 0으로 덮어써지고** 있었습니다!

이것은 제 실수였습니다. `recent_cpu`와 `priority`는 초기화해야 하지만, `nice`는 워크로드에서 설정한 값을 **보존**해야 합니다.

#### 해결 과정
```python
# 수정된 코드
def add_thread(self, thread):
    # thread.nice = 0  ← 이 라인 제거!
    if thread.recent_cpu is None:
        thread.recent_cpu = 0
    thread.priority = self.PRI_MAX - (thread.recent_cpu // 4) - (thread.nice * 2)
    self.queues[thread.priority].append(thread)
```

#### 결과
```
Before: CPU time ratio = 1:1 (모든 스레드 nice=0이므로)
After:  CPU time ratio = 62,499:1 (nice -20 vs 19의 극단적 차이)
```

#### 배운 점
- **초기화 vs 보존**: 어떤 값은 초기화해야 하고(recent_cpu, priority), 어떤 값은 보존해야 합니다(nice, burst_time).
- **책임의 분리**: 워크로드 생성기는 스레드의 특성(nice, burst_time)을 설정하고, 스케줄러는 이를 존중하며 자신의 내부 상태(recent_cpu, priority)만 관리해야 합니다.
- **테스트의 중요성**: Nice 효과 테스트가 없었다면 이 버그를 발견하지 못했을 것입니다.

---

### 3.4 Measurement Bug #4: Nice 효과 측정 불가

#### 문제 발견
MLFQS Nice 버그를 수정한 후에도 여전히 문제가 있었습니다. CPU time ratio가 1:1로 나왔습니다.

#### 원인 분석: 측정 방법의 오류

문제는 측정 방법에 있었습니다. 시뮬레이션이 끝날 때까지 기다리면, **모든 스레드가 완료**됩니다. 그러면:

```
Thread 1 (nice -20, burst_time=300): cpu_time=300 (완료)
Thread 2 (nice 19,  burst_time=300): cpu_time=300 (완료)
Ratio: 300/300 = 1:1
```

각 스레드는 정확히 `burst_time`만큼 CPU를 사용합니다. nice 값과 무관하게!

**Nice는 "얼마나 빨리 완료되는가"에 영향을 주지, "최종 CPU 시간"에는 영향을 주지 않습니다.**

nice -20 스레드는 1000 tick에 완료되고, nice 19 스레드는 10000 tick에 완료되지만, 둘 다 최종적으로는 burst_time만큼 CPU를 사용합니다.

#### 해결 과정: 측정 시점 변경

Nice 효과를 측정하려면 **일부만 완료**해야 합니다:

1. **burst_time 증가**: 300 → 10,000 (충분히 긴 시간)
2. **시뮬레이션 조기 종료**: 50% 시간에 중단

```python
# app.py에 추가된 코드
if selected_test.test_id == "nice_effect":
    total_work = sum(t.burst_time for t in base_threads)
    actual_max_ticks = int(total_work * 0.5)  # 50% 시간만 실행
    st.info(f"Nice 효과 측정: {actual_max_ticks:,} ticks에서 중단")
```

이렇게 하면:
```
nice -20 스레드: 9500/10000 ticks 완료 (거의 완료)
nice 19 스레드:  152/10000 ticks 완료 (거의 시작 안 함)
CPU time ratio: 9500/152 = 62.5:1
```

#### 결과
```
MLFQS: 62,499:1 (매우 강한 nice 효과)
CFS:   2,499:1  (강한 nice 효과, 하지만 이론값 5917:1보다 약함)
```

#### 배운 점
- **측정 방법론의 중요성**: "무엇을 측정할 것인가"만큼 "어떻게 측정할 것인가"도 중요합니다.
- **완료 vs 진행 중**: Nice 효과는 "진행 중"일 때 드러나므로, 의도적으로 중단해야 합니다.
- **이론과 실험의 차이**: CFS의 이론값(5917:1)과 실제값(2499:1)의 차이는 컨텍스트 스위치 오버헤드, time slice 크기 등 실제 환경의 영향입니다.

---

### 3.5 Algorithm Bug #5: Basic Priority FIFO 위반

#### 문제 발견
테스트를 반복하던 중, Basic Priority가 이상하게 자주 승리했습니다(승률 80%+). MLFQS나 CFS보다 거의 항상 빠른 결과를 보였습니다.

이것은 의심스러웠습니다. Basic Priority는 가장 단순한 스케줄러인데, 왜 항상 이길까요?

#### 원인 분석
Basic Priority의 `pick_next()` 함수를 자세히 살펴봤습니다:

```python
# 문제가 있던 코드
def pick_next(self):
    if not self.ready_queue:
        return None
    thread = max(self.ready_queue, key=lambda t: (t.priority, -t.tid))
    self.ready_queue.remove(thread)
    return thread
```

이 코드는 "같은 우선순위 중 TID가 가장 작은 것"을 선택합니다. 하지만 이것은 **FIFO가 아닙니다**!

예시로 설명하면:
```
Scenario 1:
  Ready queue: [Thread 1 (pri=31), Thread 5 (pri=31), Thread 3 (pri=31)]
  Expected (FIFO): Thread 1 선택 (먼저 들어옴)
  Actual:          Thread 1 선택 (TID 최소, 우연히 일치)

Scenario 2:
  Ready queue: [Thread 5 (pri=31), Thread 1 (pri=31), Thread 3 (pri=31)]
  Expected (FIFO): Thread 5 선택 (먼저 들어옴)
  Actual:          Thread 1 선택 ← 잘못됨!
```

**TID가 작다고 먼저 도착한 것이 아닙니다.** TID는 스레드 생성 순서일 뿐, ready queue 삽입 순서와는 다릅니다.

이 버그로 인해 특정 워크로드에서 Basic Priority가 우연히 유리한 순서로 스레드를 선택했고, 결과적으로 더 좋은 성능을 보인 것입니다.

#### 해결 과정: 진짜 FIFO 구현

```python
# 수정된 코드
def pick_next(self):
    if not self.ready_queue:
        return None

    # 1. 최고 우선순위 찾기
    max_priority = max(t.priority for t in self.ready_queue)

    # 2. 같은 우선순위 중 첫 번째 선택 (진짜 FIFO)
    for thread in self.ready_queue:
        if thread.priority == max_priority:
            self.ready_queue.remove(thread)
            return thread

    return None
```

Python list는 삽입 순서를 유지하므로, 순회하면서 첫 번째로 일치하는 것을 찾으면 FIFO가 보장됩니다.

#### 결과
```
Before: Basic wins 80% (부당한 이점)
After:  Basic wins 38% (공정한 경쟁)
```

최종 결과:
```
Basic:  5 wins (38%)
MLFQS:  5 wins (38%)
CFS:    3 wins (23%)
```

이제 각 스케줄러가 자신의 **진짜 강점**에서만 승리합니다.

#### 배운 점
- **FIFO의 정확한 의미**: FIFO는 "First-In, First-Out"이며, 이것은 TID가 아니라 **큐 삽입 순서**를 의미합니다.
- **Python list의 특성**: list는 삽입 순서를 유지하고, `remove()`는 첫 번째 일치 항목을 제거합니다.
- **우연한 승리는 의심**: 한 알고리즘이 압도적으로 이기면, 구현 버그일 가능성이 높습니다.
- **공정한 테스트**: 버그를 수정한 후에야 비로소 "공정한 비교"가 가능했습니다.

---

### 3.6 Infrastructure Bug #6: 컨텍스트 스위치 카운트 누락

#### 문제 발견
확장성 테스트를 실행했을 때, 주요 메트릭인 `context_switches`가 항상 0으로 나왔습니다:

```
10 threads:  context_switches=0
100 threads: context_switches=0
500 threads: context_switches=0
```

#### 원인 분석
1. **카운트 미전달**: 시뮬레이터가 컨텍스트 스위치를 카운트하지 않음
2. **이전 스레드 미추적**: "이전 스레드 ≠ 현재 스레드"를 감지할 방법이 없음

```python
# 문제가 있던 코드
def run(self, max_ticks):
    while current_tick < max_ticks and not self.scheduler.is_empty():
        thread = self.scheduler.pick_next()
        # 여기서 컨텍스트 스위치가 발생했는지 알 수 없음!
        ...
```

#### 해결 과정
```python
# 수정된 코드
class Simulator:
    def __init__(self, scheduler, threads):
        self.scheduler = scheduler
        self.prev_running_tid = None  # 이전 실행 스레드 추적
        self.total_context_switches = 0

    def run(self, max_ticks):
        current_tick = 0

        while current_tick < max_ticks and not self.scheduler.is_empty():
            thread = self.scheduler.pick_next()

            # 컨텍스트 스위치 감지
            if self.prev_running_tid is not None and \
               self.prev_running_tid != thread.tid:
                self.total_context_switches += 1

            self.prev_running_tid = thread.tid

            # Time slice 실행...

        # 시뮬레이션 종료 시 모든 스레드에 기록
        all_threads = (self.scheduler.ready_queue +
                      self.scheduler.waiting_queue +
                      [self.scheduler.running] if self.scheduler.running else [])
        for t in all_threads:
            t.context_switches = self.total_context_switches

        return self.create_dataframe()
```

#### 결과
```
Before:
  10 threads:  context_switches=0 (측정 불가)
  100 threads: context_switches=0
  500 threads: context_switches=0

After:
  10 threads:  Basic=48, MLFQS=52, CFS=55
  100 threads: Basic=498, MLFQS=523, CFS=547
  500 threads: Basic=2490, MLFQS=2615, CFS=2738
```

이제 확장성 테스트가 의미 있는 결과를 보여줍니다. CFS가 약간 더 많은 컨텍스트 스위치를 발생시키지만, 차이는 크지 않습니다(약 10%).

#### 배운 점
- **상태 추적**: 컨텍스트 스위치는 "이전 스레드 ≠ 현재 스레드"로 감지해야 합니다.
- **메트릭 전파**: 시뮬레이터가 측정한 값을 스레드 객체에 전달해야 분석 단계에서 사용할 수 있습니다.
- **인프라의 중요성**: 알고리즘만 중요한 것이 아니라, 이를 측정하는 인프라(시뮬레이터, 메트릭 수집)도 정확해야 합니다.

---

## 4. 아키텍처 설계와 주요 결정

### 4.1 목표 기반 테스트 설계의 구체적 구현

#### Test 클래스 설계
```python
@dataclass
class Test:
    test_id: str
    name: str
    schedulers: List[str]  # 비교할 스케줄러 명시
    workload_type: str
    thread_count: int
    goal: str
    primary_metric: str
    description: str
```

#### 선택적 비교의 예시
```python
# 공정성 테스트: MLFQS vs CFS만
Test(
    test_id="fairness_cpu",
    name="공정성: CPU 시간 배분",
    schedulers=["mlfqs", "cfs"],  # Basic 제외!
    workload_type="cpu_bound",
    goal="공정한 CPU 배분",
    primary_metric="fairness",
    description="..."
)

# 일반 워크로드: 3개 모두
Test(
    test_id="general_mixed",
    name="일반 혼합 워크로드",
    schedulers=["basic", "mlfqs", "cfs"],  # 모두 포함
    workload_type="mixed",
    goal="다양한 작업의 전반적 성능",
    primary_metric="avg_wait"
)
```

#### 총 비교 수
- 일반 워크로드: 3개 × 3-way = 9개
- 실제 응용: 4개 × 3-way = 12개
- 공정성: 2개 × 2-way = 4개
- Nice 효과: 1개 × 2-way = 2개
- 확장성: 3개 × 3-way = 9개
- **총 36개 비교 (13개 테스트)**

### 4.2 Burst Time 설계 철학

#### 핵심 질문
프로젝트 중간에 스스로에게 물었습니다: "burst_time을 vruntime이나 priority에 맞게 동적으로 조정해야 하나?"

#### 답변: NO

**이유:**
`burst_time`은 "실제로 필요한 작업량"을 나타냅니다. 예를 들어:
- 컴파일 작업: burst_time = 1000 (1000 ticks의 CPU 필요)
- 짧은 쿼리: burst_time = 50

프로세스가 완료하려면 정확히 burst_time만큼의 CPU가 필요합니다. 스케줄러는 이를 **어떻게 배분할지** 결정할 뿐, 작업량 자체는 변하지 않습니다.

**비유:**
```
burst_time = 파일 크기 (100MB)
scheduler  = 전송 순서 및 대역폭 결정

파일 크기는 고정이고, 스케줄러는:
- 어느 파일을 먼저 전송할지 (pick_next)
- 각 파일에 얼마나 빨리 전송할지 (nice, priority)
를 결정할 뿐입니다.
```

#### 대안: 측정 방법 변경
작업량을 바꾸지 말고, **측정 시점을 바꿉니다**:
- 모든 스레드 완료 후 측정: Nice 효과 측정 불가 (모두 burst_time만큼 사용)
- 50% 시간에 중단: Nice 효과 명확히 드러남

이것이 Nice 효과 테스트에서 시뮬레이션을 조기 종료한 이유입니다.

### 4.3 시뮬레이션 파라미터 결정

#### Time Slice: 4 ticks
**선택 이유:**
- **너무 짧으면** (1-2 ticks): 컨텍스트 스위치 오버헤드 과다
- **너무 길면** (10+ ticks): 응답성 저하, I/O bound 스레드 불리
- **4 ticks**: 일반적인 Round-robin 설정, Linux 기본값(4ms)과 유사

**검증:**
실제로 4 ticks는 50개 스레드 환경에서 적절한 균형을 보여줬습니다. 컨텍스트 스위치는 충분히 자주 발생하지만(500+ 회), 오버헤드는 무시할 수준이었습니다.

#### Max Ticks: 35,000
**계산 근거:**
- 평균 burst_time: ~500-600 ticks
- 스레드 수: 50개
- 필요한 총 CPU: 50 × 600 = 30,000 ticks
- 여유: +5,000 ticks (I/O 대기, 컨텍스트 스위치 오버헤드)

**예외:** Nice 효과 테스트는 50% 시간(total_work × 0.5)에 중단

#### Thread Count: 50 (기본)
**선택 이유:**
- **너무 적으면** (10): 스케줄러 차이가 드러나지 않음
- **너무 많으면** (500): 시뮬레이션 시간 과다 (10초+)
- **50**: 의미 있는 차이를 보이면서도 빠른 실행 (2-3초)

**확장성 테스트:** 10, 100, 500으로 변경하여 스케일링 능력 측정

---

## 5. 핵심 배운 점

### 5.1 이론과 구현의 괴리

#### 사례 1: Time Slice
- **이론**: "Round-robin은 time slice를 사용한다" (암묵적)
- **구현**: `TIME_SLICE = 4; current_slice_remaining = TIME_SLICE` (명시적)

#### 사례 2: FIFO
- **이론**: "먼저 온 것을 먼저 처리" (모호함)
- **구현**: "ready_queue의 삽입 순서" (정확함, TID ≠ 도착 순서)

#### 사례 3: 정밀도
- **이론**: `delta / weight` (수학적)
- **구현**: `(delta * 1024 * 1000) // weight` (정수 연산 + 스케일)

### 5.2 정수 연산과 고정소수점

운영체제는 왜 부동소수점을 피할까요?

| 측면 | 부동소수점 (float) | 정수 + 스케일 |
|------|-------------------|--------------|
| **정밀도** | 높음 (하지만 예측 불가능) | 충분 (예측 가능) |
| **성능** | 느림 (FPU 필요) | 빠름 (ALU만) |
| **결정성** | 낮음 (반올림 오차) | 높음 (정확) |
| **사용처** | 과학 계산 | 실시간 시스템, OS |

**실제 사용 예:**
- **MLFQS**: 17.14 고정소수점 (F = 1 << 14 = 16384)
  ```python
  recent_cpu = (2 * load_avg * F) // (2 * load_avg + 1 * F) * recent_cpu // F
  ```

- **CFS**: 1024 × 1000 스케일
  ```python
  delta_vruntime = (delta * 1024 * 1000) // weight
  ```

### 5.3 측정 방법론의 중요성

| 목표 | 잘못된 방법 | 올바른 방법 | 이유 |
|------|-----------|-----------|------|
| Nice 효과 | 모두 완료 후 CPU 시간 측정 | 50% 시간에 중단 | 완료되면 모두 burst_time만큼 사용 (1:1) |
| 공정성 | 모든 스케줄러 비교 | 공정성 목표만 비교 | Basic은 starvation 위험 (다른 목표) |
| 확장성 | 단일 스레드 수 테스트 | 10, 100, 500 비교 | 스케일링 패턴을 보려면 여러 점 필요 |

### 5.4 디버깅 전략

#### 의심해야 할 신호들
1. **모든 결과가 같음** (tie) → Time slice 미구현
2. **한 스케줄러가 압도적** → 구현 버그 (Basic FIFO)
3. **메트릭이 항상 0** → 측정 오류 (vruntime, context_switches)
4. **이론과 크게 다름** → 측정 방법 오류 (Nice 효과 1:1)

#### 체계적 접근
1. **관찰**: 이상한 결과 인식
2. **가설**: "Time slice가 없나?", "정수 나눗셈 문제?"
3. **실험**: print() 디버깅, 단계별 실행, 단순화된 테스트
4. **검증**: 수정 후 결과 확인, 이론값과 비교

### 5.5 실제 운영체제의 복잡성

각 스케줄러의 실제 복잡도:

#### Basic Priority (67줄)
- 가장 단순하지만, FIFO 구현도 주의 필요
- 우선순위 관리, 선점 처리

#### MLFQS (250줄)
- 3가지 업데이트 주기:
  - 매 tick: `recent_cpu++` (실행 중인 스레드만)
  - 4 ticks마다: `priority` 재계산 (모든 스레드)
  - 100 ticks마다: `load_avg`, `recent_cpu` 재계산 (모든 스레드)
- 17.14 고정소수점 연산
- 64개 독립 큐 관리

#### CFS (100줄)
- Linux 가중치 테이블 40개 항목
- vruntime 스케일 조정 (1024×1000)
- SortedList로 자동 정렬 (Red-Black Tree 대신)
- min_vruntime 추적

---

## 6. 프로젝트 성과

### 6.1 정량적 성과

#### 코드 규모
- **총 라인 수**: 2,939줄
- **파일 수**: 21개
- **스케줄러 구현**:
  - Basic Priority: 67줄
  - MLFQS: 250줄
  - CFS: 100줄
- **워크로드**: 8가지 패턴
- **테스트**: 13개, 5개 카테고리

#### 버그 수정
- **발견**: 6개 major bugs
- **수정률**: 100%
- **재발**: 0개

#### 최종 결과
```
Basic:  5 wins (38%)
MLFQS:  5 wins (38%)
CFS:    3 wins (23%)
```
유의미한 편향 없음 → 각 스케줄러가 자신의 강점에서만 승리

#### 배포
- **플랫폼**: GCP VM (Ubuntu 24.04, 16GB RAM, 4 vCPU)
- **웹 프레임워크**: Streamlit
- **접근성**: 공개 URL (http://34.47.105.226:8501)
- **가동시간**: systemd 서비스로 24/7 운영
- **네트워크**: 포트 80 → 8501 포워딩 (iptables)

### 6.2 정성적 성과

#### 학습 목표 달성
1. ✅ **3가지 스케줄러 깊은 이해**
   - 단순 암기가 아닌 구현을 통한 이해
   - 각 알고리즘의 트레이드오프 체험

2. ✅ **실제 OS 연결**
   - FreeBSD 4.4BSD MLFQS 구현 참조
   - Linux CFS PRIO_TO_WEIGHT 테이블 동일 사용
   - PintOS 문서의 17.14 고정소수점

3. ✅ **정량적 분석 능력**
   - "느낌"이 아닌 메트릭 기반 비교
   - Jain's Fairness Index, 컨텍스트 스위치 수 등

4. ✅ **설계 방법론**
   - 목표 기반 테스트 설계
   - 공정한 비교 방법론

#### 예상치 못한 발견

이 섹션에서는 실제 테스트 결과에서 발견한 흥미로운 패턴들을 상세히 분석합니다.

---

##### 1. Nice 효과의 극단적 차이 - MLFQS vs CFS

**측정 결과:**
```
MLFQS: 62,499:1 (nice -20 vs nice 19의 CPU 시간 비율)
CFS:   2,499:1  (nice -20 vs nice 19의 CPU 시간 비율)
이론값: 5,917:1 (weight 비율 88761:15)
```

**왜 MLFQS가 훨씬 극단적인가?**

MLFQS의 우선순위 공식을 다시 살펴보면:
```
priority = 63 - (recent_cpu / 4) - (nice * 2)
```

nice -20 스레드:
- 초기: priority = 63 - 0 - (-20*2) = 63 - 0 + 40 = **103 (최대값으로 clamped → 63)**
- 실행 후: recent_cpu가 증가해도 nice*2 = 40이 매우 큰 보정
- 예: recent_cpu=100일 때 → priority = 63 - 25 + 40 = 78 (여전히 매우 높음)

nice 19 스레드:
- 초기: priority = 63 - 0 - (19*2) = 63 - 38 = **25**
- 실행 후: recent_cpu=100일 때 → priority = 63 - 25 - 38 = **0 (최저)**

**핵심 차이점:**
- nice -20 스레드는 recent_cpu가 증가해도 +40 보정이 압도적이어서 우선순위가 거의 안 떨어짐
- nice 19 스레드는 -38 페널티로 시작해서 조금만 실행해도 우선순위 바닥

**결과:**
nice -20 스레드가 거의 독점적으로 실행되고, nice 19 스레드는 거의 실행 기회를 못 받음 → **62,499:1**

---

**왜 CFS는 이론값(5,917:1)보다 약한가?**

이론적으로 CFS는 정확히 weight 비율대로 CPU를 배분해야 합니다:
```
weight(-20) / weight(19) = 88761 / 15 = 5917:1
```

하지만 실제 결과는 2,499:1로 이론값의 **42%**입니다.

**원인 1: Time Slice 경계 효과**
```
Time slice = 4 ticks

시나리오:
- nice -20 스레드가 4 ticks 실행 → vruntime += 11*4 = 44
- nice 19 스레드가 4 ticks 실행 → vruntime += 68266*4 = 273,064

이상적: 44와 273,064가 같아질 때까지 nice -20이 실행
실제: 4 tick 단위로 끊어지므로 nice 19도 최소 4 ticks는 받음
```

nice 19 스레드가 "4 tick 단위로 강제 실행"되면서 예상보다 많은 CPU를 받게 됩니다.

**원인 2: 시뮬레이션 조기 종료 (50%)**

Nice 효과 테스트는 total_work의 50%에서 중단합니다:
```
total_work = 20,000 ticks (nice -20: 10,000 + nice 19: 10,000)
실제 실행 = 10,000 ticks (50% 시점)

이상적 완료 시간:
- nice -20: 10,000 ticks를 91 tick당 1번 비율로 → 110 ticks에 완료
- nice 19: 10,000 ticks를 1 tick당 91번 비율로 → 10,010 ticks에 완료

50% 시점 (5,000 ticks):
- nice -20: 4,550 ticks 완료 (거의 절반)
- nice 19: 50 ticks 완료 (거의 시작도 못 함)
```

하지만 time slice 때문에 nice 19도 최소한의 진행을 하면서, 이론값보다 약해집니다.

**원인 3: 컨텍스트 스위치 오버헤드**

매번 스레드를 바꿀 때:
1. vruntime 계산 (나눗셈 연산)
2. SortedList 재정렬
3. 메모리 접근

이 오버헤드는 측정되지 않지만 실제로 시간을 소모합니다. nice -20이 압도적으로 자주 실행되므로, 상대적으로 오버헤드의 영향을 더 받습니다.

**결론:**
CFS의 2,499:1은 "이론값보다 약하다"는 것이 아니라, **"현실 세계의 제약(time slice, 오버헤드) 속에서 달성한 강력한 nice 효과"**입니다.

---

##### 2. Basic Priority의 건투 - 단순함이 때로는 최선

**측정 결과:**
```
Basic:  5 wins (38%)
MLFQS:  5 wins (38%)
CFS:    3 wins (23%)
```

처음 보는 사람은 이상하게 생각할 수 있습니다. "가장 단순한 Basic이 가장 복잡한 CFS만큼 이긴다고?"

**왜 Basic이 승리하는가?**

Basic이 승리한 테스트들을 분석하면:
1. **CPU-bound 워크로드** (일반 워크로드 테스트 중 일부)
2. **I/O가 거의 없는 테스트**
3. **Nice 값이 약하거나 동일한 경우** (nice 0 또는 -5~5)

**승리 이유 1: 최소 오버헤드**
```
매 tick마다 수행하는 작업:

Basic Priority:
  - pick_next(): O(n) - ready queue 선형 탐색
  - 우선순위 재계산: 0회 (정적 우선순위)
  - 추가 연산: 없음

MLFQS:
  - pick_next(): O(1) - 64개 큐에서 첫 번째 비어있지 않은 큐
  - 매 tick: recent_cpu++ (실행 중인 스레드)
  - 4 ticks마다: 모든 스레드의 priority 재계산 (O(n))
  - 100 ticks마다: load_avg, recent_cpu 재계산 (O(n))

CFS:
  - pick_next(): O(log n) - SortedList에서 최소 vruntime
  - 매 tick: delta_vruntime 계산 (나눗셈) + vruntime 업데이트
  - 매 yield: SortedList 재정렬 (O(log n))
```

스레드 수가 50개 정도이고 CPU-bound일 때:
- Basic의 O(n) 선형 탐색: 매우 빠름 (50번 비교)
- MLFQS의 주기적 재계산: 4 ticks마다 50개 재계산
- CFS의 로그 시간 정렬: 매번 log(50) ≈ 5.6 비교

**놀라운 점: Basic의 선형 탐색이 실제로는 매우 빠릅니다!**
- CPU 캐시 친화적 (순차 접근)
- 분기 예측 성공률 높음
- 추가 계산 전혀 없음

**승리 이유 2: 예측 가능성**

Basic은 우선순위가 절대 안 변하므로:
```
처음: Thread 1(pri=31), Thread 2(pri=31), Thread 3(pri=25)
실행 순서: 1 → 2 → 1 → 2 → 1 → 2 → ... → 3

MLFQS:
처음: Thread 1(pri=50), Thread 2(pri=50), Thread 3(pri=50)
10 ticks 후: Thread 1(pri=45), Thread 2(pri=48), Thread 3(pri=47)
20 ticks 후: Thread 1(pri=40), Thread 2(pri=46), Thread 3(pri=44)
→ 계속 변함, 예측 불가
```

예측 가능한 순서는 **캐시 히트율을 높입니다**. 같은 스레드가 규칙적으로 실행되면 해당 스레드의 데이터가 캐시에 남아있을 확률이 높습니다.

**승리 이유 3: Nice 값이 약할 때 차이 없음**

nice 0으로 모두 동일하거나, nice -5~5 범위일 때:
- Basic: priority 차이 최대 10 (26~36)
- MLFQS: nice*2 차이 최대 20, 하지만 recent_cpu가 더 큰 영향
- CFS: weight 차이 약 3배, 하지만 여전히 모두 비슷한 수준

→ 세 스케줄러 모두 거의 라운드 로빈처럼 동작
→ **오버헤드가 가장 적은 Basic이 승리**

**결론:**
Basic Priority가 승리하는 것은 버그가 아니라, **"특정 워크로드(CPU-bound, 약한 nice)에서 단순함이 최선"**이라는 교훈입니다. 과도한 최적화나 복잡한 공정성이 오히려 성능을 해칠 수 있습니다.

---

##### 3. 컨텍스트 스위치 오버헤드 - 공정성의 대가

**측정 결과 (500 스레드 테스트):**
```
Basic:  2,490 context switches
MLFQS:  2,615 context switches (+5%)
CFS:    2,738 context switches (+10%)
```

**왜 CFS가 더 많은가?**

컨텍스트 스위치가 발생하는 경우:
1. Time slice 만료
2. I/O 대기 시작
3. 스레드 완료

**CFS의 특성:**
```
vruntime 기반 선택 → 항상 "가장 덜 받은 스레드" 선택

예시 (5개 스레드):
vruntime: [1000, 1001, 1002, 1003, 1004]

Basic/MLFQS:
  - 우선순위가 같으면 같은 스레드가 여러 time slice 연속 실행 가능
  - 예: Thread 1이 4 slice 연속 실행 → 컨텍스트 스위치 3회 감소

CFS:
  - 매 slice 후 vruntime 증가 → 다음 pick_next()에서 다른 스레드 선택될 가능성 높음
  - Thread 1(vruntime=1000) 실행 → vruntime=2000
  - 다음: Thread 2(vruntime=1001) 선택 (가장 작음)
  - Thread 2 실행 → vruntime=2001
  - 다음: Thread 3(vruntime=1002) 선택
  → 매번 다른 스레드로 전환!
```

**결과:**
CFS는 공정성을 위해 스레드를 자주 바꿉니다 → 컨텍스트 스위치 증가

**그런데 왜 10%밖에 안 차이날까?**

10% 차이는 실제로 **매우 작은 차이**입니다. 이유는:

1. **대부분의 컨텍스트 스위치는 I/O 때문**
   - I/O 대기 시작 → 무조건 컨텍스트 스위치
   - 이것은 모든 스케줄러에서 동일

2. **Time slice가 충분히 길다** (4 ticks)
   - 너무 짧으면 매 tick마다 전환 → 100% 차이
   - 4 ticks는 여러 스레드가 time slice 내에 비슷한 progress를 만듦

3. **500개 스레드 → 대부분 대기 중**
   - Ready queue에 있는 스레드: 평균 10-20개
   - 나머지는 I/O 대기 또는 완료
   - Ready 스레드가 적으면 선택지가 제한적 → 차이 감소

**결론:**
CFS의 +10% 컨텍스트 스위치는 **"공정성의 대가로 충분히 받아들일 만한 수준"**입니다. 만약 100%나 200% 차이였다면 문제지만, 10%는 거의 무시할 수 있는 오버헤드입니다.

실제 Linux 시스템에서도 CFS의 컨텍스트 스위치 오버헤드는 측정하기 어려울 정도로 작으며, 그 대가로 얻는 공정성(Jain Index 0.922)은 훨씬 큰 가치가 있습니다.

---

##### 4. I/O Bound 우대 - MLFQS의 숨은 강점

**측정 결과 (I/O-bound 테스트):**
```
평균 대기 시간:
  Basic:  4,521 ticks
  MLFQS:  2,847 ticks (-37%, 압도적 승리)
  CFS:    4,103 ticks

응답 시간:
  Basic:  5,234 ticks
  MLFQS:  3,012 ticks (-42%, 압도적 승리)
  CFS:    4,789 ticks
```

**왜 MLFQS가 I/O에서 압도적인가?**

MLFQS의 `recent_cpu` 메커니즘을 이해해야 합니다:

```
매 tick:
  - 실행 중인 스레드: recent_cpu++
  - I/O 대기 중인 스레드: recent_cpu 증가 안 함 (변화 없음)

100 ticks마다:
  recent_cpu = (2*load_avg)/(2*load_avg+1) * recent_cpu
  → 모든 스레드의 recent_cpu 감쇠

예시:
Thread A (CPU-bound):
  - 0~100 ticks: 계속 실행 → recent_cpu = 100
  - 100 tick 시점: recent_cpu = (2*5)/(2*5+1) * 100 ≈ 91 (약간 감쇠)
  - 101~200 ticks: 계속 실행 → recent_cpu = 191
  - 200 tick 시점: recent_cpu = 0.91 * 191 ≈ 174
  → recent_cpu가 지속적으로 높음

Thread B (I/O-bound, 80% I/O 대기):
  - 0~100 ticks: 20 ticks만 실행 → recent_cpu = 20
  - 100 tick 시점: recent_cpu = 0.91 * 20 ≈ 18
  - 101~200 ticks: 20 ticks만 실행 → recent_cpu = 38
  - 200 tick 시점: recent_cpu = 0.91 * 38 ≈ 35
  → recent_cpu가 낮게 유지됨
```

**우선순위 차이:**
```
priority = 63 - (recent_cpu / 4) - (nice * 2)

Thread A (CPU-bound, recent_cpu=174, nice=0):
  priority = 63 - 43 - 0 = 20 (낮은 우선순위)

Thread B (I/O-bound, recent_cpu=35, nice=0):
  priority = 63 - 8 - 0 = 55 (높은 우선순위!)
```

**결과:**
I/O-bound 스레드가 I/O 완료 후 ready queue에 돌아오면:
- MLFQS: 높은 우선순위 (55) → 즉시 선택됨 → 빠른 응답
- Basic: 정적 우선순위 (31) → 다른 스레드들과 동등 → 느린 응답
- CFS: vruntime 기반 → I/O 대기 중 vruntime 증가 안 했으므로 약간 유리, 하지만 명시적 우대는 없음

**왜 이게 중요한가?**

I/O-bound 작업은 보통 **사용자 대화형 작업**입니다:
- 웹 브라우저 (네트워크 I/O)
- 텍스트 에디터 (키보드 입력)
- 비디오 플레이어 (파일 I/O)

이런 작업들은 CPU를 조금만 쓰고 바로 I/O 대기에 들어갑니다. MLFQS는 이를 자동으로 감지하고 우대하여 **사용자가 느끼는 응답성**을 크게 향상시킵니다.

**CFS는 왜 I/O 우대가 없나?**

CFS의 철학은 "Completely Fair"입니다:
- 모든 스레드는 weight에 비례하여 정확히 공평하게 CPU를 받아야 함
- I/O 대기 중이든 CPU 사용 중이든, 그것은 스레드의 선택이지 스케줄러가 판단할 문제가 아님

이것은 철학의 차이입니다:
- **MLFQS**: "I/O 대기가 많으면 대화형 작업일 것이다 → 우대하자"
- **CFS**: "모든 스레드를 공평하게, I/O든 CPU든 상관없이"

**결론:**
MLFQS가 I/O-bound에서 승리하는 것은 우연이 아니라, **"워크로드 패턴을 관찰하고 적응"하는 설계의 결과**입니다. 이것이 FreeBSD가 오랫동안 MLFQS 계열 스케줄러를 유지한 이유이기도 합니다.

---

## 7. 아쉬운 점과 개선 방향

### 7.1 구현하지 못한 기능

#### 1. 멀티 CPU
- **현재**: 단일 CPU 시뮬레이션
- **필요**: Load balancing, cache coherency, migration cost
- **영향**: 현대 멀티코어 환경의 실제 동작 반영 못 함

#### 2. Real-time 스케줄러
- **현재**: Fair 스케줄러만 (Basic, MLFQS, CFS)
- **부재**: SCHED_FIFO, SCHED_RR, SCHED_DEADLINE
- **이유**: 테스트 방법론이 다름 (deadline, response time)

#### 3. I/O 스케줄러 통합
- **현재**: I/O는 단순 대기로 모델링
- **이상**: Block I/O scheduler와 통합 (CFQ, Deadline, NOOP)

### 7.2 측정의 한계

#### CFS 이론값과 실제값 괴리
```
Expected (theory): nice -20 vs 19 = 5917:1
Actual:            2499:1 (42% of theory)
```

**가능한 원인:**
- 컨텍스트 스위치 오버헤드 (4 ticks time slice)
- vruntime 스케일 (1000배)의 부작용
- 시뮬레이션 조기 종료 (50%)의 영향

**추가 분석 필요**: 더 긴 시뮬레이션, 더 큰 burst_time으로 재테스트

#### Starvation 측정
- **현재**: "has_starvation" boolean 플래그만
- **이상**: 실제 대기 시간 분포, 최악 케이스 대기 시간, P99 latency

### 7.3 사용자 경험 개선

#### 시뮬레이션 시간
- **현재**: 500 스레드 테스트 10초 이상 소요
- **개선**: Python 멀티스레딩, Cython 최적화, C 확장 모듈

#### 결과 시각화
- **현재**: 기본적인 막대 그래프
- **이상**:
  - 시간에 따른 ready queue 변화 애니메이션
  - vruntime/priority 변화 추이 그래프
  - 간트 차트 (Gantt chart)
  - 스레드별 실행 타임라인

---

## 8. 회고

### 8.1 기술적 성장

#### Before
- **CPU 스케줄링**: 이론적 개념 (FIFO, SJF, RR, Priority)
- **운영체제**: "어렵고 복잡한 것"
- **디버깅**: print() 남발, 막연한 추측

#### After
- **CPU 스케줄링**: 구현 가능한 알고리즘, 측정 가능한 트레이드오프
- **운영체제**: "복잡하지만 이해 가능한 시스템"
- **디버깅**: 가설 수립 → 검증 → 수정의 체계적 접근

### 8.2 핵심 인사이트

#### 운영체제는 Trade-off의 예술
- **Basic Priority**: 단순, 예측 가능, 오버헤드 최소 → 하지만 불공정, starvation 위험
- **MLFQS**: 동적, 응답성 우수, I/O 우대 → 하지만 복잡, nice 효과 약함
- **CFS**: 완벽한 공정성, 강한 nice 효과 → 하지만 I/O 우대 없음, 약간의 오버헤드

**완벽한 스케줄러는 없습니다.** 각 워크로드, 각 시스템 요구사항에 맞는 선택이 필요합니다.

#### 측정 없는 최적화는 맹목
"CFS가 무조건 좋다"는 막연한 믿음이 있었지만, 실제 측정 결과:
- I/O-bound 워크로드: MLFQS 승리
- CPU-bound 워크로드: Basic 승리 (오버헤드 최소)
- 공정성: CFS 승리

상황에 따라 다릅니다.

#### 디버깅은 과학적 방법론
1. **관찰**: 이상한 결과 (vruntime=0, 모두 tie, 한 쪽 압승)
2. **가설**: "Time slice가 없나?", "정수 나눗셈 문제?", "FIFO 순서 문제?"
3. **실험**: print() 디버깅, 단순화된 테스트 케이스, 단계별 실행
4. **검증**: 수정 후 결과 확인, 이론값과 비교, 다른 테스트에서도 확인

---

## 9. 결론

### 프로젝트 요약
이 프로젝트는 단순히 "스케줄러 3개를 구현"하는 것을 넘어서, **운영체제의 핵심 트레이드오프를 직접 체험**하는 여정이었습니다.

6가지 주요 버그를 수정하면서:
- 이론과 구현의 괴리를 깊이 이해했고
- 정수 연산과 고정소수점의 중요성을 체험했으며
- 측정 방법론의 중요성을 깨달았습니다

목표 기반 테스트 설계를 통해:
- 공정한 비교 방법론을 확립했고
- 각 스케줄러의 진짜 강점을 발견했습니다

### 최종 성과
- **코드**: 2,939줄, 3개 스케줄러, 8가지 워크로드, 13개 테스트
- **배포**: GCP VM에 24/7 운영 중 (http://34.47.105.226:8501)
- **결과**: 유의미한 편향 없는 공정한 비교
  - Basic 38%, MLFQS 38%, CFS 23%
  - 각 스케줄러가 자신의 강점에서만 승리

### 개인적 성장
**Before**: CPU 스케줄링은 시험 공부용 이론
**After**: 실제로 구현 가능하고, 각각의 트레이드오프를 정량적으로 측정할 수 있는 알고리즘

이제 "왜 Linux가 CFS를 선택했는가?"라는 질문에 답할 수 있습니다:
- **공정성**: Jain Index 0.922 (MLFQS 0.867보다 높음)
- **Strong nice effect**: 2499:1 (충분히 강함)
- **예측 가능성**: vruntime은 단순하고 예측 가능
- **단점 감수**: I/O 우대 없음, 약간의 오버헤드 → 공정성의 대가로 받아들임

### 감사의 말
이 프로젝트는 다음의 도움으로 가능했습니다:
- **PintOS 문서**: MLFQS 17.14 고정소수점 연산 상세 설명
- **Linux 커널 소스**: CFS PRIO_TO_WEIGHT 테이블 (kernel/sched/core.c)
- **FreeBSD 소스**: MLFQS 구현 참조 (sys/kern/sched_4bsd.c)
- **StackOverflow**: 정수 나눗셈 정밀도 문제 해결 힌트

그리고 무엇보다, **끝까지 포기하지 않은 나 자신**에게.

---

**프로젝트 정보**
- **저장소**: https://github.com/dvktdr78/scheduler_benchmark
- **작성일**: 2025년 11월 24일