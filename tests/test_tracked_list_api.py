from janus import TimelineBase


class Hero(TimelineBase):
    def __init__(self, name, hp):
        super().__init__()
        self.name = name
        self.hp = hp
        self.items = []


def test_list_insert():
    h = Hero("Arthur", 100)
    h.items.append("Sword")
    h.items.insert(0, "Shield")
    assert h.items == ["Shield", "Sword"]

    h.undo()
    assert h.items == ["Sword"]

    h.redo()
    assert h.items == ["Shield", "Sword"]


def test_list_remove():
    h = Hero("Arthur", 100)
    h.items.extend(["Sword", "Shield", "Potion"])
    assert h.items == ["Sword", "Shield", "Potion"]

    h.items.remove("Shield")
    assert h.items == ["Sword", "Potion"]

    h.undo()
    assert h.items == ["Sword", "Shield", "Potion"]


def test_list_clear():
    h = Hero("Arthur", 100)
    h.items.extend(["Sword", "Shield"])
    h.items.clear()
    assert len(h.items) == 0

    h.undo()
    assert h.items == ["Sword", "Shield"]


def test_list_setitem_atomic():
    h = Hero("Arthur", 100)
    h.items.append("Sword")
    h.items[0] = "Excalibur"
    assert h.items[0] == "Excalibur"

    # This should revert to "Sword" in ONE undo
    h.undo()
    assert h.items[0] == "Sword"

    h.redo()
    assert h.items[0] == "Excalibur"


def test_list_delitem():
    h = Hero("Arthur", 100)
    h.items.extend(["Sword", "Shield"])
    del h.items[0]
    assert h.items == ["Shield"]

    h.undo()
    assert h.items == ["Sword", "Shield"]


def test_list_utilities():
    h = Hero("Arthur", 100)
    h.items.extend(["Sword", "Shield"])

    # __repr__
    assert repr(h.items) == "['Sword', 'Shield']"

    # __contains__
    assert "Sword" in h.items
    assert "Axe" not in h.items

    # __eq__
    assert h.items == ["Sword", "Shield"]
    assert h.items != ["Sword"]

    # __iter__
    items = [item for item in h.items]
    assert items == ["Sword", "Shield"]
