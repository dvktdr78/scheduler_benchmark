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
    max_ticks: int = 10000  # 시뮬레이션 최대 시간 (기본값 10000)


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
    비교: 순수 스케줄링 알고리즘 효율성 비교
    """,
    max_ticks=35000  # 총 burst ~27,500의 1.3배
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
    I/O-bound 워크로드 (60% I/O + 40% CPU 경쟁자):
      - I/O 스레드: burst 30-100, I/O 10-30 tick마다
      - CPU 경쟁자: burst 500-1000, I/O 없음

    목표: I/O-bound vs CPU-bound 경쟁 상황
    비교: I/O 우대 능력 (MLFQS의 장점 예상)
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
    웹 서버 패턴 (Nice -5 vs 5):
      - 90% 짧은 요청: 10-50 ticks (Nice -5)
      - 10% 긴 요청: 200-600 ticks (Nice 5)

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
    """,
    max_ticks=35000  # 총 burst ~30,000 + 순차 도착
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
    게임 패턴 (Nice -10 vs 10):
      - 30% 렌더링: 50-150 ticks, 16ms 간격 (Nice -10)
      - 70% AI/물리: 200-500 ticks (Nice 10)

    목표: 60 FPS 유지, 렌더링 우선
    비교: 우선순위 기반 실시간 응답성
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

TEST_FAIRNESS_EXTREME_NICE = BenchmarkTest(
    test_id="fairness_extreme_nice",
    name="공정성: 극단 Nice 가중치",
    goal="Nice 가중치 비율에 맞는 CPU 배분",
    workload_type="extreme_nice_fairness",
    thread_count=30,
    schedulers=["mlfqs", "cfs"],  # Basic 제외
    primary_metric="fairness",
    description="""
    극단적 Nice 워크로드 (Nice -20 vs 19), I/O 없음:
      - 절반: Nice -20 (최고 우선순위)
      - 절반: Nice 19 (최저 우선순위)
      - CPU burst: 1,000 ticks (공정성 측정용으로 단축)

    목표: 가중치 비율에 따른 CPU 배분 공정성 측정
    비교: MLFQS vs CFS (CFS는 weight 비례 분배가 목표)
    메트릭: Jain's Fairness Index (1.0에 가까울수록 공정)
    """,
    max_ticks=60000  # 총 burst 30,000의 2배
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
      - CPU burst: 2,000 ticks (동일)

    목표: Nice 값의 실제 효과 측정
    비교: MLFQS vs CFS (각자의 nice 해석 방식)
    예상: CFS는 ~1000:1 비율
    """,
    max_ticks=20000  # 총 burst 100,000의 20%
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


# 6. 일관성 테스트 (CFS 장점)
TEST_CONSISTENCY_CV = BenchmarkTest(
    test_id="consistency_cv",
    name="일관성: 변동계수",
    goal="대기 시간의 예측 가능성",
    workload_type="mixed",
    thread_count=100,
    schedulers=["basic", "mlfqs", "cfs"],
    primary_metric="cv_wait",
    description="""
    Mixed 워크로드 (Nice -5~5), 100 스레드

    측정: 변동계수 (CV) = 표준편차/평균 × 100
    의미: 낮을수록 대기 시간이 예측 가능
    용도: SLA 보장이 필요한 서비스

    CFS 장점: 공정성으로 인해 모든 스레드가 비슷한 대기 경험
    """
)

TEST_CONSISTENCY_P99 = BenchmarkTest(
    test_id="consistency_p99",
    name="일관성: P99 레이턴시",
    goal="최악 1%의 대기 시간",
    workload_type="mixed",
    thread_count=100,
    schedulers=["basic", "mlfqs", "cfs"],
    primary_metric="p99_wait",
    description="""
    Mixed 워크로드 (Nice -5~5), 100 스레드

    측정: 99 퍼센타일 대기 시간
    의미: 낮을수록 테일 레이턴시가 좋음
    용도: p99 SLA가 중요한 서비스 (웹, API)

    CFS 장점: 극단적 지연을 방지
    """
)

TEST_CONSISTENCY_WORST = BenchmarkTest(
    test_id="consistency_worst",
    name="일관성: 최악/평균 비율",
    goal="극단적 지연 방지",
    workload_type="mixed",
    thread_count=100,
    schedulers=["basic", "mlfqs", "cfs"],
    primary_metric="worst_ratio",
    description="""
    Mixed 워크로드 (Nice -5~5), 100 스레드

    측정: 최악 대기 시간 / 평균 대기 시간
    의미: 1.0에 가까울수록 균일한 대기
    용도: 공정한 서비스 품질 보장

    CFS 장점: 우선순위 역전 없이 균일한 배분
    """
)

TEST_STARVATION = BenchmarkTest(
    test_id="starvation",
    name="기아 방지: 극단적 Nice",
    goal="모든 스레드 실행 보장",
    workload_type="extreme_nice",
    thread_count=50,
    schedulers=["basic", "mlfqs", "cfs"],
    primary_metric="starvation_pct",
    description="""
    극단적 Nice 워크로드 (Nice -20 vs 19)

    측정: 실행 안된 스레드 비율 (%)
    의미: 0%가 이상적 (모두 실행됨)
    용도: Starvation 방지 능력 검증

    CFS 장점: 모든 스레드가 공정하게 실행 기회 획득
    """,
    max_ticks=20000  # 총 burst 100,000의 20%
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
        "tests": [TEST_FAIRNESS_CPU, TEST_FAIRNESS_MIXED, TEST_FAIRNESS_EXTREME_NICE]
    },
    "일관성 (CFS 장점)": {
        "description": "대기 시간의 예측 가능성과 일관성 (CFS 유리)",
        "tests": [TEST_CONSISTENCY_CV, TEST_CONSISTENCY_P99, TEST_CONSISTENCY_WORST, TEST_STARVATION]
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
    TEST_FAIRNESS_CPU, TEST_FAIRNESS_MIXED, TEST_FAIRNESS_EXTREME_NICE,
    TEST_CONSISTENCY_CV, TEST_CONSISTENCY_P99, TEST_CONSISTENCY_WORST, TEST_STARVATION,
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
