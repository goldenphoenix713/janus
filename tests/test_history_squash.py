from __future__ import annotations

from janus import MultiverseBase


class Simulation(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.x = 0
        self.y = 0


def test_linear_squash() -> None:
    sim = Simulation()

    # 3 updates to x
    sim.x = 1
    sim.x = 2
    sim.x = 3

    # Before squash: timeline should have 3 ops (excluding __init__)
    # Note: sim.x = 0 happened in __init__
    timeline = sim.extract_timeline()
    # x=0, x=1, x=2, x=3, y=0 (wait, y=0 also in __init__)
    # Actually, sim.x = 0 is node 1, sim.y = 0 is node 2
    # sim.x = 1 is node 3...
    assert len(timeline) == 5

    # Squash the current branch
    sim.squash()

    # After squash: the sequence [x=1, x=2, x=3] should be one node
    # The stable ancestor is node 2 (y=0).
    # Nodes 3, 4, 5 are squashed into a new node 6.
    new_timeline = sim.extract_timeline()
    # Expect: node 6 (x=3, y=0 consolidated)
    # The list contains the two consolidated operations.
    assert len(new_timeline) == 2

    # Verify final state
    assert sim.x == 3
    assert sim.y == 0

    # Verify undo leaps over squash
    sim.undo()
    assert sim.x is None
    assert sim.y is None


def test_multi_attr_squash() -> None:
    sim = Simulation()

    sim.x = 10
    sim.y = 100
    sim.x = 20
    sim.y = 200

    sim.squash()

    timeline = sim.extract_timeline()
    # One node (consolidated) containing 2 operations (x and y)
    assert len(timeline) == 2

    # The consolidated node should have both changes
    # Since we consolidate in Rust, technically they are multiple deltas in ONE node.
    # But extract_timeline yields operations.
    # Search for x and y in the last node segment?
    # Actually, extract_timeline yields a list of dicts, one per operation.
    # So the last two dicts should have the same node_id.
    assert timeline[-1]["node_id"] == timeline[-2]["node_id"]
    assert {op["name"] for op in timeline[-2:]} == {"x", "y"}
    assert {op["new"] for op in timeline[-2:]} == {20, 200}


def test_squash_boundary_protection() -> None:
    sim = Simulation()
    sim.x = 1

    # Create a branch - then split it by mutating main
    sim.branch("experiment")
    sim.jump_to("main")
    sim.y = 999  # bifurcation point at Node 3 (x=1)

    sim.jump_to("experiment")
    sim.x = 10
    sim.x = 20

    # Squash 'experiment'
    sim.squash("experiment")

    # Timeline should be [x=0, y=0, x=1] + [x=20 consolidated]
    # Total ops: 3 (init+main segment) + 1 (consolidated expr) = 4
    tl = sim.extract_timeline("experiment")
    assert len(tl) == 4
    assert [op["new"] for op in tl] == [0, 0, 1, 20]

    # Main should be untouched
    sim.jump_to("main")
    assert sim.x == 1
    tl_main = sim.extract_timeline("main")
    assert len(tl_main) == 4


def test_squash_metadata_preservation() -> None:
    sim = Simulation()
    sim.x = 1
    sim.tag_moment(priority="high")
    sim.x = 2
    sim.tag_moment(priority="low")

    sim.squash()

    # Metadata from the leaf (low) should be preserved
    assert sim.get_moment_tag("priority") == "low"
