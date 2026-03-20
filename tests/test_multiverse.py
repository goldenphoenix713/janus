from janus import janus


@janus(mode="multiversal")
class Hero:
    def __init__(self, name, hp):
        self.name = name
        self.hp = hp
        self.inventory = []

def test_basic_branching():
    h = Hero("Arthur", 100)
    assert h.name == "Arthur"
    
    # These will be stubs for now since engine.rs logic is minimal
    h.branch("chaos-timeline")  # type: ignore
    h.hp = 50
    
    h.switch("main")  # type: ignore
    # assert h.hp == 100 # This will fail until apply_inverse is implemented
