#!/usr/bin/env python3
"""
nice_effect 테스트의 CPU 비율 분석

이론:
  - Nice -20 weight = 88761
  - Nice 19 weight = 15
  - 이론적 CPU 비율 = 88761 / 15 ≈ 5917:1

실제 결과:
  - MLFQS: 8748 (거의 독점)
  - CFS: 349 (이론보다 낮음)

왜 CFS가 이론적 5917:1에 도달하지 못하는가?
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from copy import deepcopy
from scheduler.basic_priority import BasicPriorityScheduler
from scheduler.mlfqs import MLFQSScheduler
from scheduler.cfs import CFSScheduler
from workload.generator import generate_extreme_nice
from simulator.simulator import Simulator

def analyze_cpu_distribution():
    """CPU 시간 분배 상세 분석"""
    print("=" * 70)
    print("Nice 효과 분석: Nice -20 vs Nice 19")
    print("=" * 70)

    # 이론적 가중치 비율
    weight_nice_minus20 = 88761
    weight_nice_19 = 15
    theoretical_ratio = weight_nice_minus20 / weight_nice_19
    print(f"\n[이론적 예측]")
    print(f"  Nice -20 weight: {weight_nice_minus20}")
    print(f"  Nice 19 weight: {weight_nice_19}")
    print(f"  이론적 CPU 비율: {theoretical_ratio:.1f}:1")

    # 워크로드 생성 (25개 nice -20, 25개 nice 19)
    threads = generate_extreme_nice(50, seed=42)

    nice_minus20_threads = [t for t in threads if t.nice == -20]
    nice_19_threads = [t for t in threads if t.nice == 19]

    print(f"\n[워크로드]")
    print(f"  Nice -20 스레드: {len(nice_minus20_threads)}개")
    print(f"  Nice 19 스레드: {len(nice_19_threads)}개")
    print(f"  각 스레드 burst time: {threads[0].burst_time}")

    # 시뮬레이션 시간
    max_ticks = 100000  # 더 긴 시뮬레이션

    for scheduler_name, scheduler_class in [("MLFQS", MLFQSScheduler), ("CFS", CFSScheduler)]:
        print(f"\n{'='*70}")
        print(f"[{scheduler_name} 분석]")
        print(f"{'='*70}")

        test_threads = deepcopy(threads)
        scheduler = scheduler_class()
        sim = Simulator(scheduler, test_threads)
        sim.run(max_ticks=max_ticks)

        # CPU 시간 계산
        nice_minus20_cpu = sum(t.burst_time - t.remaining_time
                              for t in test_threads if t.nice == -20)
        nice_19_cpu = sum(t.burst_time - t.remaining_time
                        for t in test_threads if t.nice == 19)

        total_cpu = nice_minus20_cpu + nice_19_cpu

        print(f"\n  총 CPU 시간 사용: {total_cpu} ticks")
        print(f"  Nice -20 그룹: {nice_minus20_cpu} ticks ({nice_minus20_cpu/total_cpu*100:.2f}%)")
        print(f"  Nice 19 그룹: {nice_19_cpu} ticks ({nice_19_cpu/total_cpu*100:.2f}%)")

        if nice_19_cpu > 0:
            actual_ratio = nice_minus20_cpu / nice_19_cpu
            print(f"  실제 CPU 비율: {actual_ratio:.1f}:1")
            print(f"  이론 대비: {actual_ratio/theoretical_ratio*100:.1f}%")
        else:
            print(f"  실제 CPU 비율: Nice 19가 전혀 실행 안됨 (무한대)")

        # 개별 스레드 상태
        print(f"\n  [개별 스레드 CPU 시간]")
        print(f"  {'Nice -20 스레드':-^30}")
        for t in test_threads[:5]:  # 처음 5개만
            if t.nice == -20:
                cpu_used = t.burst_time - t.remaining_time
                print(f"    {t.name}: {cpu_used} ticks")

        print(f"  {'Nice 19 스레드':-^30}")
        for t in test_threads:
            if t.nice == 19:
                cpu_used = t.burst_time - t.remaining_time
                if cpu_used > 0:
                    print(f"    {t.name}: {cpu_used} ticks")

        # CFS의 경우 vruntime 확인
        if scheduler_name == "CFS":
            print(f"\n  [VRuntime 분석]")
            vruntime_minus20 = [t.vruntime for t in test_threads if t.nice == -20]
            vruntime_19 = [t.vruntime for t in test_threads if t.nice == 19]

            if vruntime_minus20 and vruntime_19:
                avg_vr_minus20 = sum(vruntime_minus20) / len(vruntime_minus20)
                avg_vr_19 = sum(vruntime_19) / len(vruntime_19)
                print(f"    Nice -20 평균 vruntime: {avg_vr_minus20:.0f}")
                print(f"    Nice 19 평균 vruntime: {avg_vr_19:.0f}")

                # vruntime은 거의 동일해야 함 (CFS의 공정성)
                if avg_vr_minus20 > 0:
                    vr_ratio = avg_vr_19 / avg_vr_minus20
                    print(f"    VRuntime 비율: {vr_ratio:.2f}")
                    print(f"    (1.0에 가까우면 공정하게 분배됨)")


def analyze_fairness_calculation():
    """공정성 계산 로직 분석"""
    print("\n\n")
    print("=" * 70)
    print("공정성 계산 로직 분석")
    print("=" * 70)

    from workload.generator import generate_extreme_nice_fairness
    from analysis.insights import calculate_scheduler_metrics

    threads = generate_extreme_nice_fairness(30, seed=42)
    max_ticks = 9000

    for scheduler_name, scheduler_class in [("MLFQS", MLFQSScheduler), ("CFS", CFSScheduler)]:
        print(f"\n[{scheduler_name}]")

        test_threads = deepcopy(threads)
        scheduler = scheduler_class()
        sim = Simulator(scheduler, test_threads)
        sim.run(max_ticks=max_ticks)

        metrics = calculate_scheduler_metrics(test_threads)

        print(f"  공정성 지수: {metrics['fairness']}")
        print(f"  CPU 시간 비율: {metrics['cpu_time_ratio']}")

        # 수동 계산
        print(f"\n  [수동 공정성 계산]")
        cpu_times = []
        entitlements = []

        for t in test_threads:
            cpu_used = t.burst_time - t.remaining_time
            runnable_time = getattr(t, "runnable_time", 0)
            weight = CFSScheduler.get_weight(t.nice)

            if runnable_time > 0:
                cpu_times.append(cpu_used)
                entitlements.append(runnable_time * weight)

                if cpu_used > 0:
                    print(f"    {t.name}: CPU={cpu_used}, runnable={runnable_time}, weight={weight}")

        if cpu_times and entitlements:
            total_cpu = sum(cpu_times)
            total_weight = sum(entitlements)

            print(f"\n    총 CPU 시간: {total_cpu}")
            print(f"    총 가중치: {total_weight}")

            # share_ratios 계산
            share_ratios = []
            for cpu, weight in zip(cpu_times, entitlements):
                if weight > 0:
                    actual_share = cpu / total_cpu
                    expected_share = weight / total_weight
                    ratio = actual_share / expected_share
                    share_ratios.append(ratio)

            # Jain's Index
            if share_ratios:
                n = len(share_ratios)
                sum_x = sum(share_ratios)
                sum_x2 = sum(x*x for x in share_ratios)
                jains = (sum_x ** 2) / (n * sum_x2) if sum_x2 > 0 else 0

                print(f"\n    Share ratios: min={min(share_ratios):.4f}, max={max(share_ratios):.4f}")
                print(f"    Jain's Index: {jains:.4f}")


if __name__ == "__main__":
    analyze_cpu_distribution()
    analyze_fairness_calculation()
