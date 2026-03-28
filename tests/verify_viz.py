from janus import MultiverseBase


class Simulation(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.x = 0


def test_viz() -> None:
    sim = Simulation()

    # 1. Create some history
    sim.x = 1
    sim.label_node("v1")

    # 2. Branching
    sim.branch("dev")
    sim.x = 10
    sim.x = 20

    sim.jump_to("main")
    sim.x = 2

    # 3. Merge
    sim.merge("dev")

    # 4. Generate Mermaid
    mermaid = sim.visualize()
    print("--- MERMAID START ---")
    print(mermaid)
    print("--- MERMAID END ---")


if __name__ == "__main__":
    test_viz()
