"""
자동 Insight 생성 (3-way 비교 + 통계)

과학적 실험 원칙:
  - 반복 측정 (10회) → 평균/표준편차
  - 통계적 유의성 검증 (t-test)
  - 메트릭 정의 명확화

메트릭 분류:
  [처리량 메트릭] - 낮을수록 좋음, MLFQS/Basic 유리
    - avg_wait: 평균 대기 시간
    - avg_turnaround: 평균 반환 시간

  [일관성 메트릭] - 낮을수록 좋음, CFS 유리
    - cv_wait: 대기 시간 변동계수 (표준편차/평균*100)
    - p99_wait: 99 퍼센타일 대기 시간 (테일 레이턴시)
    - worst_ratio: 최악/평균 대기 시간 비율

  [공정성 메트릭] - CFS 유리
    - fairness: Jain's Fairness Index (높을수록 좋음)
    - starvation_pct: 실행 안된 스레드 비율 (낮을수록 좋음)
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
    """
    스케줄러 메트릭 계산

    Returns:
        [처리량 메트릭]
        avg_wait: 평균 대기 시간 (낮을수록 좋음)
        avg_turnaround: 평균 반환 시간 (낮을수록 좋음)

        [일관성 메트릭] - CFS 장점이 드러남
        cv_wait: 대기 시간 변동계수 % (낮을수록 일관적, 예측 가능)
        p99_wait: 99 퍼센타일 대기 시간 (테일 레이턴시, 낮을수록 좋음)
        worst_ratio: 최악/평균 비율 (낮을수록 좋음, 1.0이 이상적)

        [공정성 메트릭] - CFS 장점이 드러남
        fairness: Jain's Fairness Index (높을수록 좋음, 1.0이 이상적)
        starvation_pct: 실행 안된 스레드 비율 % (0%가 이상적)

        [기타]
        cpu_time_ratio: Nice 그룹간 CPU 시간 비율
        context_switches: 컨텍스트 스위치 횟수
        has_starvation: Starvation 위험 여부
    """
    if not threads:
        return {}

    # ========== 처리량 메트릭 ==========
    wait_times = [t.wait_time for t in threads]

    # 평균 대기 시간
    avg_wait = sum(wait_times) / len(wait_times)

    # 완료된 스레드들의 반환 시간
    completed = [t for t in threads if t.finish_time >= 0]
    avg_turnaround = (
        sum(t.finish_time - t.arrival_time for t in completed) / len(completed)
        if completed else None
    )

    # ========== 일관성 메트릭 (CFS 장점) ==========
    # 변동계수 (Coefficient of Variation) - 낮을수록 일관적
    std_wait = np.std(wait_times) if len(wait_times) > 1 else 0
    cv_wait = (std_wait / avg_wait * 100) if avg_wait > 0 else 0

    # 99 퍼센타일 대기 시간 (테일 레이턴시)
    p99_wait = np.percentile(wait_times, 99) if wait_times else 0

    # 최악/평균 비율 - 낮을수록 좋음
    max_wait = max(wait_times) if wait_times else 0
    worst_ratio = (max_wait / avg_wait) if avg_wait > 0 else 0

    # ========== 공정성 메트릭 (CFS 장점) ==========
    # Starvation 비율 - 실행 안된 스레드 %
    cpu_times_all = [t.burst_time - t.remaining_time for t in threads]
    starved_count = sum(1 for cpu in cpu_times_all if cpu <= 0)
    starvation_pct = (starved_count / len(threads) * 100) if threads else 0

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
        # 처리량 메트릭 (낮을수록 좋음) - MLFQS/Basic 유리
        'avg_wait': round(avg_wait, 2),
        'avg_turnaround': round(avg_turnaround, 2) if avg_turnaround else None,

        # 일관성 메트릭 (낮을수록 좋음) - CFS 유리
        'cv_wait': round(cv_wait, 2),           # 변동계수 %
        'p99_wait': round(p99_wait, 2),         # 99 퍼센타일
        'worst_ratio': round(worst_ratio, 2),   # 최악/평균 비율

        # 공정성 메트릭 - CFS 유리
        'fairness': fairness,                    # Jain Index (높을수록 좋음)
        'starvation_pct': round(starvation_pct, 1),  # 기아율 % (낮을수록 좋음)

        # 기타
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

    # Baseline 결정 (basic이 있으면 baseline, 없으면 알파벳 순 첫번째)
    scheduler_names = list(scheduler_results.keys())
    baseline_name = 'basic' if 'basic' in scheduler_names else sorted(scheduler_names)[0]
    baseline_metrics = metrics[baseline_name]
    baseline_value = baseline_metrics.get(primary_metric, 0)

    # 개선율 계산
    improvements = {}

    # 메트릭 분류 (공통으로 사용)
    lower_is_better_metrics = ['avg_wait', 'avg_turnaround', 'context_switches',
                               'cv_wait', 'p99_wait', 'worst_ratio', 'starvation_pct']
    higher_is_better_metrics = ['fairness']
    # cpu_time_ratio는 단순 비교 불가 (측정용 메트릭)

    for name, sched_metrics in metrics.items():
        if name == baseline_name:
            continue

        current_value = sched_metrics.get(primary_metric)
        # None 값 처리: 비교 불가능하면 스킵
        if current_value is None or baseline_value is None:
            continue

        if primary_metric in lower_is_better_metrics:
            # 낮을수록 좋음: (baseline - current) / baseline * 100
            if baseline_value > 1.0:
                improvement = ((baseline_value - current_value) / baseline_value * 100)
            else:
                improvement = baseline_value - current_value
        elif primary_metric in higher_is_better_metrics:
            # 높을수록 좋음: (current - baseline) / baseline * 100
            if baseline_value > 0.01:
                improvement = ((current_value - baseline_value) / baseline_value * 100)
            else:
                improvement = current_value - baseline_value
        else:
            improvement = 0

        improvements[f"{name}_vs_{baseline_name}"] = improvement

    # 승자 결정 (primary_metric 기준)
    # 기아율이 높은 스케줄러는 승자 후보에서 제외 (10% 이상이면 제외)
    valid_candidates = {
        name: m for name, m in metrics.items()
        if m.get('starvation_pct', 0) < 10
    }
    # 모든 스케줄러가 기아율 높으면 원래대로
    if not valid_candidates:
        valid_candidates = metrics

    # None 값을 안전하게 처리하는 헬퍼 함수
    def get_metric_value(m: Dict, metric: str, default_for_lower: bool) -> float:
        """메트릭 값 가져오기 (None 처리 포함)"""
        val = m.get(metric)
        if val is None:
            # 낮을수록 좋은 메트릭: None → 무한대 (최악)
            # 높을수록 좋은 메트릭: None → -무한대 (최악)
            return float('inf') if default_for_lower else float('-inf')
        return val

    if primary_metric in lower_is_better_metrics:
        # 낮을수록 좋음
        winner = min(
            valid_candidates.items(),
            key=lambda x: get_metric_value(x[1], primary_metric, True)
        )[0]
    elif primary_metric in higher_is_better_metrics:
        # 높을수록 좋음
        winner = max(
            valid_candidates.items(),
            key=lambda x: get_metric_value(x[1], primary_metric, False)
        )[0]
    elif primary_metric == 'cpu_time_ratio':
        # cpu_time_ratio: 기아율 낮은 쪽 우선, 같으면 ratio 높은 쪽
        # (기아 없이 nice 효과를 보여주는 스케줄러가 승자)
        winner = min(
            valid_candidates.items(),
            key=lambda x: (x[1].get('starvation_pct', 0), -x[1].get('cpu_time_ratio', 0))
        )[0]
    else:
        winner = list(valid_candidates.keys())[0]

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

    # 메트릭 한글 이름 매핑
    metric_names = {
        'avg_wait': '평균 대기 시간',
        'avg_turnaround': '평균 반환 시간',
        'cv_wait': '대기 시간 변동계수',
        'p99_wait': 'P99 대기 시간',
        'worst_ratio': '최악/평균 비율',
        'fairness': '공정성 지수',
        'starvation_pct': '기아율',
        'cpu_time_ratio': 'CPU 시간 비율',
        'context_switches': '컨텍스트 스위치',
    }
    metric_korean = metric_names.get(primary_metric, primary_metric)

    # 1. 개선 효과 (개선율이 10% 이상인 경우)
    significant_improvements = {k: v for k, v in improvements.items() if abs(v) > 10}
    if significant_improvements:
        improvement_strs = [f"{k.split('_vs_')[0].upper()} {v:+.1f}%"
                           for k, v in significant_improvements.items()]
        # 메트릭 설명 추가
        metric_direction = "낮을수록" if primary_metric in [
            'avg_wait', 'avg_turnaround', 'context_switches',
            'cv_wait', 'p99_wait', 'worst_ratio', 'starvation_pct'
        ] else "높을수록"
        insights.append(
            f"💡 [{metric_korean}] 개선율 (vs {baseline_name.upper()}): " + ", ".join(improvement_strs) +
            f"\n   ({metric_direction} 좋음, +는 개선 / -는 악화)"
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

    # 4. 일관성 메트릭 비교 (CFS 장점)
    if any('cv_wait' in m for m in metrics.values()):
        cv_scores = {name: m.get('cv_wait', float('inf')) for name, m in metrics.items()}
        best_cv = min(cv_scores.items(), key=lambda x: x[1])
        worst_cv = max(cv_scores.items(), key=lambda x: x[1])
        if worst_cv[1] > best_cv[1] * 1.3:  # 30% 이상 차이나면
            insights.append(
                f"📊 일관성: {best_cv[0].upper()}가 가장 예측 가능 "
                f"(CV: {best_cv[1]:.1f}% vs {worst_cv[0].upper()}: {worst_cv[1]:.1f}%)"
            )

    # 5. Starvation 비교
    if any('starvation_pct' in m for m in metrics.values()):
        starv_scores = {name: m.get('starvation_pct', 0) for name, m in metrics.items()}
        has_starv = {k: v for k, v in starv_scores.items() if v > 0}
        no_starv = {k: v for k, v in starv_scores.items() if v == 0}
        if has_starv and no_starv:
            insights.append(
                f"🚨 Starvation: {', '.join(k.upper() for k in has_starv)}에서 "
                f"{max(has_starv.values()):.1f}% 스레드 미실행. "
                f"{', '.join(k.upper() for k in no_starv)}는 안전"
            )

    # 6. 실제 결과 기반 요약 (동적 생성)
    # 각 스케줄러의 primary_metric 값 가져오기
    metric_values = {name: m.get(primary_metric) for name, m in metrics.items()}
    valid_values = {k: v for k, v in metric_values.items() if v is not None}

    if valid_values and len(valid_values) >= 2:
        lower_is_better = primary_metric in [
            'avg_wait', 'avg_turnaround', 'context_switches',
            'cv_wait', 'p99_wait', 'worst_ratio', 'starvation_pct'
        ]

        # 전체 스케줄러 중 최고/최저 찾기 (기아율 무시하고 순수 메트릭만)
        if lower_is_better:
            best = min(valid_values.items(), key=lambda x: x[1])
            worst = max(valid_values.items(), key=lambda x: x[1])
            direction = "낮을수록"
        else:
            best = max(valid_values.items(), key=lambda x: x[1])
            worst = min(valid_values.items(), key=lambda x: x[1])
            direction = "높을수록"

        # 메트릭별 단위/포맷
        metric_format = {
            'avg_wait': ('ticks', '.1f'),
            'avg_turnaround': ('ticks', '.1f'),
            'cv_wait': ('%', '.1f'),
            'p99_wait': ('ticks', '.1f'),
            'worst_ratio': ('배', '.2f'),
            'fairness': ('', '.4f'),
            'starvation_pct': ('%', '.1f'),
            'cpu_time_ratio': (':1', '.1f'),
            'context_switches': ('회', 'd'),
        }
        unit, fmt = metric_format.get(primary_metric, ('', '.2f'))

        best_val = f"{best[1]:{fmt}}{unit}"
        worst_val = f"{worst[1]:{fmt}}{unit}"

        # 기아율 표시
        best_starv = metrics[best[0]].get('starvation_pct', 0)
        worst_starv = metrics[worst[0]].get('starvation_pct', 0)

        best_note = f" (기아율 {best_starv:.0f}%)" if best_starv > 0 else ""
        worst_note = f" (기아율 {worst_starv:.0f}%)" if worst_starv > 0 else ""

        # 기아율 때문에 승자가 달라지는 경우 설명 추가
        excluded_by_starvation = [k for k, v in metrics.items()
                                   if v.get('starvation_pct', 0) >= 10]

        summary = f"📊 결과 요약 ({primary_metric}, {direction} 좋음):\n"
        summary += f"  🥇 최고: {best[0].upper()} = {best_val}{best_note}\n"
        summary += f"  🥉 최저: {worst[0].upper()} = {worst_val}{worst_note}"

        if excluded_by_starvation and best[0] in excluded_by_starvation:
            summary += f"\n  ⚠️ {best[0].upper()}는 기아율 {best_starv:.0f}%로 승자에서 제외됨"

        insights.append(summary)

    return insights
