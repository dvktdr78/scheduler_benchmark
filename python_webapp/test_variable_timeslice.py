#!/usr/bin/env python3
"""
가변 Time Slice 효과 테스트

Linux CFS의 time slice 계산:
  time_slice = (weight / total_weight) * sched_latency

현재 구현: 고정 4 tick
개선 구현: 가중치 비례 time slice
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from copy import deepcopy
from typing import List, Optional, Any
import pandas as pd
from scheduler.cfs import CFSScheduler, PRIO_TO_WEIGHT
from scheduler.thread import Thread, ThreadStatus
from workload.generator import generate_extreme_nice, generate_cpu_bound, generate_mixed

# ============================================================
# 가변 Time Slice를 지원하는 시뮬레이터
# ============================================================

class VariableSliceSimulator:
    """가변 time slice를 지원하는 시뮬레이터"""

    def __init__(self, scheduler: Any, threads: List[Thread],
                 min_granularity: int = 1, sched_latency: int = 48):
        """
        Args:
            scheduler: CFS 스케줄러
            threads: 스레드 리스트
            min_granularity: 최소 time slice (Linux default: 0.75ms ≈ 1 tick)
            sched_latency: 스케줄링 주기 (Linux default: 6ms ≈ 48 ticks at 8kHz)
        """
        self.scheduler = scheduler
        self.threads = threads
        self.min_granularity = min_granularity
        self.sched_latency = sched_latency
        self.current_tick = 0
        self.running: Optional[Thread] = None
        self.current_slice_remaining = 0
        self.prev_running_tid: Optional[int] = None
        self.context_switches = 0

        for thread in threads:
            thread.status = ThreadStatus.BLOCKED
            thread.io_remaining = 0

    def calc_time_slice(self, thread: Thread) -> int:
        """
        가중치 비례 time slice 계산

        Linux 공식: time_slice = (weight / total_weight) * sched_latency
        """
        # Ready/Running 스레드들의 총 가중치
        total_weight = sum(
            t.weight for t in self.threads
            if t.status in (ThreadStatus.READY, ThreadStatus.RUNNING)
        )

        if total_weight <= 0:
            return self.min_granularity

        # 가중치 비례 time slice
        slice_ticks = int((thread.weight / total_weight) * self.sched_latency)
        return max(self.min_granularity, slice_ticks)

    def run(self, max_ticks: int = 10000) -> pd.DataFrame:
        """시뮬레이션 실행"""
        for tick in range(max_ticks):
            self.current_tick = tick

            # 1. 새로 도착한 스레드 처리
            for thread in self.threads:
                if thread.arrival_time == tick and thread.status == ThreadStatus.BLOCKED:
                    thread.status = ThreadStatus.READY
                    self.scheduler.add_thread(thread)

            # 2. 스케줄러 tick
            self.scheduler.tick(tick, self.running)

            # 3. 실행 중인 스레드 처리
            if self.running is not None:
                self.running.remaining_time -= 1
                self.current_slice_remaining -= 1

                if self.running.start_time == -1:
                    self.running.start_time = tick

                # 완료
                if self.running.remaining_time <= 0:
                    self.running.status = ThreadStatus.TERMINATED
                    self.running.finish_time = tick
                    self.scheduler.thread_exit(self.running)
                    self.prev_running_tid = self.running.tid
                    self.running = None
                # Time slice 만료
                elif self.current_slice_remaining <= 0:
                    self.scheduler.thread_yield(self.running)
                    self.prev_running_tid = self.running.tid
                    self.running = None

            # 4. 다음 스레드 선택
            if self.running is None:
                prev_tid = self.prev_running_tid
                next_thread = self.scheduler.pick_next()

                if next_thread is not None:
                    self.running = next_thread
                    self.running.status = ThreadStatus.RUNNING
                    # 가변 time slice!
                    self.current_slice_remaining = self.calc_time_slice(next_thread)

                    if prev_tid is not None and prev_tid != next_thread.tid:
                        self.context_switches += 1
                    self.prev_running_tid = next_thread.tid

            # 5. 대기 시간 업데이트
            for thread in self.threads:
                if thread.status in (ThreadStatus.READY, ThreadStatus.RUNNING):
                    thread.runnable_time += 1
                if thread.status == ThreadStatus.READY:
                    thread.wait_time += 1

            # 6. 완료 체크
            if all(t.status == ThreadStatus.TERMINATED for t in self.threads):
                break

        for thread in self.threads:
            thread.context_switches = self.context_switches

        return pd.DataFrame()


# ============================================================
# 고정 Time Slice 시뮬레이터 (기존)
# ============================================================

class FixedSliceSimulator:
    """고정 time slice 시뮬레이터 (기존 방식)"""

    def __init__(self, scheduler: Any, threads: List[Thread], time_slice: int = 4):
        self.scheduler = scheduler
        self.threads = threads
        self.time_slice = time_slice
        self.current_tick = 0
        self.running: Optional[Thread] = None
        self.current_slice_remaining = 0
        self.prev_running_tid: Optional[int] = None
        self.context_switches = 0

        for thread in threads:
            thread.status = ThreadStatus.BLOCKED
            thread.io_remaining = 0

    def run(self, max_ticks: int = 10000) -> pd.DataFrame:
        for tick in range(max_ticks):
            self.current_tick = tick

            for thread in self.threads:
                if thread.arrival_time == tick and thread.status == ThreadStatus.BLOCKED:
                    thread.status = ThreadStatus.READY
                    self.scheduler.add_thread(thread)

            self.scheduler.tick(tick, self.running)

            if self.running is not None:
                self.running.remaining_time -= 1
                self.current_slice_remaining -= 1

                if self.running.start_time == -1:
                    self.running.start_time = tick

                if self.running.remaining_time <= 0:
                    self.running.status = ThreadStatus.TERMINATED
                    self.running.finish_time = tick
                    self.scheduler.thread_exit(self.running)
                    self.prev_running_tid = self.running.tid
                    self.running = None
                elif self.current_slice_remaining <= 0:
                    self.scheduler.thread_yield(self.running)
                    self.prev_running_tid = self.running.tid
                    self.running = None

            if self.running is None:
                prev_tid = self.prev_running_tid
                next_thread = self.scheduler.pick_next()

                if next_thread is not None:
                    self.running = next_thread
                    self.running.status = ThreadStatus.RUNNING
                    self.current_slice_remaining = self.time_slice  # 고정!

                    if prev_tid is not None and prev_tid != next_thread.tid:
                        self.context_switches += 1
                    self.prev_running_tid = next_thread.tid

            for thread in self.threads:
                if thread.status in (ThreadStatus.READY, ThreadStatus.RUNNING):
                    thread.runnable_time += 1
                if thread.status == ThreadStatus.READY:
                    thread.wait_time += 1

            if all(t.status == ThreadStatus.TERMINATED for t in self.threads):
                break

        for thread in self.threads:
            thread.context_switches = self.context_switches

        return pd.DataFrame()


# ============================================================
# 비교 테스트
# ============================================================

def compare_nice_effect():
    """Nice 효과 비교: 고정 vs 가변 time slice"""
    print("=" * 70)
    print("Nice 효과 테스트: Nice -20 vs Nice 19 (50 스레드)")
    print("=" * 70)

    # 이론적 비율
    weight_minus20 = PRIO_TO_WEIGHT[0]   # 88761
    weight_19 = PRIO_TO_WEIGHT[39]       # 15
    theoretical_ratio = weight_minus20 / weight_19
    print(f"\n이론적 CPU 비율: {theoretical_ratio:.1f}:1")

    threads_base = generate_extreme_nice(50, seed=42)
    max_ticks = 100000

    results = {}

    for name, SimClass in [("고정 Time Slice (4 tick)", FixedSliceSimulator),
                            ("가변 Time Slice", VariableSliceSimulator)]:
        threads = deepcopy(threads_base)
        scheduler = CFSScheduler()
        sim = SimClass(scheduler, threads)
        sim.run(max_ticks=max_ticks)

        cpu_minus20 = sum(t.burst_time - t.remaining_time for t in threads if t.nice == -20)
        cpu_19 = sum(t.burst_time - t.remaining_time for t in threads if t.nice == 19)
        total = cpu_minus20 + cpu_19

        ratio = cpu_minus20 / cpu_19 if cpu_19 > 0 else float('inf')
        pct_theory = (ratio / theoretical_ratio) * 100

        results[name] = {
            'cpu_minus20': cpu_minus20,
            'cpu_19': cpu_19,
            'ratio': ratio,
            'pct_theory': pct_theory,
            'context_switches': sim.context_switches
        }

        print(f"\n[{name}]")
        print(f"  Nice -20: {cpu_minus20} ticks ({cpu_minus20/total*100:.2f}%)")
        print(f"  Nice 19: {cpu_19} ticks ({cpu_19/total*100:.2f}%)")
        print(f"  실제 비율: {ratio:.1f}:1")
        print(f"  이론 대비: {pct_theory:.1f}%")
        print(f"  컨텍스트 스위치: {sim.context_switches}")

    # 개선율
    fixed = results["고정 Time Slice (4 tick)"]
    variable = results["가변 Time Slice"]
    improvement = ((variable['pct_theory'] - fixed['pct_theory']) / fixed['pct_theory']) * 100
    print(f"\n[개선 효과]")
    print(f"  이론 도달률 개선: {fixed['pct_theory']:.1f}% → {variable['pct_theory']:.1f}% (+{improvement:.1f}%)")


def compare_fairness():
    """공정성 비교"""
    print("\n\n")
    print("=" * 70)
    print("공정성 테스트: CPU-bound 50 스레드 (Nice 0)")
    print("=" * 70)

    threads_base = generate_cpu_bound(50, seed=42)
    max_ticks = 30000

    for name, SimClass in [("고정 Time Slice", FixedSliceSimulator),
                            ("가변 Time Slice", VariableSliceSimulator)]:
        threads = deepcopy(threads_base)
        scheduler = CFSScheduler()
        sim = SimClass(scheduler, threads)
        sim.run(max_ticks=max_ticks)

        cpu_times = [t.burst_time - t.remaining_time for t in threads]
        avg = sum(cpu_times) / len(cpu_times)
        min_cpu = min(cpu_times)
        max_cpu = max(cpu_times)

        # Jain's Index
        n = len(cpu_times)
        sum_x = sum(cpu_times)
        sum_x2 = sum(x*x for x in cpu_times)
        jains = (sum_x ** 2) / (n * sum_x2) if sum_x2 > 0 else 0

        print(f"\n[{name}]")
        print(f"  평균 CPU: {avg:.1f} ticks")
        print(f"  최소/최대: {min_cpu}/{max_cpu}")
        print(f"  Jain's Index: {jains:.6f}")
        print(f"  컨텍스트 스위치: {sim.context_switches}")


def compare_mixed_workload():
    """혼합 워크로드 비교"""
    print("\n\n")
    print("=" * 70)
    print("혼합 워크로드 테스트: Mixed 50 스레드")
    print("=" * 70)

    threads_base = generate_mixed(50, seed=42)
    max_ticks = 35000

    for name, SimClass in [("고정 Time Slice", FixedSliceSimulator),
                            ("가변 Time Slice", VariableSliceSimulator)]:
        threads = deepcopy(threads_base)
        scheduler = CFSScheduler()
        sim = SimClass(scheduler, threads)
        sim.run(max_ticks=max_ticks)

        completed = [t for t in threads if t.finish_time >= 0]
        avg_wait = sum(t.wait_time for t in threads) / len(threads)
        avg_turnaround = sum(t.finish_time - t.arrival_time for t in completed) / len(completed) if completed else 0

        print(f"\n[{name}]")
        print(f"  완료: {len(completed)}/{len(threads)}")
        print(f"  평균 대기 시간: {avg_wait:.1f} ticks")
        print(f"  평균 반환 시간: {avg_turnaround:.1f} ticks")
        print(f"  컨텍스트 스위치: {sim.context_switches}")


if __name__ == "__main__":
    compare_nice_effect()
    compare_fairness()
    compare_mixed_workload()

    print("\n\n")
    print("=" * 70)
    print("결론")
    print("=" * 70)
    print("""
1. Nice 효과: 가변 time slice가 이론적 비율에 더 가깝게 도달
2. 공정성: 둘 다 비슷 (Nice 0에서는 차이 없음)
3. 혼합 워크로드: 가변 time slice가 컨텍스트 스위치 줄일 수 있음

구현 가치:
- Nice 값 차이가 큰 워크로드에서 효과 있음
- 일반 워크로드 (Nice 0)에서는 차이 미미
- 구현 복잡도 대비 효과는 제한적
""")
