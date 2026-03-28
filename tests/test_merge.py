from __future__ import annotations

import pytest

from janus import MultiverseBase


class Simulation(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.x = 0
        self.y = 0


def test_no_conflict_merge() -> None:
    sim = Simulation()

    # Split
    sim.branch("feature")
    sim.jump_to("main")
    sim.x = 10  # main head

    sim.jump_to("feature")
    sim.y = 20  # feature head

    # Merge feature into main
    sim.jump_to("main")
    sim.merge("feature")

    # Shared state should have both
    assert sim.x == 10
    assert sim.y == 20

    # Verify undo goes back to 'main' before merge
    sim.undo()
    assert sim.x == 10
    assert sim.y == 0


def test_merge_strategy_overshadow() -> None:
    sim = Simulation()
    sim.x = 1

    sim.branch("conflict_branch")
    sim.jump_to("main")
    sim.x = 2

    sim.jump_to("conflict_branch")
    sim.x = 3

    # Merge source wins
    sim.jump_to("main")
    sim.merge("conflict_branch", strategy="overshadow")
    assert sim.x == 3


def test_merge_strategy_preserve() -> None:
    sim = Simulation()
    sim.x = 1

    sim.branch("conflict_branch")
    sim.jump_to("main")
    sim.x = 2

    sim.jump_to("conflict_branch")
    sim.x = 3

    # Merge target wins
    sim.jump_to("main")
    sim.merge("conflict_branch", strategy="preserve")
    assert sim.x == 2  # Kept main's value


def test_merge_strategy_strict() -> None:
    sim = Simulation()
    sim.x = 1

    sim.branch("conflict_branch")
    sim.jump_to("main")
    sim.x = 2

    sim.jump_to("conflict_branch")
    sim.x = 3

    # Merge strict should raise
    sim.jump_to("main")
    with pytest.raises(ValueError, match="Merge conflict on attribute 'x'"):
        sim.merge("conflict_branch", strategy="strict")


def test_complex_dag_merge() -> None:
    sim = Simulation()

    # Chain: A(x=1) -> B(x=2)
    sim.x = 1
    sim.branch("b1")
    sim.jump_to("b1")
    sim.x = 2

    # Chain: A(x=1) -> C(y=10)
    sim.jump_to("main")
    sim.branch("b2")
    sim.jump_to("b2")
    sim.y = 10

    # Merge b1 into b2 -> D(x=2, y=10)
    sim.merge("b1")
    assert sim.x == 2
    assert sim.y == 10

    # Now merge D back into main
    sim.jump_to("main")
    sim.merge("b2")
    assert sim.x == 2
    assert sim.y == 10
