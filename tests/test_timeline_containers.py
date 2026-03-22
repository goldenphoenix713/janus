import pytest

from janus import multiverse


@multiverse
class Inventory:
    def __init__(self):
        self.items = []


def test_timeline_extraction():
    inv = Inventory()
    inv.create_moment_label("empty")  # type: ignore

    inv.items.append("Sword")
    inv.create_moment_label("armed")  # type: ignore

    inv.items.append("Shield")

    # Extract timeline from "armed" branch
    timeline = inv.extract_timeline("armed")  # type: ignore

    # Should contain:
    # 1. Initial items=[] (UpdateAttr)
    # 2. Append "Sword" (ListInsert)
    assert len(timeline) >= 2
    assert timeline[-1]["type"] == "ListInsert"
    assert timeline[-1]["value"] == "Sword"


def test_list_reversion():
    inv = Inventory()
    inv.create_moment_label("base")  # type: ignore

    inv.items.append("Potion")
    assert len(inv.items) == 1

    inv.jump_to("base")  # type: ignore
    assert len(inv.items) == 0


@multiverse
class Config:
    def __init__(self):
        self.settings = {}


def test_dict_reversion():
    c = Config()
    c.create_moment_label("empty")  # type: ignore

    c.settings["theme"] = "dark"
    c.create_moment_label("themed")  # type: ignore

    c.settings["font"] = "Inter"
    assert c.settings["theme"] == "dark"
    assert c.settings["font"] == "Inter"

    # Revert to empty
    c.jump_to("empty")  # type: ignore
    assert len(c.settings) == 0

    # Revert to themed
    c.jump_to("themed")  # type: ignore
    assert c.settings["theme"] == "dark"
    assert "font" not in c.settings


if __name__ == "__main__":
    pytest.main([__file__])
