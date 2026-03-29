import time
from typing import Any

from janus import MultiverseBase, TimelineBase


def test_mutation_o1_scaling() -> None:
    """Verify that mutation logging (setattr) is O(1) relative to history depth."""

    class State(TimelineBase):
        def __init__(self) -> None:
            super().__init__(max_history=100_000)
            self.x = 0

    obj = State()

    # 1. Measure latency at small history
    start_early = time.perf_counter()
    for i in range(100):
        obj.x = i
    end_early = time.perf_counter()
    duration_early = (end_early - start_early) / 100

    # 2. Grow history significantly
    for i in range(100, 10_000):
        obj.x = i

    # 3. Measure latency at large history
    start_late = time.perf_counter()
    for i in range(10_000, 10_100):
        obj.x = i
    end_late = time.perf_counter()
    duration_late = (end_late - start_late) / 100

    # O(1) Assertion: Latency should not have exploded.
    # We allow a small margin for cache effects, but it shouldn't be 10x slower.
    assert duration_late < duration_early * 5, (
        f"Mutation latency scaled linearly! {duration_late} vs {duration_early}"
    )


def test_branching_o1_scaling() -> None:
    """Verify that branching is efficient relative to history depth."""

    class State(MultiverseBase):
        def __init__(self) -> None:
            super().__init__(max_history=100_000)
            self.x = 0

    obj = State()

    # 1. Initial branch
    obj.branch("early_branch")

    # 2. Grow history
    for i in range(10_000):
        obj.x = i

    # 3. Branch again
    start_late = time.perf_counter()
    obj.branch("late_branch")
    end_late = time.perf_counter()
    duration_late = end_late - start_late

    # Branching should still be extremely fast.
    assert duration_late < 0.01, f"Branching too slow: {duration_late}s"


def test_pruning_performance() -> None:
    """Verify that automated pruning doesn't cause a spike in mutation latency."""

    class State(TimelineBase):
        def __init__(self) -> None:
            # Small max_history triggers frequent pruning
            super().__init__(max_history=100)
            self.x = 0

    obj = State()

    latencies = []
    for i in range(1000):
        start = time.perf_counter()
        obj.x = i
        latencies.append(time.perf_counter() - start)

    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)

    # Even with pruning, avg latency should stay reasonable.
    # 5ms is generous enough to tolerate slow CI runners (e.g. Windows Azure VMs)
    # while still catching any genuine O(n) regression.
    assert avg_latency < 0.005
    assert max_latency < 0.05


def test_bench_mutation(benchmark: Any) -> None:
    class State(TimelineBase):
        def __init__(self) -> None:
            super().__init__()
            self.x = 0

    obj = State()

    def do_mutate() -> None:
        obj.x = 1

    benchmark(do_mutate)


def test_bench_branching(benchmark: Any) -> None:
    class State(MultiverseBase):
        def __init__(self) -> None:
            super().__init__()
            self.x = 0

    obj = State()
    obj.x = 1
    branch_count = 0

    def do_branch() -> None:
        nonlocal branch_count
        branch_count += 1
        obj.branch(f"branch_{branch_count}")

    benchmark(do_branch)


def test_bench_timeline_extraction(benchmark: Any) -> None:
    class State(MultiverseBase):
        def __init__(self) -> None:
            super().__init__()
            self.x = 0

    obj = State()
    for i in range(100):
        obj.x = i

    def do_extract() -> None:
        obj.extract_timeline()

    benchmark(do_extract)
