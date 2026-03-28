from __future__ import annotations

from typing import Any

import pytest

from janus import MultiverseBase


class Simulation(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.data: list[Any] = []
        self.status: str = "init"


def test_branch_lifecycle() -> None:
    """Verify that branches can be created, listed, and tracked as current."""
    sim = Simulation()
    assert sim.current_branch == "main"
    assert sim.list_branches() == ["main"]

    # 1. Create multiple branches
    sim.branch("experiment-a")
    assert sim.current_branch == "experiment-a"

    sim.branch("experiment-b")
    assert sim.current_branch == "experiment-b"

    branches = sim.list_branches()
    assert "experiment-a" in branches
    assert "experiment-b" in branches
    assert "main" in branches
    assert len(branches) == 3

    # 2. Switch and verify current_branch
    sim.switch_branch("experiment-a")
    assert sim.current_branch == "experiment-a"

    sim.switch_branch("main")
    assert sim.current_branch == "main"


def test_branch_deletion() -> None:
    """Verify that branches can be deleted only when not active."""
    sim = Simulation()
    sim.branch("to-delete")
    assert "to-delete" in sim.list_branches()

    sim.switch_branch("main")
    sim.delete_branch("to-delete")
    assert "to-delete" not in sim.list_branches()
    assert sim.list_branches() == ["main"]


def test_deletion_guards() -> None:
    """Verify safety guards for branch deletion."""
    sim = Simulation()
    sim.branch("active-branch")

    # Cannot delete active branch
    error_msg = "Cannot delete active branch: 'active-branch'"
    with pytest.raises(ValueError, match=error_msg):
        sim.delete_branch("active-branch")

    # Cannot delete non-existent branch
    with pytest.raises(KeyError, match="Branch 'nonexistent' not found"):
        sim.delete_branch("nonexistent")


def test_branch_independent_state() -> None:
    """Verify that mutations on one branch do not affect others."""
    sim = Simulation()
    sim.status = "stage-1"
    sim.data.append(1)

    sim.branch("fork-A")
    sim.status = "stage-A"
    sim.data.append(2)
    assert sim.status == "stage-A"
    assert sim.data == [1, 2]

    sim.switch_branch("main")
    assert sim.status == "stage-1"
    assert sim.data == [1]

    sim.branch("fork-B")
    sim.status = "stage-B"
    sim.data.append(3)
    assert sim.status == "stage-B"
    assert sim.data == [1, 3]

    sim.switch_branch("fork-A")
    assert sim.status == "stage-A"
    assert sim.data == [1, 2]


def test_moment_reversion() -> None:
    """Verify that create_moment_label creates a static tag that does not move."""
    sim = Simulation()
    sim.create_moment_label("stable")
    sim.status = "experimental"
    assert sim.status == "experimental"

    sim.jump_to("stable")
    assert sim.status == "init"
    # Even after jumping to a moment, we are still on the same branch
    assert sim.current_branch == "main"
