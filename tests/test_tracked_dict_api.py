from janus.base import MultiverseBase


class State(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.data: dict[str, int | str] = {"a": 1, "b": 2}


def test_tracked_dict_basic_mutation() -> None:
    s = State()
    assert s.data["a"] == 1

    s.data["a"] = 10
    assert s.data["a"] == 10

    s.undo()
    assert s.data["a"] == 1


def test_tracked_dict_update() -> None:
    s = State()
    s.data.update({"b": 20, "c": 30})
    assert s.data["b"] == 20
    assert s.data["c"] == 30

    s.undo()
    assert s.data["b"] == 2
    assert "c" not in s.data


def test_tracked_dict_pop() -> None:
    s = State()
    val = s.data.pop("a")
    assert val == 1
    assert "a" not in s.data

    s.undo()
    assert s.data["a"] == 1


def test_tracked_dict_popitem() -> None:
    s = State()
    initial_len = len(s.data)
    key, val = s.data.popitem()
    assert len(s.data) == initial_len - 1

    s.undo()
    assert len(s.data) == initial_len
    assert s.data[key] == val


def test_tracked_dict_setdefault() -> None:
    s = State()
    # Key exists
    val = s.data.setdefault("a", 100)
    assert val == 1
    assert s.data["a"] == 1

    # Key doesn't exist
    val = s.data.setdefault("c", 300)
    assert val == 300
    assert s.data["c"] == 300

    s.undo()
    assert "c" not in s.data


def test_tracked_dict_clear() -> None:
    s = State()
    s.data.clear()
    assert len(s.data) == 0

    s.undo()
    assert s.data == {"a": 1, "b": 2}


def test_tracked_dict_utilities() -> None:
    s = State()
    assert "a" in s.data
    assert list(s.data.keys()) == ["a", "b"] or list(s.data.keys()) == ["b", "a"]
    assert 1 in s.data.values()
    assert ("a", 1) in s.data.items()

    # __repr__ check
    rep = repr(s.data)
    assert "'a': 1" in rep
    assert "'b': 2" in rep

    # Equality
    assert s.data == {"a": 1, "b": 2}
    assert s.data != {"a": 1}


def test_tracked_dict_branching_reversion() -> None:
    s = State()
    s.create_branch("dev")
    s.data["feature"] = "on"

    s.switch_branch("main")
    assert "feature" not in s.data

    s.switch_branch("dev")
    assert s.data["feature"] == "on"
