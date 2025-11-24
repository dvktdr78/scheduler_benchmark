"""
성능 메트릭 계산

METRICS_DEFINITION.md에 정의된 메트릭들을 구현.
"""

from typing import List, Dict, Tuple
import numpy as np
import pandas as pd
from scipy import stats
from scheduler.thread import Thread


def calculate_avg_wait_time(threads: List[Thread]) -> float:
    """평균 대기 시간 계산"""
    total_wait = sum(t.wait_time for t in threads)
    return total_wait / len(threads) if threads else 0.0


def calculate_avg_turnaround(threads: List[Thread]) -> float:
    """평균 반환 시간 계산"""
    completed = [t for t in threads if t.finish_time >= 0]
    if not completed:
        return 0.0

    total_turnaround = sum(
        t.finish_time - t.arrival_time
        for t in completed
    )
    return total_turnaround / len(completed)


def calculate_avg_response(threads: List[Thread]) -> float:
    """평균 응답 시간 계산"""
    responses = [
        t.start_time - t.arrival_time
        for t in threads
        if t.start_time >= 0
    ]
    return sum(responses) / len(responses) if responses else 0.0


def calculate_jains_index(values: List[float]) -> float:
    """
    Jain's Fairness Index

    Args:
        values: 각 스레드가 받은 자원 (CPU time 등)

    Returns:
        0.0 ~ 1.0 (1.0 = 완전 공정)
    """
    if not values:
        return 0.0

    n = len(values)
    sum_x = sum(values)
    sum_x2 = sum(x*x for x in values)

    if sum_x2 == 0:
        return 0.0

    return (sum_x ** 2) / (n * sum_x2)


def calculate_cv(values: List[float]) -> float:
    """변동 계수 계산 (Coefficient of Variation)"""
    if not values:
        return 0.0

    mean = np.mean(values)
    if mean == 0:
        return 0.0

    std = np.std(values, ddof=1)
    return std / mean


def calculate_throughput(threads: List[Thread]) -> float:
    """처리량 계산 (tasks/tick)"""
    completed = [t for t in threads if t.finish_time >= 0]
    if not completed:
        return 0.0

    max_finish = max(t.finish_time for t in completed)
    min_arrival = min(t.arrival_time for t in threads)

    total_time = max_finish - min_arrival
    if total_time == 0:
        return 0.0

    return len(completed) / total_time


def count_context_switches(history: pd.DataFrame) -> int:
    """컨텍스트 스위치 횟수"""
    if history.empty:
        return 0

    running_threads = history[
        history['status'] == 'RUNNING'
    ]['tid'].values

    switches = 0
    prev = None
    for tid in running_threads:
        if prev is not None and tid != prev:
            switches += 1
        prev = tid

    return switches


def detect_starvation(threads: List[Thread], threshold: int = 10000) -> List[Thread]:
    """Starvation 발생 스레드 검출"""
    return [
        t for t in threads
        if t.wait_time > threshold
    ]


def calculate_statistics(values: List[float]) -> Dict:
    """
    통계량 계산 (반복 측정용)

    Returns:
        mean: 평균
        std: 표준편차
        min: 최소값
        max: 최대값
        ci_lower: 95% 신뢰구간 하한
        ci_upper: 95% 신뢰구간 상한
    """
    if not values:
        return {}

    mean = np.mean(values)
    std = np.std(values, ddof=1)  # 표본 표준편차
    n = len(values)

    # 95% 신뢰구간 계산 (t-distribution)
    ci = stats.t.interval(0.95, n-1, loc=mean, scale=std/np.sqrt(n))

    return {
        'mean': mean,
        'std': std,
        'min': np.min(values),
        'max': np.max(values),
        'ci_lower': ci[0],
        'ci_upper': ci[1]
    }


def calculate_95_ci(values: List[float]) -> Tuple[float, float]:
    """95% 신뢰구간 계산"""
    n = len(values)
    mean = np.mean(values)
    std = np.std(values, ddof=1)

    ci = stats.t.interval(
        confidence=0.95,
        df=n-1,
        loc=mean,
        scale=std / np.sqrt(n)
    )

    return ci  # (lower, upper)


def test_significance(values_a: List[float], values_b: List[float]) -> Dict:
    """
    통계적 유의성 검증

    Returns:
        t_statistic: t 통계량
        p_value: p-value
        significant: p < 0.05인가?
    """
    if len(values_a) < 2 or len(values_b) < 2:
        return {}

    t_stat, p_value = stats.ttest_ind(values_a, values_b)

    return {
        't_statistic': t_stat,
        'p_value': p_value,
        'significant': p_value < 0.05
    }


def cohens_d(values_a: List[float], values_b: List[float]) -> float:
    """Cohen's d 계산 (Effect size)"""
    mean_a = np.mean(values_a)
    mean_b = np.mean(values_b)

    std_a = np.std(values_a, ddof=1)
    std_b = np.std(values_b, ddof=1)

    pooled_std = np.sqrt((std_a**2 + std_b**2) / 2)

    if pooled_std == 0:
        return 0.0

    return (mean_a - mean_b) / pooled_std
