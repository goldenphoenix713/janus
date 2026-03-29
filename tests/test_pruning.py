from janus import MultiverseBase, TimelineBase


def test_linear_pruning() -> None:
    class State(TimelineBase):
        def __init__(self, max_history: int = 10) -> None:
            super().__init__(max_history=max_history)
            self.x = 0

    obj = State(max_history=10)

    # Mutate 100 times
    for i in range(1, 101):
        obj.x = i

    # Check current state
    assert obj.x == 100

    # Check graph size
    # Max history is 10. We expect around 10 nodes + genesis (if protected)
    graph = obj._engine.get_graph_data()
    # Pruning removes oldest unlabeled nodes.
    # In linear mode, there are no labels except genesis.
    # Current node is always protected.
    assert len(graph) <= 15  # Some buffer for genesis etc.


def test_multiversal_pruning_protection() -> None:
    class State(MultiverseBase):
        def __init__(self, max_history: int = 10) -> None:
            super().__init__(max_history=max_history)
            self.x = 0

    obj = State(max_history=10)

    # Mutate a bit
    for i in range(1, 6):
        obj.x = i

    # Label a moment (this node should be protected)
    obj.label_node("five")
    protected_node_id = obj._engine.get_node_id("five")

    # Mutate many more times
    for i in range(6, 101):
        obj.x = i

    # Check that the protected node still exists
    graph = obj._engine.get_graph_data()
    node_ids = [n["id"] for n in graph]
    assert protected_node_id in node_ids

    # Check that we can still jump to it
    obj.jump_to("five")
    assert obj.x == 5


def test_branch_protection() -> None:
    class State(MultiverseBase):
        def __init__(self, max_history: int = 5) -> None:
            super().__init__(max_history=max_history)
            self.x = 0

    obj = State(max_history=5)
    obj.x = 1
    obj.branch("side")  # Side branch at x=1

    obj.switch_branch("main")
    for i in range(2, 20):
        obj.x = i

    # Check side branch still exists
    assert "side" in obj.list_branches()
    obj.switch_branch("side")
    assert obj.x == 1

    # Check graph size isn't exploding
    graph = obj._engine.get_graph_data()
    assert len(graph) <= 15
