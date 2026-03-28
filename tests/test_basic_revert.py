import pytest

from janus import TimelineBase


class Player(TimelineBase):
    def __init__(self, name: str, hp: int) -> None:
        super().__init__()
        self.name = name
        self.hp = hp


def test_basic_reversion() -> None:
    p = Player("Alice", 100)

    # Normal state
    assert p.hp == 100

    # Create a branch at the initial state
    p.create_moment_label("start")

    # Modify state
    p.hp = 80
    p.create_moment_label("damaged")

    # Modify again
    p.hp = 50

    # Revert to start
    p.jump_to("start")
    assert p.hp == 100

    # Switch to damaged
    p.jump_to("damaged")
    assert p.hp == 80


if __name__ == "__main__":
    pytest.main([__file__])
