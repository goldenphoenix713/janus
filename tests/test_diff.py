from janus import MultiverseBase


class SimpleObj(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.x = 0
        self.y = 0
        self.data: list[int] = []


def test_linear_attribute_diff() -> None:
    obj = SimpleObj()
    obj.x = 0
    obj.create_moment_label("v0")

    obj.x = 10
    obj.y = 20
    obj.create_moment_label("v1")

    diff = obj.diff("v0", "v1")

    assert "x" in diff["attributes"]
    assert diff["attributes"]["x"]["old"] == 0
    assert diff["attributes"]["x"]["new"] == 10

    assert "y" in diff["attributes"]
    assert diff["attributes"]["y"]["old"] == 0
    assert diff["attributes"]["y"]["new"] == 20


def test_multiversal_diff() -> None:
    obj = SimpleObj()
    obj.x = 0
    obj.create_moment_label("root")

    # Branch A
    obj.x = 1
    obj.create_moment_label("branch_a")

    # Branch B
    obj.jump_to("root")
    obj.x = 2
    obj.create_moment_label("branch_b")

    # Diff between A and B
    # A has x=1, B has x=2. LCA is "root" (x=0).
    # Path: A -> root (x=0) -> B (x=2)
    diff = obj.diff("branch_a", "branch_b")

    assert "x" in diff["attributes"]
    # Net change from A to B
    assert diff["attributes"]["x"]["old"] == 1
    assert diff["attributes"]["x"]["new"] == 2


def test_container_diff_ops() -> None:
    obj = SimpleObj()
    obj.data = [1, 2]
    obj.create_moment_label("start")

    obj.data.append(3)
    obj.data.pop(0)
    obj.create_moment_label("end")

    diff = obj.diff("start", "end")

    # Container operations are returned as a list of raw op dicts
    ops = diff["container_operations"]
    assert len(ops) >= 2

    # Verify we can find the append and pop
    op_types = [op["type"] for op in ops]
    assert "list_op" in op_types
