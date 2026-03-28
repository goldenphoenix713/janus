from __future__ import annotations

import time

from janus import MultiverseBase


class Simulation(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.x = 0
        self.y = 0


def test_timeline_attribute_filtering() -> None:
    sim = Simulation()

    # Sequence of mixed mutations
    sim.x = 1
    sim.y = 10
    sim.x = 2
    sim.y = 20

    # Extract full timeline
    full = sim.extract_timeline()
    # __init__ (2) + mixed mutations (4) = 6 ops total
    assert len(full) == 6

    # Extract only 'x'
    only_x = sim.extract_timeline(filter_attr="x")
    # x=0 in __init__, x=1, x=2 -> 3 ops
    assert len(only_x) == 3

    # Extract only 'y'
    only_y = sim.extract_timeline(filter_attr="y")
    # y=0 in __init__, y=10, y=20 -> 3 ops
    assert len(only_y) == 3
    assert all(op["name"] == "y" for op in only_y)
    assert [op["new"] for op in only_y] == [0, 10, 20]

    # Extract multiple
    both = sim.extract_timeline(filter_attr=["x", "y"])
    assert len(both) == 6


def test_timeline_rich_metadata() -> None:
    sim = Simulation()
    start_time = time.time()

    sim.tag_moment(step="init")
    sim.x = 1
    sim.tag_moment(step="mutation")

    timeline = sim.extract_timeline()
    # Check that at least one event in the timeline (should be the last one)
    # has the 'mutation' tag
    found = False
    for event in timeline:
        if event["metadata"].get("step") == "mutation":
            found = True
            assert event["timestamp"] >= int(start_time)
            assert event["node_id"] > 0
    assert found


def test_multiversal_search() -> None:
    sim = Simulation()

    # Setup multiple branches with metadata
    sim.tag_moment(common="true", branch="root")
    sim.label_node("root_node")

    sim.branch("experiment_a")
    sim.x = 100
    sim.tag_moment(common="true", score=0.95, branch="a")
    sim.label_node("node_a")

    sim.jump_to("main")
    sim.branch("experiment_b")
    sim.x = 200
    sim.tag_moment(common="true", score=0.80, branch="b")
    sim.create_moment_label("node_b")  # Just another way to label

    # Search by single criterion
    matches = sim.find_moments(common="true")
    # Should find root_node, node_a, node_b
    assert len(matches) == 3

    # Search by multiple criteria
    matches_high_score = sim.find_moments(common="true", score=0.95)
    assert len(matches_high_score) == 1
    # Depending on how label resolution works, it might be the label or ID
    assert "experiment_a" in matches_high_score or "node_a" in matches_high_score

    # Search with no results
    assert sim.find_moments(score=1.0) == []
