from pathlib import Path

from janus import MultiverseBase, TimelineBase


class SimpleObj(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.val = 0
        self.name = "root"


class LinearObj(TimelineBase):
    def __init__(self) -> None:
        super().__init__()
        self.val = 0


def test_multiverse_persistence(tmp_path: Path) -> None:
    save_path = tmp_path / "test_mv.jns"

    # 1. Setup original object with complex history
    obj = SimpleObj()
    obj.val = 10
    obj.label_node("start")

    obj.branch("feature")
    obj.val = 20
    obj.name = "feature_branch"
    obj.label_node("feat_end")

    obj.jump_to("start")
    obj.val = 30
    obj.label_node("main_end")

    # Save it
    obj.save(save_path)
    assert save_path.exists()

    # 2. Load into new object
    new_obj = SimpleObj()
    new_obj.load(save_path)

    # Check current state (should be at "main_end")
    assert new_obj.val == 30
    assert new_obj.name == "root"

    # Check labels
    labels = new_obj.list_nodes()
    assert "start" in labels
    assert "feat_end" in labels
    assert "main_end" in labels

    # Jump to feature branch
    new_obj.jump_to("feat_end")
    assert new_obj.val == 20
    assert new_obj.name == "feature_branch"

    # Jump back to start
    new_obj.jump_to("start")
    assert new_obj.val == 10
    assert new_obj.name == "root"


def test_linear_persistence(tmp_path: Path) -> None:
    save_path = tmp_path / "test_linear.jns"

    obj = LinearObj()
    obj.val = 1
    obj.val = 2
    obj.label_node("checkpoint")
    obj.val = 3

    obj.save(save_path)

    new_obj = LinearObj()
    new_obj.load(save_path)

    assert new_obj.val == 3
    new_obj.undo()
    assert new_obj.val == 2

    new_obj.jump_to("checkpoint")
    assert new_obj.val == 2


def test_container_persistence(tmp_path: Path) -> None:
    save_path = tmp_path / "test_cont.jns"

    obj = SimpleObj()
    obj.data = [1, 2, 3]  # Becomes TrackedList
    obj.info = {"a": 1}  # Becomes TrackedDict

    obj.label_node("init")
    obj.data.append(4)  # type: ignore[attr-defined]
    obj.info["b"] = 2  # type: ignore[attr-defined]

    obj.save(save_path)

    new_obj = SimpleObj()
    new_obj.load(save_path)

    assert len(new_obj.data) == 4  # type: ignore[attr-defined]
    assert new_obj.data[3] == 4  # type: ignore[attr-defined]
    assert new_obj.info["b"] == 2  # type: ignore[attr-defined]

    new_obj.jump_to("init")
    assert len(new_obj.data) == 3  # type: ignore[attr-defined]
    assert "b" not in new_obj.info  # type: ignore[attr-defined]
