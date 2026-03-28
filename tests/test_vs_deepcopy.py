import copy
import timeit

import matplotlib.pyplot as plt

from janus import MultiverseBase


# 1. Define the Janus-tracked class
class LargeState(MultiverseBase):
    def __init__(self, size: int) -> None:
        super().__init__()
        self.data = list(range(size))


# 2. Define a standard class for deepcopy comparison
class StandardState:
    def __init__(self, size: int) -> None:
        self.data = list(range(size))


def run_benchmark() -> None:
    # Reduced sizes slightly for faster execution during dev
    sizes = [100, 1000, 10000, 100000, 500000]
    janus_times: list[float] = []
    deepcopy_times: list[float] = []

    print(f"{'Size (N)':<15} | {'Janus Snapshot (s)':<20} | {'Deepcopy (s)':<15}")
    print("-" * 55)

    for n in sizes:
        # Setup objects
        j_obj = LargeState(n)
        s_obj = StandardState(n)

        # Benchmark Janus Snapshot (O(1))
        # We time the snapshot() call which just marks a node in Rust
        j_time = (
            timeit.timeit(lambda: j_obj.create_moment_label("test"), number=10) / 10
        )
        janus_times.append(j_time)

        # Benchmark Deepcopy (O(N))
        d_time = timeit.timeit(lambda: copy.deepcopy(s_obj), number=10) / 10
        deepcopy_times.append(d_time)

        print(f"{n:<15} | {j_time:<20.8f} | {d_time:<15.8f}")

    # 3. Plotting the results
    plt.figure(figsize=(10, 6))
    plt.plot(sizes, janus_times, label="Janus Snapshot (O(1))", marker="o", linewidth=2)
    plt.plot(
        sizes, deepcopy_times, label="copy.deepcopy (O(N))", marker="x", linewidth=2
    )

    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("Object Size (Number of Elements)")
    plt.ylabel("Time (Seconds)")
    plt.title("State Capture Performance: Janus vs. Deepcopy")
    plt.legend()
    plt.grid(True, which="both", ls="-", alpha=0.5)

    output_path = "performance_comparison.png"
    plt.savefig(output_path)
    print(f"\nBenchmark complete. Chart saved as '{output_path}'.")


if __name__ == "__main__":
    run_benchmark()
