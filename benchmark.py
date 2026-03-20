import copy
import timeit

import matplotlib.pyplot as plt

from janus import janus


# 1. Define the Janus-tracked class
@janus
class LargeState:
    def __init__(self, size):
        self.data = list(range(size))


# 2. Define a standard class for deepcopy comparison
class StandardState:
    def __init__(self, size):
        self.data = list(range(size))


def run_benchmark():
    sizes = [100, 1000, 10000, 100000, 1000000]
    janus_times = []
    deepcopy_times = []

    print(f"{'Size (N)':<15} | {'Janus Snapshot (s)':<20} | {'Deepcopy (s)':<15}")
    print("-" * 55)

    for n in sizes:
        # Setup objects
        j_obj = LargeState(n)
        s_obj = StandardState(n)

        # Benchmark Janus Snapshot (O(1))
        # We time the snapshot() call which just marks a length in Rust
        j_time = timeit.timeit(lambda: j_obj.snapshot("test"), number=100) / 100  # type: ignore
        janus_times.append(j_time)

        # Benchmark Deepcopy (O(N))
        d_time = timeit.timeit(lambda: copy.deepcopy(s_obj), number=100) / 100
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

    plt.savefig("performance_comparison.png")
    print("\nBenchmark complete. Chart saved as 'performance_comparison.png'.")


if __name__ == "__main__":
    run_benchmark()
