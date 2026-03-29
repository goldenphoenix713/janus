import copy
import timeit

import matplotlib.pyplot as plt

from janus import TimelineBase


# 1. Define the Janus-tracked class
class LargeState(TimelineBase):
    def __init__(self, size: int) -> None:
        super().__init__()
        self.data = list(range(size))


# 2. Define a standard class for deepcopy comparison
class StandardState:
    def __init__(self, size: int) -> None:
        self.data = list(range(size))


def run_benchmark() -> None:
    sizes = [100, 1000, 10000, 100000]
    janus_snapshot_times: list[float] = []
    janus_mutation_times: list[float] = []
    deepcopy_times: list[float] = []

    header = (
        f"{'Size (N)':<10} | {'Snapshot (s)':<15} | "
        f"{'Mutation (s)':<15} | {'Deepcopy (s)':<12}"
    )
    print(header)
    print("-" * len(header))

    for n in sizes:
        # Setup objects
        j_obj = LargeState(n)
        s_obj = StandardState(n)

        # 1. Benchmark Snapshot (O(1))
        j_snap = (
            timeit.timeit(lambda: j_obj.create_moment_label(f"m_{n}"), number=10) / 10
        )
        janus_snapshot_times.append(j_snap)

        # 2. Benchmark Mutation (O(1))
        # We mutate a single attr. In standard Python, this is O(1).
        # We verify Janus overhead is also O(1).
        j_mut = timeit.timeit(lambda: setattr(j_obj, "x", 1), number=1000) / 1000
        janus_mutation_times.append(j_mut)

        # 3. Benchmark Deepcopy (O(N))
        d_time = timeit.timeit(lambda: copy.deepcopy(s_obj), number=10) / 10
        deepcopy_times.append(d_time)

        print(f"{n:<10} | {j_snap:<15.8f} | {j_mut:<15.8f} | {d_time:<12.8f}")

    # 3. Plotting the results
    plt.figure(figsize=(10, 6))
    plt.plot(sizes, janus_snapshot_times, label="Janus Snapshot (O(1))", marker="o")
    plt.plot(sizes, janus_mutation_times, label="Janus Mutation (O(1))", marker="s")
    plt.plot(sizes, deepcopy_times, label="copy.deepcopy (O(N))", marker="x")

    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("Object Size / History Depth")
    plt.ylabel("Time (Seconds)")
    plt.title("Janus Performance Scalability")
    plt.legend()
    plt.grid(True, which="both", ls="-", alpha=0.5)

    plt.savefig("performance_comparison.png")
    print("\nBenchmark complete. Chart saved as 'performance_comparison.png'.")


if __name__ == "__main__":
    run_benchmark()
