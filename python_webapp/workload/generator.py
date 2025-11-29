"""
워크로드 생성 (Level 2 확장)

Level 2 특징:
  - 9가지 워크로드 (기본 3개 + 실제 응용 4개 + 극단 테스트 2개)
  - 스레드 수 변화 지원 (10, 50, 100, 500)
  - 실제 시스템 패턴 모방
  - Random seed 고정 (재현성)
"""
import random
from typing import List, Optional
from scheduler.thread import Thread, ThreadStatus

# 기본 설정
DEFAULT_WORKLOAD = "mixed"
DEFAULT_THREAD_COUNT = 10
DEFAULT_SEED = 42


def generate_default_workload(seed: Optional[int] = DEFAULT_SEED) -> List[Thread]:
    """기본 워크로드 (Mixed, 10 스레드)"""
    return generate_mixed(DEFAULT_THREAD_COUNT, seed=seed)


# ========== Level 1: 기본 워크로드 (3개) ==========

def generate_mixed(count: int, seed: Optional[int] = None) -> List[Thread]:
    """
    Mixed 워크로드

    특성: 다양한 burst, 일부 I/O, Nice -5~5 (약한 우선순위 차이)
    용도: 일반적인 시스템
    """
    if seed is not None:
        random.seed(seed)

    threads = []
    for i in range(count):
        tid = i + 1
        burst = random.randint(100, 500)  # 줄임: 2000-8000 → 100-500
        io_freq = random.randint(0, 500)
        io_dur = random.randint(0, 200)
        nice = random.randint(-5, 5)  # 약한 nice 차이 (원래 -10~10)

        thread = Thread(
            tid=tid,
            name=f"mixed_{tid}",
            arrival_time=random.randint(0, 100),
            burst_time=burst,
            remaining_time=burst,
            io_frequency=io_freq,
            io_duration=io_dur,
            nice=nice,
            status=ThreadStatus.READY
        )
        threads.append(thread)
    return threads


def generate_cpu_bound(count: int, seed: Optional[int] = None) -> List[Thread]:
    """
    CPU-bound 워크로드

    특성: 긴 CPU burst, I/O 없음, Nice 0 (순수 알고리즘 비교)
    용도: 과학 계산, 컴파일

    NOTE: Nice 0으로 통일하여 순수 스케줄링 알고리즘 효율성 비교
          공정성 테스트에서도 동일 가중치로 측정
    """
    if seed is not None:
        random.seed(seed)

    threads = []
    for i in range(count):
        burst = random.randint(300, 800)  # 줄임: 5000-10000 → 300-800
        thread = Thread(
            tid=i+1,
            name=f"cpu_{i+1}",
            arrival_time=random.randint(0, 50),
            burst_time=burst,
            remaining_time=burst,
            io_frequency=0,
            nice=0,  # Nice 0 - 순수 알고리즘 비교
            status=ThreadStatus.READY
        )
        threads.append(thread)
    return threads


def generate_io_bound(count: int, seed: Optional[int] = None) -> List[Thread]:
    """
    I/O-bound 워크로드 (CPU-bound 경쟁자 포함)

    특성: 60% I/O-bound + 40% CPU-bound 혼합
    용도: MLFQS의 I/O 우대 능력 테스트

    NOTE: CPU-bound 경쟁자가 있어야 MLFQS의 I/O 우대가 드러남
          I/O 스레드는 매우 잦은 I/O (10-30 ticks 간격)
          CPU 스레드는 긴 burst (500-1000 ticks)로 자원 경쟁 극대화
    """
    if seed is not None:
        random.seed(seed)

    threads = []
    io_count = int(count * 0.6)  # 60% I/O-bound
    cpu_count = count - io_count  # 40% CPU-bound (경쟁 강화)

    # I/O-bound 스레드 (짧은 burst, 매우 잦은 I/O)
    for i in range(io_count):
        burst = random.randint(30, 100)  # 더 짧은 burst
        thread = Thread(
            tid=i+1,
            name=f"io_{i+1}",
            arrival_time=random.randint(0, 100),
            burst_time=burst,
            remaining_time=burst,
            io_frequency=random.randint(10, 30),  # 매우 잦은 I/O (10-30 tick마다)
            io_duration=random.randint(50, 150),
            nice=0,
            status=ThreadStatus.READY
        )
        threads.append(thread)

    # CPU-bound 경쟁자 (긴 burst, I/O 없음)
    for i in range(cpu_count):
        burst = random.randint(500, 1000)  # 더 긴 burst
        thread = Thread(
            tid=io_count + i + 1,
            name=f"cpu_competitor_{i+1}",
            arrival_time=random.randint(0, 50),
            burst_time=burst,
            remaining_time=burst,
            io_frequency=0,  # I/O 없음
            io_duration=0,
            nice=0,
            status=ThreadStatus.READY
        )
        threads.append(thread)

    return threads


# ========== Level 2: 실제 응용 워크로드 (5개) ==========

def generate_web_server(count: int, seed: Optional[int] = None) -> List[Thread]:
    """
    웹 서버 패턴

    특성: 90% 짧은 요청 (Nice -5), 10% 긴 요청 (Nice 5)
    실제: Nginx, Apache 패턴 모방 - 짧은 요청 우선 처리

    NOTE: Nice 차이로 짧은 요청 우선 처리 능력 테스트
    """
    if seed is not None:
        random.seed(seed)

    threads = []

    # 90% short requests (10-50 ticks) - Nice -5 (higher priority)
    short_count = int(count * 0.9)
    for i in range(short_count):
        burst = random.randint(10, 50)
        thread = Thread(
            tid=i+1,
            name=f"web_short_{i+1}",
            arrival_time=random.randint(0, 200),  # 요청 도착 분산
            burst_time=burst,
            remaining_time=burst,
            io_frequency=random.randint(20, 50),  # DB/파일 읽기
            io_duration=random.randint(10, 30),
            nice=-5,  # 짧은 요청 우선
            status=ThreadStatus.READY
        )
        threads.append(thread)

    # 10% long requests (200-600 ticks) - Nice 5 (lower priority)
    long_count = count - short_count
    for i in range(long_count):
        burst = random.randint(200, 600)
        thread = Thread(
            tid=short_count + i + 1,
            name=f"web_long_{i+1}",
            arrival_time=random.randint(0, 200),
            burst_time=burst,
            remaining_time=burst,
            io_frequency=random.randint(100, 300),
            io_duration=random.randint(50, 100),
            nice=5,  # 긴 요청 낮은 우선순위
            status=ThreadStatus.READY
        )
        threads.append(thread)

    return threads


def generate_database(count: int, seed: Optional[int] = None) -> List[Thread]:
    """
    데이터베이스 패턴

    특성: 짧은 쿼리 + 긴 트랜잭션 혼합
    실제: PostgreSQL, MySQL 패턴
    """
    if seed is not None:
        random.seed(seed)

    threads = []

    # 70% 짧은 SELECT 쿼리
    select_count = int(count * 0.7)
    for i in range(select_count):
        burst = random.randint(30, 150)
        thread = Thread(
            tid=i+1,
            name=f"db_select_{i+1}",
            arrival_time=random.randint(0, 100),
            burst_time=burst,
            remaining_time=burst,
            io_frequency=random.randint(10, 50),  # 디스크 I/O
            io_duration=random.randint(20, 80),
            nice=0,  # Nice 0으로 통일
            status=ThreadStatus.READY
        )
        threads.append(thread)

    # 30% 긴 트랜잭션/JOIN
    tx_count = count - select_count
    for i in range(tx_count):
        burst = random.randint(200, 600)
        thread = Thread(
            tid=select_count + i + 1,
            name=f"db_tx_{i+1}",
            arrival_time=random.randint(0, 100),
            burst_time=burst,
            remaining_time=burst,
            io_frequency=random.randint(50, 200),
            io_duration=random.randint(100, 300),
            nice=0,  # Nice 0으로 통일
            status=ThreadStatus.READY
        )
        threads.append(thread)

    return threads


def generate_batch_processing(count: int, seed: Optional[int] = None) -> List[Thread]:
    """
    배치 처리 패턴

    특성: 모두 CPU-heavy, 비슷한 우선순위
    실제: 대용량 데이터 처리, 컴파일
    """
    if seed is not None:
        random.seed(seed)

    threads = []
    for i in range(count):
        burst = random.randint(400, 800)
        thread = Thread(
            tid=i+1,
            name=f"batch_{i+1}",
            arrival_time=i * 10,  # 순차 도착
            burst_time=burst,
            remaining_time=burst,
            io_frequency=0,  # CPU-only
            io_duration=0,
            nice=0,  # Nice 0으로 통일
            status=ThreadStatus.READY
        )
        threads.append(thread)
    return threads


def generate_gaming(count: int, seed: Optional[int] = None) -> List[Thread]:
    """
    게임/실시간 시스템 패턴

    특성: 고우선순위 (렌더링 Nice=-10) vs 저우선순위 (AI Nice=10)
    실제: 60 FPS 유지 필요 - 렌더링이 AI보다 우선

    NOTE: Nice 차이가 있어야 MLFQS/CFS가 렌더링을 우선 처리
    """
    if seed is not None:
        random.seed(seed)

    threads = []

    # 30% 고우선순위 (렌더링, 입력) - Nice -10
    high_count = int(count * 0.3)
    for i in range(high_count):
        burst = random.randint(50, 150)
        thread = Thread(
            tid=i+1,
            name=f"game_render_{i+1}",
            arrival_time=i * 16,  # 60 FPS = 16ms 간격
            burst_time=burst,
            remaining_time=burst,
            io_frequency=random.randint(5, 20),  # GPU I/O
            io_duration=random.randint(10, 30),
            nice=-10,  # 고우선순위 렌더링
            status=ThreadStatus.READY
        )
        threads.append(thread)

    # 70% 저우선순위 (AI, 물리 연산) - Nice 10
    low_count = count - high_count
    for i in range(low_count):
        burst = random.randint(200, 500)
        thread = Thread(
            tid=high_count + i + 1,
            name=f"game_ai_{i+1}",
            arrival_time=random.randint(0, 100),
            burst_time=burst,
            remaining_time=burst,
            io_frequency=0,
            io_duration=0,
            nice=10,  # 저우선순위 AI
            status=ThreadStatus.READY
        )
        threads.append(thread)

    return threads


def generate_extreme_nice(count: int, seed: Optional[int] = None) -> List[Thread]:
    """
    Nice 값 극단 테스트

    특성: Nice -20 vs Nice 19 대비
    용도: Nice 효과 검증

    NOTE: Burst time 2,000 → 총 100,000 ticks (50개 기준)
          MLFQS 성능 고려하여 축소, 여전히 nice 효과 측정 가능
    """
    if seed is not None:
        random.seed(seed)

    threads = []
    half = count // 2

    # 절반: Nice -20 (최고 우선순위)
    for i in range(half):
        thread = Thread(
            tid=i+1,
            name=f"nice_minus20_{i+1}",
            arrival_time=random.randint(0, 50),
            burst_time=2000,  # 10,000 → 2,000 (MLFQS 성능 고려)
            remaining_time=2000,
            io_frequency=0,
            io_duration=0,
            nice=-20,
            status=ThreadStatus.READY
        )
        threads.append(thread)

    # 절반: Nice 19 (최저 우선순위)
    for i in range(count - half):
        thread = Thread(
            tid=half + i + 1,
            name=f"nice_19_{i+1}",
            arrival_time=random.randint(0, 50),
            burst_time=2000,  # 10,000 → 2,000 (MLFQS 성능 고려)
            remaining_time=2000,
            io_frequency=0,
            io_duration=0,
            nice=19,
            status=ThreadStatus.READY
        )
        threads.append(thread)

    return threads


def generate_extreme_nice_fairness(count: int, seed: Optional[int] = None) -> List[Thread]:
    """
    Nice 값 극단 테스트 (공정성 측정용, 짧은 burst)

    목적: 기본 extreme_nice보다 짧은 burst로, 제한된 시뮬레이션 시간 내 일부 스레드가 완료되도록 함.
    """
    if seed is not None:
        random.seed(seed)

    threads = []
    half = count // 2

    # 절반: Nice -20 (최고 우선순위)
    for i in range(half):
        burst = 1000
        thread = Thread(
            tid=i+1,
            name=f"nice_minus20_fair_{i+1}",
            arrival_time=random.randint(0, 50),
            burst_time=burst,
            remaining_time=burst,
            io_frequency=0,
            io_duration=0,
            nice=-20,
            status=ThreadStatus.READY
        )
        threads.append(thread)

    # 절반: Nice 19 (최저 우선순위)
    for i in range(count - half):
        burst = 1000
        thread = Thread(
            tid=half + i + 1,
            name=f"nice_19_fair_{i+1}",
            arrival_time=random.randint(0, 50),
            burst_time=burst,
            remaining_time=burst,
            io_frequency=0,
            io_duration=0,
            nice=19,
            status=ThreadStatus.READY
        )
        threads.append(thread)

    return threads


# ========== 워크로드 팩토리 ==========

WORKLOAD_GENERATORS = {
    "mixed": generate_mixed,
    "cpu_bound": generate_cpu_bound,
    "io_bound": generate_io_bound,
    "web_server": generate_web_server,
    "database": generate_database,
    "batch": generate_batch_processing,
    "gaming": generate_gaming,
    "extreme_nice": generate_extreme_nice,
    "extreme_nice_fairness": generate_extreme_nice_fairness,
}


def generate_workload(workload_type: str, count: int, seed: Optional[int] = None) -> List[Thread]:
    """
    워크로드 생성 팩토리

    Args:
        workload_type: 워크로드 종류
        count: 스레드 수
        seed: Random seed

    Returns:
        스레드 리스트
    """
    generator = WORKLOAD_GENERATORS.get(workload_type)
    if generator is None:
        raise ValueError(f"Unknown workload: {workload_type}")

    return generator(count, seed)
