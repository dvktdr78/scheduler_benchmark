"""
스케줄러 벤치마크 테스트 정의 (Goal-based)

설계 원칙:
  - 테스트는 "목표/개념"으로 정의 (scheduler-neutral)
  - 각 테스트마다 비교할 스케줄러 명시
  - 각 스케줄러가 자신의 방식으로 목표 달성
"""

from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class BenchmarkTest:
    """벤치마크 테스트 정의"""
    test_id: str
    name: str
    goal: str  # 테스트 목표
    workload_type: str  # workload generator 타입
    thread_count: int
    schedulers: List[str]  # 비교할 스케줄러 리스트
    primary_metric: str  # 주요 측정 지표
    description: str  # 상세 설명


# ========== 테스트 정의 ==========

# 1. 일반 워크로드 성능 비교 (3-way)
TEST_GENERAL_MIXED = BenchmarkTest(
    test_id="general_mixed",
    name="일반 혼합 워크로드",
    goal="다양한 작업이 혼재된 일반 시스템에서의 전반적 성능",
    workload_type="mixed",
    thread_count=50,
    schedulers=["basic", "mlfqs", "cfs"],
    primary_metric="avg_wait",
    description="""
    Mixed 워크로드 (Nice -5~5):
      - CPU burst: 100-500 ticks
      - I/O 빈도: 0-500 ticks
      - I/O 지속: 0-200 ticks

    목표: 일반적인 멀티태스킹 환경 시뮬레이션
    비교: 3개 스케줄러 모두 비교 (각자의 방식으로 최적화)
    """
)

TEST_GENERAL_CPU = BenchmarkTest(
    test_id="general_cpu",
    name="CPU 집약적 워크로드",
    goal="순수 연산 작업의 처리 효율",
    workload_type="cpu_bound",
    thread_count=50,
    schedulers=["basic", "mlfqs", "cfs"],
    primary_metric="avg_turnaround",
    description="""
    CPU-bound 워크로드 (Nice 0):
      - CPU burst: 300-800 ticks
      - I/O 없음

    목표: 과학 계산, 컴파일 등 CPU 집약 작업
    비교: 순수 알고리즘 효율성 비교 (Nice 0으로 통일)
    """
)

TEST_GENERAL_IO = BenchmarkTest(
    test_id="general_io",
    name="I/O 집약적 워크로드",
    goal="Interactive 애플리케이션의 응답성",
    workload_type="io_bound",
    thread_count=50,
    schedulers=["basic", "mlfqs", "cfs"],
    primary_metric="avg_wait",
    description="""
    I/O-bound 워크로드 (Nice 0):
      - CPU burst: 50-200 ticks (짧음)
      - I/O 빈도: 50-200 ticks (잦음)
      - I/O 지속: 50-150 ticks

    목표: 사용자 인터페이스, 에디터 등 interactive 작업
    비교: Interactive 최적화 능력 (MLFQS/CFS의 장점 예상)
    """
)

# 2. 실제 응용 패턴 (3-way)
TEST_APP_WEB = BenchmarkTest(
    test_id="app_web",
    name="웹 서버 패턴",
    goal="웹 서버의 요청 처리 패턴 시뮬레이션",
    workload_type="web_server",
    thread_count=50,
    schedulers=["basic", "mlfqs", "cfs"],
    primary_metric="avg_turnaround",
    description="""
    웹 서버 패턴 (Nice 0):
      - 90% 짧은 요청: 10-50 ticks
      - 10% 긴 요청: 200-600 ticks

    목표: Nginx, Apache 등 웹 서버 시뮬레이션
    비교: 짧은 요청 우선 처리 능력
    """
)

TEST_APP_DATABASE = BenchmarkTest(
    test_id="app_database",
    name="데이터베이스 패턴",
    goal="데이터베이스의 쿼리/트랜잭션 처리",
    workload_type="database",
    thread_count=50,
    schedulers=["basic", "mlfqs", "cfs"],
    primary_metric="avg_turnaround",
    description="""
    데이터베이스 패턴 (Nice 0):
      - 70% SELECT 쿼리: 30-150 ticks
      - 30% 트랜잭션: 200-600 ticks

    목표: PostgreSQL, MySQL 등 DB 워크로드
    비교: 짧은 쿼리와 긴 트랜잭션 혼합 처리
    """
)

TEST_APP_BATCH = BenchmarkTest(
    test_id="app_batch",
    name="배치 처리 패턴",
    goal="대용량 배치 작업의 처리량",
    workload_type="batch",
    thread_count=50,
    schedulers=["basic", "mlfqs", "cfs"],
    primary_metric="avg_turnaround",
    description="""
    배치 처리 패턴 (Nice 0):
      - CPU burst: 400-800 ticks
      - 순차 도착 (i * 10 ticks)

    목표: 대용량 데이터 처리, 빌드 시스템
    비교: 순차 배치 작업 처리 효율
    """
)

TEST_APP_GAMING = BenchmarkTest(
    test_id="app_gaming",
    name="게임/실시간 패턴",
    goal="실시간 응답이 필요한 시스템",
    workload_type="gaming",
    thread_count=50,
    schedulers=["basic", "mlfqs", "cfs"],
    primary_metric="avg_wait",
    description="""
    게임 패턴 (Nice 0):
      - 30% 렌더링: 50-150 ticks, 16ms 간격 도착
      - 70% AI/물리: 200-500 ticks

    목표: 60 FPS 유지, 실시간 반응성
    비교: 짧은 작업 우선 처리 능력
    """
)

# 3. 공정성 테스트 (MLFQS vs CFS만)
TEST_FAIRNESS_CPU = BenchmarkTest(
    test_id="fairness_cpu",
    name="공정성: CPU 시간 배분",
    goal="모든 스레드에게 공정한 CPU 시간 배분",
    workload_type="cpu_bound",
    thread_count=50,
    schedulers=["mlfqs", "cfs"],  # Basic 제외
    primary_metric="fairness",
    description="""
    CPU-bound 워크로드 (Nice 0):
      - CPU burst: 300-800 ticks
      - I/O 없음

    목표: Starvation 방지, 공정한 CPU 배분
    비교: MLFQS vs CFS (Basic은 starvation 위험으로 제외)
    메트릭: Jain's Fairness Index (1.0에 가까울수록 공정)
    """
)

TEST_FAIRNESS_MIXED = BenchmarkTest(
    test_id="fairness_mixed",
    name="공정성: 혼합 워크로드",
    goal="다양한 특성의 스레드 간 공정성",
    workload_type="mixed",
    thread_count=50,
    schedulers=["mlfqs", "cfs"],  # Basic 제외
    primary_metric="fairness",
    description="""
    Mixed 워크로드 (Nice -5~5):
      - CPU burst: 100-500 ticks
      - I/O 다양

    목표: CPU/I/O 혼합 시 공정성
    비교: MLFQS vs CFS (동적 조정 능력)
    """
)

# 4. Nice 효과 테스트 (MLFQS vs CFS만)
TEST_NICE_EFFECT = BenchmarkTest(
    test_id="nice_effect",
    name="Nice 값 효과 검증",
    goal="Nice 값에 따른 우선순위/CPU 시간 차이",
    workload_type="extreme_nice",
    thread_count=50,
    schedulers=["mlfqs", "cfs"],  # Basic 제외
    primary_metric="cpu_time_ratio",
    description="""
    Extreme Nice 워크로드:
      - 절반: Nice -20 (최고 우선순위)
      - 절반: Nice 19 (최저 우선순위)
      - CPU burst: 10,000 ticks (동일, 긴 시간으로 nice 효과 측정)

    목표: Nice 값의 실제 효과 측정
    비교: MLFQS vs CFS (각자의 nice 해석 방식)
    예상: CFS는 ~4000:1 비율, MLFQS는 더 약한 차이

    NOTE: Burst time이 길어야 vruntime/priority 차이가 CPU 시간 차이로 나타남
    """
)

# 5. 확장성 테스트 (스레드 수 변화)
TEST_SCALABILITY_10 = BenchmarkTest(
    test_id="scalability_10",
    name="확장성: 10 스레드",
    goal="적은 스레드 수에서의 오버헤드",
    workload_type="mixed",
    thread_count=10,
    schedulers=["basic", "mlfqs", "cfs"],
    primary_metric="context_switches",
    description="""
    Mixed 워크로드, 10 스레드
    목표: 스케줄러 오버헤드 측정
    """
)

TEST_SCALABILITY_100 = BenchmarkTest(
    test_id="scalability_100",
    name="확장성: 100 스레드",
    goal="많은 스레드 수에서의 성능",
    workload_type="mixed",
    thread_count=100,
    schedulers=["basic", "mlfqs", "cfs"],
    primary_metric="avg_wait",
    description="""
    Mixed 워크로드, 100 스레드
    목표: 고부하 상황에서의 스케일링
    """
)

TEST_SCALABILITY_500 = BenchmarkTest(
    test_id="scalability_500",
    name="확장성: 500 스레드",
    goal="극한 부하에서의 동작",
    workload_type="mixed",
    thread_count=500,
    schedulers=["basic", "mlfqs", "cfs"],
    primary_metric="avg_wait",
    description="""
    Mixed 워크로드, 500 스레드
    목표: 극한 상황에서의 안정성
    """
)


# ========== 테스트 카테고리 ==========

TEST_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "일반 워크로드": {
        "description": "다양한 일반적인 워크로드 패턴 (3-way 비교)",
        "tests": [TEST_GENERAL_MIXED, TEST_GENERAL_CPU, TEST_GENERAL_IO]
    },
    "실제 응용": {
        "description": "실제 시스템 패턴 시뮬레이션 (3-way 비교)",
        "tests": [TEST_APP_WEB, TEST_APP_DATABASE, TEST_APP_BATCH, TEST_APP_GAMING]
    },
    "공정성": {
        "description": "CPU 시간 배분의 공정성 (MLFQS vs CFS)",
        "tests": [TEST_FAIRNESS_CPU, TEST_FAIRNESS_MIXED]
    },
    "Nice 효과": {
        "description": "Nice 값의 실제 효과 검증 (MLFQS vs CFS)",
        "tests": [TEST_NICE_EFFECT]
    },
    "확장성": {
        "description": "스레드 수에 따른 성능 변화 (3-way 비교)",
        "tests": [TEST_SCALABILITY_10, TEST_SCALABILITY_100, TEST_SCALABILITY_500]
    }
}


# ========== 모든 테스트 리스트 ==========

ALL_TESTS = [
    TEST_GENERAL_MIXED, TEST_GENERAL_CPU, TEST_GENERAL_IO,
    TEST_APP_WEB, TEST_APP_DATABASE, TEST_APP_BATCH, TEST_APP_GAMING,
    TEST_FAIRNESS_CPU, TEST_FAIRNESS_MIXED,
    TEST_NICE_EFFECT,
    TEST_SCALABILITY_10, TEST_SCALABILITY_100, TEST_SCALABILITY_500
]


def get_test_by_id(test_id: str) -> BenchmarkTest:
    """테스트 ID로 테스트 찾기"""
    for test in ALL_TESTS:
        if test.test_id == test_id:
            return test
    raise ValueError(f"Unknown test_id: {test_id}")


def get_tests_by_category(category: str) -> List[BenchmarkTest]:
    """카테고리별 테스트 리스트"""
    return TEST_CATEGORIES.get(category, {}).get("tests", [])
