import pytest

from janus import timeline


@timeline
class Player:
    def __init__(self, name, hp):
        self.name = name
        self.hp = hp


def test_basic_reversion():
    p = Player("Alice", 100)

    # Normal state
    assert p.hp == 100

    # Create a branch at the initial state
    p.create_moment_label("start")  # type: ignore

    # Modify state
    p.hp = 80
    p.create_moment_label("damaged")  # type: ignore

    # Modify again
    p.hp = 50

    # Revert to start
    p.jump_to("start")  # type: ignore
    assert p.hp == 100

    # Switch to damaged
    p.jump_to("damaged")  # type: ignore
    assert p.hp == 80


if __name__ == "__main__":
    pytest.main([__file__])
