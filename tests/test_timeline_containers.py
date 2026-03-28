from typing import Any

import pytest

from janus import MultiverseBase


class Inventory(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[Any] = []


def test_timeline_extraction() -> None:
    inv = Inventory()
    inv.create_moment_label("empty")

    inv.items.append("Sword")
    inv.create_moment_label("armed")

    inv.items.append("Shield")

    # Extract timeline from "armed" branch
    timeline = inv.extract_timeline("armed")

    # Should contain:
    # 1. Initial items=[] (UpdateAttr)
    # 2. Append "Sword" (ListInsert)
    assert len(timeline) >= 2
    assert timeline[-1]["type"] == "ListInsert"
    assert timeline[-1]["value"] == "Sword"


def test_list_reversion() -> None:
    inv = Inventory()
    inv.create_moment_label("base")

    inv.items.append("Potion")
    assert len(inv.items) == 1

    inv.jump_to("base")
    assert len(inv.items) == 0


class Config(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.settings: dict[str, Any] = {}


def test_dict_reversion() -> None:
    c = Config()
    c.create_moment_label("empty")

    c.settings["theme"] = "dark"
    c.create_moment_label("themed")

    c.settings["font"] = "Inter"
    assert c.settings["theme"] == "dark"
    assert c.settings["font"] == "Inter"

    # Revert to empty
    c.jump_to("empty")
    assert len(c.settings) == 0

    # Revert to themed
    c.jump_to("themed")
    assert c.settings["theme"] == "dark"
    assert "font" not in c.settings


if __name__ == "__main__":
    pytest.main([__file__])
