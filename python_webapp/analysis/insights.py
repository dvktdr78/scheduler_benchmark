"""
자동 Insight 생성 (3-way 비교 + 통계)

과학적 실험 원칙:
  - 반복 측정 (10회) → 평균/표준편차
  - 통계적 유의성 검증 (t-test)
  - 메트릭 정의 명확화
"""
from typing import List, Dict
import numpy as np
from scipy import stats
from scheduler.thread import Thread
from scheduler.cfs import CFSScheduler


def calculate_jains_index(values: List[float]) -> float:
    """
    Jain's Fairness Index

    정의: J = (Σx_i)^2 / (n * Σx_i^2)
    where x_i = i번째 스레드의 측정값 (CPU time, throughput 등)

    해석:
      - 1.0: 완전 공정 (모두 동일)
      - 0.0: 완전 불공정 (한쪽만 독점)
      - >0.95: 우수한 공정성
    """
    if not values:
        return 0.0
    n = len(values)
    sum_x = sum(values)
    sum_x2 = sum(x*x for x in values)
    return (sum_x ** 2) / (n * sum_x2) if sum_x2 > 0 else 0.0


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


def test_statistical_significance(values_a: List[float], values_b: List[float]) -> Dict:
    """
    통계적 유의성 검증 (t-test)

    Returns:
        t_statistic: t 통계량
        p_value: p-value
        significant: 유의미한가? (p < 0.05)
        effect_size: Cohen's d (효과 크기)
    """
    if len(values_a) < 2 or len(values_b) < 2:
        return {}

    # 독립 표본 t-검정
    t_stat, p_value = stats.ttest_ind(values_a, values_b)

    # Cohen's d (효과 크기)
    pooled_std = np.sqrt((np.std(values_a, ddof=1)**2 + np.std(values_b, ddof=1)**2) / 2)
    cohens_d = (np.mean(values_a) - np.mean(values_b)) / pooled_std if pooled_std > 0 else 0

    return {
        't_statistic': t_stat,
        'p_value': p_value,
        'significant': p_value < 0.05,
        'effect_size': cohens_d
    }


def calculate_scheduler_metrics(threads: List[Thread]) -> Dict:
    """스케줄러 메트릭 계산"""
    if not threads:
        return {}

    # 평균 대기 시간
    avg_wait = sum(t.wait_time for t in threads) / len(threads)

    # 완료된 스레드들의 반환 시간
    completed = [t for t in threads if t.finish_time >= 0]
    avg_turnaround = (
        sum(t.finish_time - t.arrival_time for t in completed) / len(completed)
        if completed else None
    )

    # 공정성 지수 (runnable 시간 대비 가중치 비율 기반)
    wait_times = [t.wait_time for t in threads]
    cpu_times = []
    entitlements = []
    for t in threads:
        if t.burst_time <= 0:
            continue
        cpu_used = max(0, t.burst_time - t.remaining_time)
        runnable_time = getattr(t, "runnable_time", 0)
        if runnable_time <= 0:
            continue
        cpu_times.append(cpu_used)
        # CFS weight 테이블을 공통 entitlement로 사용 (nice 기반 가중치)
        weight = getattr(t, "weight", None)
        if weight is None or weight <= 0:
            weight = CFSScheduler.get_weight(t.nice)
        entitlements.append(runnable_time * weight)

    if cpu_times and entitlements:
        total_cpu = sum(cpu_times)
        total_weight = sum(entitlements)
        if total_cpu > 0 and total_weight > 0:
            # 실측 비중 / 기대 비중이 모두 동일하면 완전 공정(=1.0)
            share_ratios = [
                (cpu / total_cpu) / (weight / total_weight)
                for cpu, weight in zip(cpu_times, entitlements)
                if weight > 0
            ]
            fairness = calculate_jains_index(share_ratios) if share_ratios else 0.0
        else:
            fairness = 0.0
    else:
        fairness = 0.0
    fairness = round(fairness, 4)

    # Starvation 감지
    # - 공정성 지수가 높으면 (≥0.85) starvation 없음
    # - 평균 대기 시간의 15배 이상인 스레드가 있는 경우
    has_starvation = False
    if fairness < 0.85 and avg_wait > 0:
        max_wait = max(wait_times) if wait_times else 0
        has_starvation = (max_wait > avg_wait * 15)

    # CPU time ratio (nice 효과 측정)
    # Nice가 다른 그룹 간 CPU 시간 비율 계산
    cpu_time_ratio = None
    nice_values = set(t.nice for t in threads)
    if len(nice_values) >= 2:
        # Nice 값으로 그룹화
        nice_groups = {}
        for t in threads:
            if t.nice not in nice_groups:
                nice_groups[t.nice] = []
            # CPU time = burst_time - remaining_time
            cpu_time = t.burst_time - t.remaining_time
            nice_groups[t.nice].append(cpu_time)

        # 가장 높은 우선순위(가장 낮은 nice)와 가장 낮은 우선순위(가장 높은 nice) 비교
        sorted_nices = sorted(nice_groups.keys())
        high_priority_nice = sorted_nices[0]  # 가장 낮은 nice (높은 우선순위)
        low_priority_nice = sorted_nices[-1]  # 가장 높은 nice (낮은 우선순위)

        high_priority_cpu = sum(nice_groups[high_priority_nice])
        low_priority_cpu = sum(nice_groups[low_priority_nice])

        if low_priority_cpu > 0:
            cpu_time_ratio = high_priority_cpu / low_priority_cpu
        elif high_priority_cpu > 0:
            # 낮은 우선순위가 한 번도 실행되지 않은 경우: 과도한 비율 대신 사용된 CPU 시간으로 대체
            cpu_time_ratio = float(high_priority_cpu)
        else:
            cpu_time_ratio = 1.0

    # 컨텍스트 스위치 수 (스케일 테스트용)
    context_switches = threads[0].context_switches if hasattr(threads[0], "context_switches") else 0

    return {
        'avg_wait': avg_wait,
        'avg_turnaround': avg_turnaround,
        'fairness': fairness,
        'has_starvation': has_starvation,
        'cpu_time_ratio': cpu_time_ratio,
        'context_switches': context_switches
    }


def generate_3way_comparison_report(
    basic_threads: List[Thread],
    mlfqs_threads: List[Thread],
    cfs_threads: List[Thread]
) -> Dict:
    """3-way 비교 리포트 생성 (하위 호환성 유지)"""
    results = {
        'basic': basic_threads,
        'mlfqs': mlfqs_threads,
        'cfs': cfs_threads
    }
    return generate_comparison_report(results, primary_metric='avg_wait')


def generate_comparison_report(
    scheduler_results: Dict[str, List[Thread]],
    primary_metric: str = 'avg_wait'
) -> Dict:
    """
    유연한 스케줄러 비교 리포트 생성

    Args:
        scheduler_results: {'scheduler_name': [threads]} 형태
        primary_metric: 주요 비교 메트릭

    Returns:
        비교 리포트 딕셔너리
    """
    # 각 스케줄러 메트릭 계산
    metrics = {}
    for scheduler_name, threads in scheduler_results.items():
        metrics[scheduler_name] = calculate_scheduler_metrics(threads)

    # Baseline 결정 (basic이 있으면 baseline, 없으면 첫번째)
    scheduler_names = list(scheduler_results.keys())
    baseline_name = 'basic' if 'basic' in scheduler_names else scheduler_names[0]
    baseline_metrics = metrics[baseline_name]
    baseline_value = baseline_metrics.get(primary_metric, 0)

    # 개선율 계산
    improvements = {}
    for name, sched_metrics in metrics.items():
        if name == baseline_name:
            continue

        current_value = sched_metrics.get(primary_metric, 0)
        if current_value is None or baseline_value is None:
            continue

        # 메트릭 종류에 따라 개선 방향 결정
        if primary_metric in ['avg_wait', 'avg_turnaround', 'context_switches']:
            # 낮을수록 좋음
            if baseline_value > 1.0:
                improvement = ((baseline_value - current_value) / baseline_value * 100)
            else:
                improvement = baseline_value - current_value
        elif primary_metric in ['fairness', 'cpu_time_ratio']:
            # 높을수록 좋음
            if baseline_value > 0.01:
                improvement = ((current_value - baseline_value) / baseline_value * 100)
            else:
                improvement = current_value - baseline_value
        else:
            improvement = 0

        improvements[f"{name}_vs_{baseline_name}"] = improvement

    # 승자 결정 (primary_metric 기준)
    if primary_metric in ['avg_wait', 'avg_turnaround', 'context_switches']:
        # 낮을수록 좋음
        winner = min(metrics.items(), key=lambda x: x[1].get(primary_metric, float('inf')))[0]
    elif primary_metric in ['fairness', 'cpu_time_ratio']:
        # 높을수록 좋음
        winner = max(metrics.items(), key=lambda x: x[1].get(primary_metric, 0))[0]
    else:
        winner = list(metrics.keys())[0]

    # Insight 생성
    insights = generate_insights(metrics, scheduler_names, primary_metric, improvements, baseline_name)

    return {
        'winner': winner,
        'metrics': metrics,
        'improvements': improvements,
        'insights': insights,
        'baseline': baseline_name,
        'primary_metric': primary_metric
    }


def generate_insights(
    metrics: Dict[str, Dict],
    scheduler_names: List[str],
    primary_metric: str,
    improvements: Dict[str, float],
    baseline_name: str
) -> List[str]:
    """Insight 생성"""
    insights = []

    # 1. 개선 효과 (개선율이 10% 이상인 경우)
    significant_improvements = {k: v for k, v in improvements.items() if abs(v) > 10}
    if significant_improvements:
        improvement_strs = [f"{k.split('_vs_')[0].upper()} {v:+.1f}%"
                           for k, v in significant_improvements.items()]
        insights.append(
            f"💡 개선 효과 (vs {baseline_name.upper()}): " + ", ".join(improvement_strs)
        )

    # 2. 공정성 비교 (fairness가 있는 경우)
    if any('fairness' in m for m in metrics.values()):
        fairness_scores = {name: m.get('fairness', 0) for name, m in metrics.items()}
        best_fairness = max(fairness_scores.items(), key=lambda x: x[1])
        if best_fairness[1] > 0.9:
            insights.append(
                f"⚖️ 공정성: {best_fairness[0].upper()}가 가장 우수 "
                f"(Jain Index: {best_fairness[1]:.4f})"
            )

    # 3. Starvation 경고 (basic이 포함된 경우)
    if 'basic' in metrics:
        if metrics['basic'].get('has_starvation', False):
            other_schedulers = [s for s in scheduler_names if s != 'basic']
            if other_schedulers:
                insights.append(
                    f"⚠️ Basic Priority는 Starvation 위험이 있습니다. "
                    f"{', '.join(s.upper() for s in other_schedulers)}는 안전합니다."
                )

    # 4. 메트릭별 권장사항
    if primary_metric == 'avg_wait':
        insights.append(
            "📈 대기 시간 최소화:\n"
            "  - Interactive 작업에 적합\n"
            "  - 사용자 응답성이 중요한 경우"
        )
    elif primary_metric == 'avg_turnaround':
        insights.append(
            "📈 반환 시간 최소화:\n"
            "  - 배치 작업 처리에 적합\n"
            "  - 전체 처리량이 중요한 경우"
        )
    elif primary_metric == 'fairness':
        insights.append(
            "📈 공정성 최대화:\n"
            "  - 모든 작업에 공평한 기회\n"
            "  - Starvation 방지"
        )
    elif primary_metric == 'cpu_time_ratio':
        insights.append(
            "📈 CPU 시간 비율 향상:\n"
            "  - 낮은 nice(높은 우선순위) 그룹이 얼마나 더 많은 CPU를 가져갔는지 측정\n"
            "  - 값이 높을수록 nice 차이를 제대로 반영"
        )

    return insights
