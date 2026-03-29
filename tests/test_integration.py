from pathlib import Path

import pandas as pd

from janus import MultiverseBase


class ResearchLab(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.data = pd.DataFrame({"A": [1.0, 2.0, 3.0], "B": [4.0, 5.0, 6.0]})
        self.params = {"learning_rate": 0.01, "layers": [64, 32]}


def test_scientific_workflow_e2e(tmp_path: Path) -> None:
    save_path = tmp_path / "research_session.jns"
    lab = ResearchLab()

    # 1. Start baseline
    lab.label_node("baseline")

    # 2. Branch A: Optimizing learning rate
    lab.branch("opt_lr")
    lab.params["learning_rate"] = 0.005
    # Pandas mutation via tracked adapter
    lab.data["A"] = lab.data["A"] * 2
    lab.label_node("lr_done")

    # 3. Branch B: Changing architecture (from baseline)
    lab.jump_to("baseline")
    lab.branch("new_arch")
    lab.params["layers"] = [128, 64, 32]
    lab.data["B"] = lab.data["B"] + 10
    lab.label_node("arch_done")

    # 4. Merge Branch A into Branch B (current)
    # This should merge the 'A' column changes from Branch A into current Branch B
    lab.merge("opt_lr")

    # Verify merged state
    assert lab.params["learning_rate"] == 0.005
    assert lab.params["layers"] == [128, 64, 32]
    # Check pandas data integrity after merge
    pd.testing.assert_series_equal(
        lab.data["A"], pd.Series([2.0, 4.0, 6.0], name="A"), check_series_type=False
    )
    pd.testing.assert_series_equal(
        lab.data["B"], pd.Series([14.0, 15.0, 16.0], name="B"), check_series_type=False
    )

    # 5. Persist the entire merged lab
    lab.save(save_path)
    assert save_path.exists()

    # 6. Re-hydrate in a fresh object
    new_lab = ResearchLab()
    new_lab.load(save_path)

    # Verify loaded state matches merged state
    assert new_lab.params["learning_rate"] == 0.005
    pd.testing.assert_series_equal(
        new_lab.data["A"], lab.data["A"], check_series_type=False
    )

    # 7. Verify history is alive and navigatable in re-hydrated object
    new_lab.jump_to("baseline")
    assert new_lab.params["learning_rate"] == 0.01
    pd.testing.assert_series_equal(
        new_lab.data["A"], pd.Series([1.0, 2.0, 3.0], name="A"), check_series_type=False
    )

    new_lab.jump_to("lr_done")
    assert new_lab.params["learning_rate"] == 0.005
    pd.testing.assert_series_equal(
        new_lab.data["A"], pd.Series([2.0, 4.0, 6.0], name="A"), check_series_type=False
    )
    # In lr_done, B should still be its original values
    pd.testing.assert_series_equal(
        new_lab.data["B"], pd.Series([4.0, 5.0, 6.0], name="B"), check_series_type=False
    )
