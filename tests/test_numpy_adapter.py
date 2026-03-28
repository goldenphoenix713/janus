import numpy as np

from janus import MultiverseBase
from janus.plugins.numpy import TrackedNumpyArray


class Simulation(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.weights = np.zeros(5)


def test_numpy_basic_tracking() -> None:
    """Verify that in-place mutations are caught and reversible."""
    sim = Simulation()
    assert isinstance(sim.weights, TrackedNumpyArray)

    # 1. Mutate in-place
    sim.weights[0] = 10.0
    assert sim.weights[0] == 10.0

    # 2. Undo
    sim.undo()
    assert sim.weights[0] == 0.0

    # 3. Redo
    sim.redo()
    assert sim.weights[0] == 10.0


def test_numpy_branching() -> None:
    """Verify that numpy state is isolated across branches."""
    sim = Simulation()
    sim.weights[0] = 1.0

    sim.branch("experiment")
    sim.weights[1] = 2.0
    assert sim.weights[0] == 1.0
    assert sim.weights[1] == 2.0

    sim.switch_branch("main")
    assert sim.weights[0] == 1.0
    assert sim.weights[1] == 0.0

    sim.switch_branch("experiment")
    assert sim.weights[0] == 1.0
    assert sim.weights[1] == 2.0


def test_numpy_view_tracking() -> None:
    """Verify that mutations to array views are correctly attributed to the parent."""
    sim = Simulation()
    # Create a view (slice)
    view = sim.weights[1:3]
    assert isinstance(view, TrackedNumpyArray)
    # The view should share or point to the same Janus parent

    # Mutate the view
    view[0] = 99.0
    assert sim.weights[1] == 99.0

    # Undo the mutation performed via the view
    sim.undo()
    assert sim.weights[1] == 0.0


def test_numpy_reassignment() -> None:
    """Verify that full array reassignment is also tracked."""
    sim = Simulation()
    sim.weights = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert sim.weights[0] == 1.0

    sim.undo()
    # Reverts to the original zeros(5)
    assert np.all(sim.weights == 0)
    assert len(sim.weights) == 5
