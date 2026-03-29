import matplotlib as mpl

mpl.use("Agg")  # Use non-interactive backend to avoid Tk dependency on Windows CI

import matplotlib.pyplot as plt
import pytest
from matplotlib.figure import Figure

from janus import MultiverseBase


class Simulation(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.x = 0


def test_viz_mpl_basic() -> None:
    sim = Simulation()
    sim.branch("feature")
    sim.x = 10
    sim.jump_to("main")
    sim.x = 5

    # Render with matplotlib
    fig = sim.plot(backend="matplotlib", title="Test Graph")

    assert isinstance(fig, Figure)
    assert fig.get_axes()[0].get_title() == "Test Graph"

    plt.close(fig)


def test_viz_mpl_figsize() -> None:
    sim = Simulation()
    fig = sim.plot(backend="matplotlib", figsize=(12, 12))
    assert fig.get_size_inches().tolist() == [12, 12]
    plt.close(fig)


if __name__ == "__main__":
    pytest.main([__file__])
