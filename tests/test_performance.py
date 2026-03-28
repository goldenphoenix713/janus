import statistics
import time

from janus import MultiverseBase


class BenchTarget(MultiverseBase):
    def __init__(self) -> None:
        self.val = 0


def benchmark_logging(depth_steps: list[int] | None = None) -> None:
    if depth_steps is None:
        depth_steps = [1000, 10000, 50000, 100000]

    obj = BenchTarget()
    results: dict[int, float] = {}

    print(f"{'Depth':>10} | {'Mean Latency (ns)':>20} | {'Std Dev':>10}")
    print("-" * 50)

    current_depth = 0
    for target_depth in depth_steps:
        latencies: list[int] = []
        to_add = target_depth - current_depth

        for _ in range(to_add):
            start = time.perf_counter_ns()
            obj.val += 1
            end = time.perf_counter_ns()
            latencies.append(end - start)

        mean_lat = statistics.mean(latencies)
        std_dev = statistics.stdev(latencies)
        results[target_depth] = mean_lat
        current_depth = target_depth

        print(f"{target_depth:>10} | {mean_lat:>20.2f} | {std_dev:>10.2f}")

    # Simple O(1) verify: check if 100k is significantly slower than 1k
    ratio = results[depth_steps[-1]] / results[depth_steps[0]]
    print(f"\nLatency Ratio (100k/1k): {ratio:.2f}x")
    if ratio < 1.5:
        print(
            "O(1) Verification Passed: Logging latency is independent of history depth."
        )
        print(
            "O(1) Verification Warning: Logging latency may be increasing with "
            "history depth."
        )


def benchmark_restoration(distance: int = 10000, total_depth: int = 50000) -> None:
    obj = BenchTarget()
    # Build history
    obj.branch("root")
    for _ in range(total_depth):
        obj.val += 1

    obj.branch("deep_end")

    # Measure restoration
    start = time.perf_counter()
    obj.switch_branch("root")
    end = time.perf_counter()

    print(f"\nRestoration Time ({total_depth} nodes back to root): {end - start:.4f}s")
    print(f"Time per node restoration: {(end - start) / total_depth * 1_000_000:.2f}μs")


if __name__ == "__main__":
    print("--- Janus O(1) Logging Benchmark ---\n")
    benchmark_logging()
    print("\n--- Janus Restoration Benchmark ---")
    benchmark_restoration()
