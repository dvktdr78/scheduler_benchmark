#!/usr/bin/env python3
"""
모든 벤치마크 테스트케이스 실행 스크립트

버그 의심 기준:
1. 지나치게 outlier 값이 나오는 이론과 실제의 괴리가 심한 경우
2. 특정 값이 나오지 않고 null이나 이상한 값이 나오는 경우
3. 수행항목과 결과 해석이 전혀 달라서 딴소리를 하는 경우
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from copy import deepcopy
from scheduler.basic_priority import BasicPriorityScheduler
from scheduler.mlfqs import MLFQSScheduler
from scheduler.cfs import CFSScheduler
from workload.generator import generate_workload
from simulator.simulator import Simulator
from analysis.insights import generate_comparison_report
from benchmark.tests import ALL_TESTS, TEST_CATEGORIES


def run_test(test, max_ticks=35000):
    """단일 테스트 실행"""
    print(f"\n{'='*60}")
    print(f"테스트: {test.name} ({test.test_id})")
    print(f"목표: {test.goal}")
    print(f"워크로드: {test.workload_type}, 스레드: {test.thread_count}")
    print(f"비교 대상: {', '.join(s.upper() for s in test.schedulers)}")
    print(f"주요 메트릭: {test.primary_metric}")
    print(f"{'='*60}")

    # 워크로드 생성
    base_threads = generate_workload(test.workload_type, test.thread_count, seed=42)

    # 시뮬레이션 시간 조정
    actual_max_ticks = max_ticks
    if test.test_id == "nice_effect":
        total_work = sum(t.burst_time for t in base_threads)
        suggested_ticks = int(total_work * 0.2)
        actual_max_ticks = min(max_ticks, suggested_ticks)
    elif test.test_id == "fairness_extreme_nice":
        total_work = sum(t.burst_time for t in base_threads)
        suggested_ticks = int(total_work * 0.3)
        actual_max_ticks = min(max_ticks, suggested_ticks)
    elif test.test_id in ["fairness_cpu", "fairness_mixed"]:
        total_work = sum(t.burst_time for t in base_threads)
        suggested_ticks = int(total_work * 0.5)
        actual_max_ticks = min(max_ticks, suggested_ticks)

    print(f"시뮬레이션 ticks: {actual_max_ticks}")

    # 스케줄러 실행
    scheduler_results = {}

    for scheduler_name in test.schedulers:
        threads = deepcopy(base_threads)

        if scheduler_name == "basic":
            scheduler = BasicPriorityScheduler(enable_aging=False)
        elif scheduler_name == "mlfqs":
            scheduler = MLFQSScheduler()
        elif scheduler_name == "cfs":
            scheduler = CFSScheduler()
        else:
            print(f"Unknown scheduler: {scheduler_name}")
            continue

        sim = Simulator(scheduler, threads)
        df = sim.run(max_ticks=actual_max_ticks)
        scheduler_results[scheduler_name] = threads

    # 결과 분석
    report = generate_comparison_report(scheduler_results, primary_metric=test.primary_metric)

    return report, scheduler_results


def analyze_results(test, report, scheduler_results):
    """결과 분석 및 버그 의심 사항 검출"""
    issues = []

    print(f"\n--- 결과 분석 ---")
    print(f"승자: {report['winner'].upper()}")

    # 메트릭 출력
    print("\n[메트릭 비교]")
    for scheduler_name, metrics in report['metrics'].items():
        print(f"\n{scheduler_name.upper()}:")
        print(f"  - 평균 대기 시간: {metrics.get('avg_wait', 'N/A')}")
        print(f"  - 평균 반환 시간: {metrics.get('avg_turnaround', 'N/A')}")
        print(f"  - 공정성 지수: {metrics.get('fairness', 'N/A')}")
        print(f"  - CPU 시간 비율: {metrics.get('cpu_time_ratio', 'N/A')}")
        print(f"  - 컨텍스트 스위치: {metrics.get('context_switches', 'N/A')}")
        print(f"  - Starvation 위험: {metrics.get('has_starvation', False)}")

        # 버그 검사 1: null 또는 이상한 값
        if metrics.get('avg_wait') is None:
            issues.append(f"[경고] {scheduler_name}: avg_wait가 None입니다")
        if metrics.get('avg_turnaround') is None:
            issues.append(f"[주의] {scheduler_name}: avg_turnaround가 None입니다 (완료된 스레드 없음?)")
        if metrics.get('fairness') == 0.0:
            issues.append(f"[경고] {scheduler_name}: fairness가 0.0입니다 (계산 오류 가능)")

        # 버그 검사 2: 이상한 값 범위
        avg_wait = metrics.get('avg_wait')
        if avg_wait is not None:
            if avg_wait < 0:
                issues.append(f"[버그] {scheduler_name}: avg_wait가 음수입니다 ({avg_wait})")
            if avg_wait > 100000:
                issues.append(f"[경고] {scheduler_name}: avg_wait가 매우 높습니다 ({avg_wait}) - 확인 필요")

        fairness = metrics.get('fairness')
        if fairness is not None:
            if fairness < 0 or fairness > 1:
                issues.append(f"[버그] {scheduler_name}: fairness가 [0,1] 범위 밖입니다 ({fairness})")

        cpu_ratio = metrics.get('cpu_time_ratio')
        if cpu_ratio is not None:
            if cpu_ratio < 0:
                issues.append(f"[버그] {scheduler_name}: cpu_time_ratio가 음수입니다 ({cpu_ratio})")

    # 버그 검사 3: 이론과 실제 괴리
    if test.primary_metric == 'fairness':
        # CFS는 공정성이 높아야 함
        if 'cfs' in report['metrics']:
            cfs_fairness = report['metrics']['cfs'].get('fairness', 0)
            if cfs_fairness < 0.8:
                issues.append(f"[의심] CFS의 공정성이 낮습니다 ({cfs_fairness:.4f}) - CFS는 공정성에 강해야 함")

    if test.primary_metric == 'cpu_time_ratio':
        # Nice 효과 테스트에서 CFS는 큰 비율 차이를 보여야 함
        if 'cfs' in report['metrics']:
            cfs_ratio = report['metrics']['cfs'].get('cpu_time_ratio')
            if cfs_ratio is not None and cfs_ratio < 10:
                issues.append(f"[의심] CFS의 CPU 시간 비율이 낮습니다 ({cfs_ratio:.1f}) - Nice -20 vs 19는 큰 차이가 예상됨")

    if test.primary_metric == 'avg_wait':
        # I/O bound에서 MLFQS/CFS가 basic보다 좋아야 함
        if 'basic' in report['metrics'] and 'mlfqs' in report['metrics']:
            basic_wait = report['metrics']['basic'].get('avg_wait', 0)
            mlfqs_wait = report['metrics']['mlfqs'].get('avg_wait', 0)
            if mlfqs_wait > basic_wait * 1.5 and test.workload_type == 'io_bound':
                issues.append(f"[의심] I/O bound에서 MLFQS가 Basic보다 나쁨 (MLFQS: {mlfqs_wait:.1f}, Basic: {basic_wait:.1f})")

    # 개선율 출력
    if report['improvements']:
        print(f"\n[개선율 vs {report['baseline'].upper()}]")
        for key, value in report['improvements'].items():
            scheduler_name = key.split('_vs_')[0]
            print(f"  {scheduler_name.upper()}: {value:+.1f}%")

    # Insights 출력
    if report['insights']:
        print("\n[Insights]")
        for insight in report['insights']:
            print(f"  {insight}")

    # 스레드 상태 확인
    print("\n[스레드 상태 확인]")
    for scheduler_name, threads in scheduler_results.items():
        completed = sum(1 for t in threads if t.finish_time >= 0)
        print(f"  {scheduler_name.upper()}: {completed}/{len(threads)} 완료")

        # 완료된 스레드가 없으면 경고
        if completed == 0:
            issues.append(f"[경고] {scheduler_name}: 완료된 스레드가 없습니다")

    return issues


def main():
    """모든 테스트 실행"""
    print("="*70)
    print("스케줄러 벤치마크 테스트 실행")
    print("="*70)

    all_issues = []

    for category_name, category_info in TEST_CATEGORIES.items():
        print(f"\n\n{'#'*70}")
        print(f"# 카테고리: {category_name}")
        print(f"# {category_info['description']}")
        print(f"{'#'*70}")

        for test in category_info['tests']:
            try:
                report, scheduler_results = run_test(test)
                issues = analyze_results(test, report, scheduler_results)

                if issues:
                    print(f"\n[!!! 발견된 문제점 !!!]")
                    for issue in issues:
                        print(f"  {issue}")
                    all_issues.append((test.test_id, issues))
                else:
                    print(f"\n[OK] 특별한 문제 없음")

            except Exception as e:
                print(f"\n[오류 발생] {test.test_id}: {str(e)}")
                import traceback
                traceback.print_exc()
                all_issues.append((test.test_id, [f"[오류] {str(e)}"]))

    # 최종 요약
    print("\n\n")
    print("="*70)
    print("최종 요약")
    print("="*70)

    if all_issues:
        print(f"\n총 {len(all_issues)}개 테스트에서 문제 발견:\n")
        for test_id, issues in all_issues:
            print(f"\n[{test_id}]")
            for issue in issues:
                print(f"  {issue}")
    else:
        print("\n모든 테스트 통과!")

    return len(all_issues) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
