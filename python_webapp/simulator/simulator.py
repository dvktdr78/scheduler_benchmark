"""
시뮬레이션 엔진

단일 CPU 스케줄러 시뮬레이터.
매 tick마다 스케줄링 결정을 수행하고 결과를 기록.
"""

from typing import List, Optional, Any
import pandas as pd
from scheduler.thread import Thread, ThreadStatus

MIN_IO_DURATION = 8   # ticks (2 time slices)
MAX_IO_DURATION = 120 # ticks


class Simulator:
    """스케줄러 시뮬레이터"""

    def __init__(self, scheduler: Any, threads: List[Thread], time_slice: int = 4):
        """
        Args:
            scheduler: 스케줄러 인스턴스 (BasicPriorityScheduler, MLFQSScheduler, CFSScheduler)
            threads: 시뮬레이션할 스레드 리스트
            time_slice: 시간 조각 (ticks)
        """
        self.scheduler = scheduler
        self.threads = threads
        self.history = []
        self.current_tick = 0
        self.running: Optional[Thread] = None
        self.context_switches = 0
        self.time_slice = time_slice
        self.current_slice_remaining = 0
        self.prev_running_tid: Optional[int] = None

        # 모든 스레드를 스케줄러에 추가
        for thread in threads:
            # 초기에는 모두 READY로 설정하지 않고 arrival_time에 추가
            thread.status = ThreadStatus.BLOCKED  # 도착 전
            thread.io_remaining = 0
            thread.cpu_since_io = 0

    def run(self, max_ticks: int = 10000) -> pd.DataFrame:
        """
        시뮬레이션 실행

        Args:
            max_ticks: 최대 시뮬레이션 시간

        Returns:
            시뮬레이션 히스토리 (DataFrame)
        """
        for tick in range(max_ticks):
            self.current_tick = tick

            # 1. 새로 도착한 스레드 처리
            self._handle_arrivals()

            # 2. I/O 완료 처리 (BLOCKED → READY)
            self._handle_io_completion()

            # 3. 스케줄러 tick 호출
            self.scheduler.tick(tick, self.running)

            # 4. 실행 중인 스레드 처리
            self._handle_running_thread()

            # 5. 다음 스레드 선택
            if self.running is None:
                self._schedule_next()

            # 6. 대기 중인 스레드의 wait_time 증가
            self._update_wait_times()

            # 7. 현재 상태 기록
            self._record_state()

            # 8. 모든 스레드 완료 확인
            if self._all_threads_done():
                break

        # 메트릭 계산을 위해 모든 스레드에 컨텍스트 스위치 수를 기록
        for thread in self.threads:
            thread.context_switches = self.context_switches

        return pd.DataFrame(self.history)

    def _handle_arrivals(self):
        """새로 도착한 스레드 추가"""
        for thread in self.threads:
            if thread.arrival_time == self.current_tick and thread.status == ThreadStatus.BLOCKED:
                thread.status = ThreadStatus.READY
                self.scheduler.add_thread(thread)

    def _handle_io_completion(self):
        """I/O 완료 처리 (BLOCKED → READY)"""
        for thread in self.threads:
            if thread.status == ThreadStatus.BLOCKED and thread.io_remaining > 0:
                thread.io_remaining -= 1
                if thread.io_remaining <= 0:
                    thread.status = ThreadStatus.READY
                    self.scheduler.add_thread(thread)

    def _handle_running_thread(self):
        """실행 중인 스레드 처리"""
        if self.running is None:
            return

        # CPU 실행
        self.running.remaining_time -= 1
        self.current_slice_remaining -= 1

        # 첫 실행 시간 기록
        if self.running.start_time == -1:
            self.running.start_time = self.current_tick

        # 스레드 완료
        if self.running.remaining_time <= 0:
            self.running.status = ThreadStatus.TERMINATED
            self.running.finish_time = self.current_tick
            self.scheduler.thread_exit(self.running)
            self.prev_running_tid = self.running.tid
            self.running = None
            return

        # I/O 진입 여부 확인 (완료가 아닐 때만)
        if self.running.io_frequency > 0 and self.running.io_duration > 0:
            self.running.cpu_since_io += 1
            if self.running.cpu_since_io >= self.running.io_frequency:
                self.running.cpu_since_io = 0
                self.running.io_remaining = self._clamp_io_duration(self.running.io_duration)
                if self.running.io_remaining > 0:
                    self.running.status = ThreadStatus.BLOCKED
                    self.prev_running_tid = self.running.tid
                    self.running = None
                    return

        # Time slice 만료 - 스레드를 다시 ready queue에 넣기
        if self.current_slice_remaining <= 0:
            self.scheduler.thread_yield(self.running)
            self.prev_running_tid = self.running.tid
            self.running = None

    def _schedule_next(self):
        """다음 스레드 선택"""
        prev_tid = self.prev_running_tid
        next_thread = self.scheduler.pick_next()

        if next_thread is not None:
            self.running = next_thread
            self.running.status = ThreadStatus.RUNNING
            self.running.last_scheduled = self.current_tick
            self.current_slice_remaining = self.time_slice

            # 컨텍스트 스위치 카운트
            if prev_tid is not None and prev_tid != next_thread.tid:
                self.context_switches += 1
            self.prev_running_tid = next_thread.tid

    def _update_wait_times(self):
        """대기 중인 스레드의 wait_time 증가"""
        for thread in self.threads:
            if thread.status == ThreadStatus.READY:
                thread.wait_time += 1

    def _record_state(self):
        """현재 상태 기록"""
        for thread in self.threads:
            # 도착하지 않은 스레드는 기록하지 않음
            if thread.status == ThreadStatus.BLOCKED and thread.arrival_time > self.current_tick:
                continue

            self.history.append({
                'tick': self.current_tick,
                'tid': thread.tid,
                'name': thread.name,
                'status': thread.status.name,
                'priority': getattr(thread, 'priority', None),
                'nice': thread.nice,
                'vruntime': getattr(thread, 'vruntime', 0),
                'remaining_time': thread.remaining_time,
                'wait_time': thread.wait_time,
            })

    def _all_threads_done(self) -> bool:
        """모든 스레드 완료 확인"""
        return all(t.status == ThreadStatus.TERMINATED for t in self.threads)

    def _clamp_io_duration(self, raw: int) -> int:
        """의미 있는 블로킹이 되도록 I/O 시간을 클램프"""
        if raw <= 0:
            return 0
        return max(MIN_IO_DURATION, min(MAX_IO_DURATION, raw))
