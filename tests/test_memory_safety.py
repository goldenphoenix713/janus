import gc
import weakref

import pytest

from janus import MultiverseBase


class Simulation(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.x = 0


def test_circular_reference_breakage() -> None:
    # Create an object
    sim = Simulation()
    engine = sim._engine

    # Create a weakref to the object
    sim_weak = weakref.ref(sim)

    # Delete the strong reference to the object
    # If the engine held a strong ref, sim would not be collected.
    del sim
    gc.collect()

    # Verify the object was collected
    assert sim_weak() is None

    # Verify the engine still exists (if we have a reference to it)
    # but accessing the owner raises ReferenceError
    with pytest.raises(ReferenceError, match="Janus object has been garbage collected"):
        _ = engine.owner


def test_tombstone_on_mutation_attempt() -> None:
    sim = Simulation()
    engine = sim._engine

    # We shouldn't be able to mutate if the owner is gone,
    # but wait! The engine's public methods like log_update_attr
    # don't currently catch the tombstone because they don't 'upgrade_owner'.
    # This is fine as long as we can't 'move' or 'undo'.

    del sim
    gc.collect()

    with pytest.raises(ReferenceError, match="Tombstone state"):
        engine.move_to(
            "main"
        )  # move_to_label calls move_to_node_id which upgrades owner


def test_tombstone_on_undo() -> None:
    sim = Simulation()
    sim.x = 10
    engine = sim._engine

    del sim
    gc.collect()

    # undo() would need to call move_to_node_id
    # We can't call it directly on MultiverseBase (it's gone),
    # but if we held a ref to the engine and called move:
    with pytest.raises(ReferenceError, match="Tombstone state"):
        engine.undo()


if __name__ == "__main__":
    pytest.main([__file__])
