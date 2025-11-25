"""
Basic Priority Scheduler

특징:
  - 정적 우선순위 기반 (0-63, 높을수록 우선)
  - Preemptive (높은 우선순위가 항상 실행)
  - Aging 옵션 (starvation 방지)

검증됨:
  - tests/test_basic_verification.py (10개 테스트 통과)

제한사항:
  - Priority donation 미지원 (간소화)
  - Synchronization primitive 미포함
"""

from typing import List, Optional
from .thread import Thread, ThreadStatus

# Pintos 우선순위 범위
PRI_MIN = 0
PRI_DEFAULT = 31
PRI_MAX = 63


class BasicPriorityScheduler:
    """Basic Priority Scheduler (검증됨)"""

    def __init__(self, enable_aging=False):
        """
        Args:
            enable_aging: True면 starvation 방지 활성화
        """
        self.ready_queue: List[Thread] = []
        self.all_threads: List[Thread] = []
        self.enable_aging = enable_aging

        # Aging 관련 (옵션)
        self.aging_threshold = 100  # 100 tick 대기 시 priority +1

    def add_thread(self, thread: Thread):
        """스레드 추가"""
        # 초기 우선순위 설정 (nice 기반)
        # nice -20~19 → priority 63~0
        if thread.priority is None:
            thread.priority = PRI_DEFAULT - thread.nice
            thread.priority = max(PRI_MIN, min(PRI_MAX, thread.priority))

        if thread not in self.all_threads:
            self.all_threads.append(thread)

        if thread.status == ThreadStatus.READY and thread not in self.ready_queue:
            self.ready_queue.append(thread)

    def pick_next(self) -> Optional[Thread]:
        """최고 우선순위 스레드 선택"""
        if not self.ready_queue:
            return None

        # 최고 우선순위 찾기
        max_priority = max(t.priority for t in self.ready_queue)

        # 같은 우선순위 중 첫 번째 스레드 선택 (FIFO)
        for thread in self.ready_queue:
            if thread.priority == max_priority:
                self.ready_queue.remove(thread)
                thread.status = ThreadStatus.RUNNING
                return thread

        return None

    def tick(self, current_tick: int, running: Optional[Thread]):
        """매 틱마다 호출"""
        if running is None:
            return

        # Aging 처리 (옵션)
        if self.enable_aging:
            for thread in self.ready_queue:
                thread.wait_time += 1

                # 오래 대기하면 우선순위 상승
                if thread.wait_time >= self.aging_threshold:
                    thread.priority = min(PRI_MAX, thread.priority + 1)
                    thread.wait_time = 0

    def thread_yield(self, thread: Thread):
        """스레드 양보"""
        thread.status = ThreadStatus.READY
        self.ready_queue.append(thread)

    def thread_exit(self, thread: Thread):
        """스레드 종료"""
        if thread in self.ready_queue:
            self.ready_queue.remove(thread)
        if thread in self.all_threads:
            self.all_threads.remove(thread)

    def thread_set_priority(self, thread: Thread, new_priority: int):
        """우선순위 변경 (동적)"""
        new_priority = max(PRI_MIN, min(PRI_MAX, new_priority))
        thread.priority = new_priority
