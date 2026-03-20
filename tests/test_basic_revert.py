import pytest

from janus import janus


@janus(mode="multiversal")
class Player:
    def __init__(self, name, hp):
        self.name = name
        self.hp = hp


def test_basic_reversion():
    p = Player("Alice", 100)

    # Normal state
    assert p.hp == 100

    # Create a branch at the initial state
    p.branch("start")  # type: ignore

    # Modify state
    p.hp = 80
    p.branch("damaged")  # type: ignore

    # Modify again
    p.hp = 50

    # Revert to start
    p.switch("start")  # type: ignore
    assert p.hp == 100

    # Switch to damaged
    p.switch("damaged")  # type: ignore
    assert p.hp == 80


if __name__ == "__main__":
    pytest.main([__file__])
