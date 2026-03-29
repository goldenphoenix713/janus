from typing import Any

import pytest

from janus import options
from janus.base import JanusBase, MultiverseBase
from janus.viz import register_backend


class Simulation(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.x = 0


class MockBackend:
    def plot(self, obj: JanusBase, **kwargs: Any) -> str:
        return f"Mock plot for {type(obj).__name__} with {kwargs}"


def test_viz_registry_custom_backend() -> None:
    sim = Simulation()
    register_backend("mock", MockBackend())

    result = sim.plot(backend="mock", title="Test Graph")
    assert "Mock plot for Simulation" in result
    assert "'title': 'Test Graph'" in result


def test_viz_default_backend_options() -> None:
    sim = Simulation()
    register_backend("mock", MockBackend())

    # Change global default
    original = options.plotting.backend
    try:
        options.plotting.backend = "mock"
        result = sim.plot()
        assert "Mock plot for Simulation" in result
    finally:
        options.plotting.backend = original


def test_viz_mermaid_shortcut() -> None:
    sim = Simulation()
    sim.x = 1

    # visualize() should still return mermaid string
    result = sim.visualize()
    assert "graph LR" in result
    assert "node0" in result


def test_viz_invalid_backend() -> None:
    sim = Simulation()
    with pytest.raises(ValueError, match="Unknown visualization backend"):
        sim.plot(backend="sketchy")


if __name__ == "__main__":
    pytest.main([__file__])
