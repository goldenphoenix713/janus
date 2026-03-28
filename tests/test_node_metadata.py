from __future__ import annotations

from typing import Any

from janus import MultiverseBase, TimelineBase


def test_tag_moment_linear() -> None:
    class Model(TimelineBase):
        def __init__(self) -> None:
            super().__init__()
            self.x = 0

    m = Model()
    m.x = 10
    m.tag_moment(description="Step 1", value=42)

    tags = m.get_all_tags()
    assert tags["description"] == "Step 1"
    assert tags["value"] == 42

    m.x = 20
    m.tag_moment(description="Step 2")

    assert m.get_all_tags()["description"] == "Step 2"

    m.undo()
    assert m.x == 10
    assert m.get_all_tags()["description"] == "Step 1"

    m.redo()
    assert m.x == 20
    assert m.get_all_tags()["description"] == "Step 2"


def test_tag_moment_multiversal() -> None:
    class Model(MultiverseBase):
        def __init__(self) -> None:
            super().__init__()
            self.val = 0

    m = Model()
    m.val = 1
    m.tag_moment(v=1)

    m.branch("alt")
    m.val = 2
    m.tag_moment(v=2)

    assert m.get_all_tags()["v"] == 2

    m.jump_to("main")
    assert m.val == 1
    assert m.get_all_tags()["v"] == 1

    m.jump_to("alt")
    assert m.val == 2
    assert m.get_all_tags()["v"] == 2


def test_complex_metadata() -> None:
    class Model(TimelineBase):
        def __init__(self) -> None:
            super().__init__()
            self.data: list[Any] = []

    m = Model()
    complex_data = {"metrics": [0.1, 0.2], "params": {"lr": 0.001}}
    m.tag_moment(run_data=complex_data)

    retrieved = m.get_all_tags()["run_data"]
    assert retrieved == complex_data
    assert retrieved["metrics"][1] == 0.2


def test_arbitrary_node_tags() -> None:
    class Model(MultiverseBase):
        def __init__(self) -> None:
            super().__init__()
            self.val = 0

    m = Model()
    m.val = 1
    m.tag_moment(v="genesis")
    m.label_node("m1")

    m.val = 2
    m.tag_moment(v="step2")

    # Check current tags
    assert m.get_all_tags()["v"] == "step2"

    # Check arbitrary node tags using label
    assert m.get_all_tags(label="m1")["v"] == "genesis"

    # Check specific tag
    assert m.get_moment_tag("v", label="m1") == "genesis"

    m.branch("experiment")
    m.val = 3
    m.tag_moment(type="exploratory")

    assert m.get_all_tags(label="main")["v"] == "step2"
    assert m.get_all_tags()["type"] == "exploratory"
