"""스레드 시뮬레이션 (3개 스케줄러 공통)"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class ThreadStatus(Enum):
    RUNNING = 0
    READY = 1
    BLOCKED = 2
    TERMINATED = 3

@dataclass
class Thread:
    """시뮬레이션 스레드"""
    tid: int
    name: str
    status: ThreadStatus = ThreadStatus.READY

    # 공통 속성
    nice: int = 0  # -20 ~ 19

    # Basic Priority 필드
    priority: Optional[int] = None  # 0-63 (None이면 nice로 계산)

    # MLFQS 필드
    recent_cpu: int = 0  # 고정소수점

    # CFS 필드
    vruntime: int = 0
    weight: int = 1024

    # 워크로드
    arrival_time: int = 0
    burst_time: int = 0
    remaining_time: int = 0
    io_frequency: int = 0
    io_duration: int = 0
    io_remaining: int = 0  # I/O 남은 시간
    cpu_since_io: int = 0  # 마지막 I/O 이후 CPU 사용량

    # 통계
    start_time: int = -1
    finish_time: int = -1
    wait_time: int = 0
    last_scheduled: int = -1
    # 시뮬레이션 전체 컨텍스트 스위치 수 (메트릭 계산용)
    context_switches: int = 0

    def __repr__(self):
        return (f"Thread({self.tid}, pri={self.priority}, "
                f"nice={self.nice}, vr={self.vruntime})")
