from typing import Any

import pytest

from janus import MultiverseBase


class SimpleModel(MultiverseBase):
    def __init__(self, value: int = 0) -> None:
        super().__init__()
        self.value = value
        self.data: dict[str, Any] = {"a": 1}


def test_overshadow_strategy() -> None:
    m = SimpleModel(10)
    m.branch("feature")

    m.jump_to("feature")
    m.value = 20
    m.data["b"] = 2

    m.jump_to("main")
    m.value = 15
    m.merge("feature", strategy="overshadow")

    assert m.value == 20
    assert m.data["b"] == 2
    assert m.data["a"] == 1


def test_preserve_strategy() -> None:
    m = SimpleModel(10)
    m.branch("feature")

    m.jump_to("feature")
    m.value = 20

    m.jump_to("main")
    m.value = 15
    m.merge("feature", strategy="preserve")

    assert m.value == 15


def test_strict_strategy() -> None:
    m = SimpleModel(10)
    m.branch("feature")

    m.jump_to("feature")
    m.value = 20

    m.jump_to("main")
    m.value = 15
    with pytest.raises(ValueError, match="Merge conflict on attribute 'value'"):
        m.merge("feature", strategy="strict")


def test_custom_callback_attribute() -> None:
    m = SimpleModel(10)
    m.branch("feature")

    m.jump_to("feature")
    m.value = 20

    m.jump_to("main")
    m.value = 15

    def my_strategy(name: str, base: Any, source: Any, target: Any) -> Any:
        if name == "value":
            return (source + target) / 2
        return source

    m.merge("feature", strategy=my_strategy)
    assert m.value == 17.5


def test_custom_callback_dict_keys() -> None:
    m = SimpleModel(10)
    m.data = {"conflict": 100, "only_main": 50}

    m.branch("feature")

    m.jump_to("feature")
    m.data["conflict"] = 200
    m.data["only_feature"] = 300

    m.jump_to("main")
    m.data["conflict"] = 150

    def dict_strategy(name: Any, base: Any, source: Any, target: Any) -> Any:
        # When called for attribute 'data' during transformation/rebase
        if name == "data" and isinstance(source, dict):
            # We let the key-level conflicts handle it by returning base or source?
            # Actually, return source to allow transformation to proceed
            return source

        # When called for key-level conflict
        if isinstance(name, str) and ("conflict" in name or "conflict" in str(source)):
            return source + target  # 150 + 200 = 350
        return source

    m.merge("feature", strategy=dict_strategy)

    assert m.data["conflict"] == 350
    assert m.data["only_main"] == 50
    assert m.data["only_feature"] == 300
