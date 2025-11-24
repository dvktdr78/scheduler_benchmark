"""MLFQS 스케줄러 (64-Queue 구현 - FreeBSD 정확)

✅ 개선사항:
  - 64개 독립 큐 (진짜 Multi-Level!)
  - O(1) pick_next (기존 O(n) → O(64) = O(1))
  - O(1) thread_yield (기존 O(n log n) → O(1))
  - FreeBSD 구조와 정확히 일치

핵심:
  - Priority 동적 계산: priority = PRI_MAX - (recent_cpu/4) - (nice*2)
  - Load average, Recent CPU 기반 (4.4BSD 공식)
"""
from typing import List, Optional
from collections import deque
from .thread import Thread, ThreadStatus
from .fixed_point import FP

PRI_MIN = 0
PRI_MAX = 63
NUM_PRIORITIES = 64
TIMER_FREQ = 100

class MLFQSScheduler:
    """Multi-Level Feedback Queue Scheduler (64-Queue 구현)"""

    def __init__(self):
        # 64개 독립 큐 (FreeBSD 방식!)
        self.ready_queues: List[deque] = [deque() for _ in range(NUM_PRIORITIES)]

        self.load_avg = 0  # 고정소수점
        self.all_threads: List[Thread] = []

    def calculate_priority(self, thread: Thread):
        """priority = PRI_MAX - (recent_cpu/4) - (nice*2)"""
        term_recent = FP.fp_div_int(thread.recent_cpu, 4)
        term_nice = FP.int_to_fp(thread.nice * 2)

        fp_priority = FP.int_to_fp(PRI_MAX)
        fp_priority = FP.fp_sub(fp_priority, term_recent)
        fp_priority = FP.fp_sub(fp_priority, term_nice)

        new_priority = FP.fp_to_int_trunc(fp_priority)
        thread.priority = max(PRI_MIN, min(PRI_MAX, new_priority))

    def increment_recent_cpu(self, thread: Thread):
        """실행 중인 스레드 recent_cpu 증가"""
        thread.recent_cpu = FP.fp_add_int(thread.recent_cpu, 1)

    def update_load_avg(self, running: Optional[Thread]):
        """load_avg = (59/60)*load_avg + (1/60)*ready_threads"""
        ready_count = sum(1 for t in self.all_threads
                         if t.status != ThreadStatus.TERMINATED
                         and t.status != ThreadStatus.BLOCKED)

        if running is not None:
            ready_count += 1

        coef_59_60 = FP.fp_div(FP.int_to_fp(59), FP.int_to_fp(60))
        coef_1_60 = FP.fp_div(FP.int_to_fp(1), FP.int_to_fp(60))

        term1 = FP.fp_mul(coef_59_60, self.load_avg)
        term2 = FP.fp_mul_int(coef_1_60, ready_count)
        self.load_avg = FP.fp_add(term1, term2)

    def update_recent_cpu_all(self):
        """recent_cpu = (2*load_avg)/(2*load_avg+1) * recent_cpu + nice"""
        two_load = FP.fp_mul_int(self.load_avg, 2)
        coef = FP.fp_div(two_load, FP.fp_add_int(two_load, 1))

        for thread in self.all_threads:
            if thread.status != ThreadStatus.TERMINATED:
                thread.recent_cpu = FP.fp_add_int(
                    FP.fp_mul(coef, thread.recent_cpu),
                    thread.nice
                )

    def recalculate_priority_all(self):
        """
        모든 스레드 우선순위 재계산 및 큐 재배치

        ⚠️ 64-Queue 방식에서는 priority 변경 시 큐 이동 필요!
        """
        # 모든 큐에서 스레드 제거 (재배치 준비)
        all_ready_threads = []
        for pri in range(NUM_PRIORITIES):
            while self.ready_queues[pri]:
                all_ready_threads.append(self.ready_queues[pri].popleft())

        # Priority 재계산
        for thread in self.all_threads:
            if thread.status != ThreadStatus.TERMINATED:
                old_priority = thread.priority
                self.calculate_priority(thread)

        # 새로운 priority에 맞게 재배치
        for thread in all_ready_threads:
            self.ready_queues[thread.priority].append(thread)

    def add_thread(self, thread: Thread):
        """스레드 추가"""
        # nice 값은 workload에서 설정된 값 유지
        thread.recent_cpu = 0
        self.calculate_priority(thread)

        self.all_threads.append(thread)

        if thread.status == ThreadStatus.READY:
            # 해당 priority 큐에 추가 (O(1)!)
            self.ready_queues[thread.priority].append(thread)

    def tick(self, current_tick: int, running: Optional[Thread]):
        """매 틱마다 호출"""
        if running is not None:
            self.increment_recent_cpu(running)

        if current_tick % TIMER_FREQ == 0:
            self.update_load_avg(running)
            self.update_recent_cpu_all()

        if current_tick % 4 == 0:
            self.recalculate_priority_all()

    def pick_next(self) -> Optional[Thread]:
        """
        최고 우선순위 스레드 선택 (O(64) = O(1))

        63 (highest) → 0 (lowest) 순서로 non-empty queue 찾기
        """
        for pri in range(PRI_MAX, PRI_MIN - 1, -1):
            if self.ready_queues[pri]:
                next_thread = self.ready_queues[pri].popleft()
                next_thread.status = ThreadStatus.RUNNING
                return next_thread

        return None

    def thread_yield(self, thread: Thread):
        """
        스레드 양보 (O(1))

        해당 priority 큐의 맨 뒤에 추가 (FIFO)
        """
        thread.status = ThreadStatus.READY

        # 현재 priority의 큐에 추가 (O(1)!)
        self.ready_queues[thread.priority].append(thread)

    def thread_exit(self, thread: Thread):
        """스레드 종료"""
        # 해당 priority 큐에서 제거
        if thread in self.ready_queues[thread.priority]:
            self.ready_queues[thread.priority].remove(thread)

        if thread in self.all_threads:
            self.all_threads.remove(thread)
