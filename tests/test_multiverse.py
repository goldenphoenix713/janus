from typing import Any

import pytest

from janus import MultiverseBase


class Hero(MultiverseBase):
    def __init__(self, name: str, hp: int) -> None:
        super().__init__()
        self.name = name
        self.hp = hp
        self.inventory: list[Any] = []


def test_basic_branching() -> None:
    h = Hero("Arthur", 100)
    assert h.name == "Arthur"

    # These will be stubs for now since engine.rs logic is minimal
    h.branch("chaos-timeline")
    h.hp = 50

    h.jump_to("main")
    # assert h.hp == 100 # This will fail until apply_inverse is implemented


def test_delete_branch() -> None:
    h = Hero("Arthur", 100)
    h.branch("chaos-timeline")
    h.hp = 50
    assert h.hp == 50
    assert h.current_branch == "chaos-timeline"
    assert "chaos-timeline" in h.list_branches()
    assert "main" in h.list_branches()
    assert len(h.list_branches()) == 2

    h.jump_to("main")
    assert h.hp == 100
    assert h.current_branch == "main"

    h.delete_branch("chaos-timeline")
    assert h.current_branch == "main"
    assert h.hp == 100
    assert h.list_branches() == ["main"]


def test_cannot_delete_active_branch() -> None:
    h = Hero("Arthur", 100)
    h.branch("chaos-timeline")
    with pytest.raises(ValueError) as e:
        h.delete_branch("chaos-timeline")
    assert e.value.args[0] == "Cannot delete active branch: 'chaos-timeline'"


def test_cannot_delete_nonexistent_branch() -> None:
    h = Hero("Arthur", 100)
    with pytest.raises(KeyError) as excinfo:
        h.delete_branch("nonexistent-branch")
    assert excinfo.value.args[0] == "Branch 'nonexistent-branch' not found"
