from typing import Any

import pytest

from janus import MultiverseBase


class Simulation(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.data: list[Any] = [1, 2, 3]
        self.config: dict[str, Any] = {"a": 1, "b": 2}


def test_list_merge_independent_inserts() -> None:
    sim = Simulation()
    sim.branch("feature")

    # Target (main): Insert at end
    sim.jump_to("main")
    sim.data.append(4)  # [1, 2, 3, 4]

    # Source (feature): Insert at beginning
    sim.jump_to("feature")
    sim.data.insert(0, 0)  # [0, 1, 2, 3]

    # Merge feature into main
    sim.jump_to("main")
    sim.merge("feature")

    # Result should be [0, 1, 2, 3, 4]
    # Simple append works here because indices don't overlap
    assert sim.data == [0, 1, 2, 3, 4]


def test_list_merge_shifting_indices() -> None:
    sim = Simulation()
    sim.branch("feature")

    # Target (main): Insert at 0
    sim.jump_to("main")
    sim.data.insert(0, "prefix")  # ["prefix", 1, 2, 3]

    # Source (feature): Insert at 2
    sim.jump_to("feature")
    sim.data.insert(2, "mid")  # [1, 2, "mid", 3]

    # Merge feature into main
    sim.jump_to("main")
    sim.merge("feature")

    # If source op is applied blindly: data.insert(2, "mid")
    # on ["prefix", 1, 2, 3]
    # Result: ["prefix", 1, "mid", 2, 3].
    # BUT "mid" was originally between 2 and 3.
    # In the new list, it should be at index 3.
    # Expected: ["prefix", 1, 2, "mid", 3]
    assert sim.data == ["prefix", 1, 2, "mid", 3]


def test_dict_merge_conflict() -> None:
    sim = Simulation()
    sim.branch("feature")

    sim.jump_to("main")
    sim.config["a"] = 10

    sim.jump_to("feature")
    sim.config["a"] = 20

    sim.jump_to("main")
    # This should raise a conflict if using "strict"
    with pytest.raises(ValueError, match="conflict"):
        sim.merge("feature", strategy="strict")

    # Default (overshadow) should pick 20
    sim.merge("feature")
    assert sim.config["a"] == 20


def test_dict_independent_keys() -> None:
    sim = Simulation()
    sim.branch("feature")

    sim.jump_to("main")
    sim.config["c"] = 3

    sim.jump_to("feature")
    sim.config["d"] = 4

    sim.jump_to("main")
    sim.merge("feature")

    assert sim.config == {"a": 1, "b": 2, "c": 3, "d": 4}


if __name__ == "__main__":
    pytest.main([__file__])
