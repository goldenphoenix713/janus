from janus import MultiverseBase


class SimpleObj(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.x = 0
        self.y = 0
        self.data: list[int] = []


def test_basic_attribute_squash() -> None:
    obj = SimpleObj()
    obj.x = 0
    obj.create_moment_label("start")

    # Series of micro-updates
    obj.x = 1
    obj.create_moment_label("m1")
    obj.x = 2
    obj.create_moment_label("m2")
    obj.x = 3
    obj.create_moment_label("end")

    assert obj.x == 3
    assert len(obj.get_labeled_moments()) == 5  # genesis, start, m1, m2, end

    # Squash from start to end
    obj.squash("start", "end")

    # State should be preserved
    assert obj.x == 3

    # Intermediate labels should be merged or cleaned up
    # In my current design, all labels in the range move to the new squashed node
    # or just the end label survives. Let's say all survive but point to the same node.
    labels = obj.get_labeled_moments()
    assert "start" in labels
    assert "end" in labels
    assert "m1" in labels
    assert "m2" in labels

    # Undo should jump back before "start" (as a single unit)
    # Actually, if we squash [start...end], then the new node replaces that whole range.
    # So undoing "end" will go to parent of "start".
    obj.undo()
    assert obj.x == 0

    obj.redo()
    assert obj.x == 3


def test_container_squash() -> None:
    obj = SimpleObj()
    obj.data = []
    obj.create_moment_label("anchor")
    obj.x = 999  # Dummy to separate anchor from start
    obj.create_moment_label("start")

    obj.data.append(1)
    obj.data.append(2)
    obj.data.pop(0)
    obj.create_moment_label("end")

    assert obj.data == [2]

    obj.squash("start", "end")
    assert obj.data == [2]

    obj.undo()
    assert obj.data == []

    obj.redo()
    assert obj.data == [2]


def test_branch_migration_after_squash() -> None:
    obj = SimpleObj()
    obj.x = 0
    obj.create_moment_label("start")  # node 1
    obj.x = 1  # node 2
    obj.branch("side_branch")  # branch at node 2
    obj.x = 2
    obj.create_moment_label("end")  # node 3

    # Initial state
    assert obj.x == 2
    assert "side_branch" in obj.list_branches()

    # Squash start-end
    obj.squash("start", "end")

    # The labels "start", "end" and branch "side_branch" should all
    # now point to the squashed node
    obj.switch_branch("side_branch")
    assert obj.x == 2
    assert "side_branch" in obj.list_branches()
