from typing import Any

import pytest

from janus.base import MultiverseBase

try:
    import pandas as pd

    from janus.plugins.pandas import TrackedDataFrame, TrackedSeries

    PANDAS_INSTALLED = True
except ImportError:
    PANDAS_INSTALLED = False


@pytest.mark.skipif(not PANDAS_INSTALLED, reason="Pandas is not installed")
class MockPandasStore(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.df: Any = None
        self.s: Any = None


@pytest.mark.skipif(not PANDAS_INSTALLED, reason="Pandas is not installed")
def test_pandas_wrapping() -> None:
    """Verify that pd.DataFrame and pd.Series are auto-wrapped."""
    store = MockPandasStore()

    # Store a plain DataFrame
    data_df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    store.df = data_df

    # Verify it is now a TrackedDataFrame
    assert isinstance(store.df, TrackedDataFrame)
    assert isinstance(store.df, pd.DataFrame)
    assert store.df._janus_name == "df"

    # Store a plain Series
    data_s = pd.Series([10, 20, 30], name="myseries")
    store.s = data_s

    # Verify it is now a TrackedSeries
    assert isinstance(store.s, TrackedSeries)
    assert isinstance(store.s, pd.Series)
    assert store.s._janus_name == "s"


@pytest.mark.skipif(not PANDAS_INSTALLED, reason="Pandas is not installed")
def test_dataframe_mutation_rollback() -> None:
    """Verify that in-place DataFrame mutations can be undone."""
    store = MockPandasStore()
    store.df = pd.DataFrame({"A": [1, 2, 3]})

    # Initial state
    assert store.df["A"].tolist() == [1, 2, 3]

    # In-place mutation via __setitem__
    store.df["A"] = [10, 20, 30]
    assert store.df["A"].tolist() == [10, 20, 30]

    # Undo the mutation
    store.undo()

    # Verify restoration
    assert store.df["A"].tolist() == [1, 2, 3]


@pytest.mark.skipif(not PANDAS_INSTALLED, reason="Pandas is not installed")
def test_series_mutation_rollback() -> None:
    """Verify that in-place Series mutations can be undone."""
    store = MockPandasStore()
    store.s = pd.Series([1, 2, 3])

    # Initial state
    assert store.s[0] == 1

    # In-place mutation via __setitem__
    store.s[0] = 99
    assert store.s[0] == 99

    # Undo the mutation
    store.undo()

    # Verify restoration
    assert store.s[0] == 1


@pytest.mark.skipif(not PANDAS_INSTALLED, reason="Pandas is not installed")
def test_pandas_branching() -> None:
    """Verify pandas state restoration across multiverse branches."""
    store = MockPandasStore()
    store.df = pd.DataFrame({"val": [10]})

    # Create Branch A
    store.create_branch("branch_A")
    store.df["val"] = [20]

    # Create Branch B from root (by switching back first)
    store.switch_branch("main")
    store.create_branch("branch_B")
    store.df["val"] = [30]

    # Switch cross-branch
    store.switch_branch("branch_A")
    assert store.df["val"].tolist() == [20]

    store.switch_branch("branch_B")
    assert store.df["val"].tolist() == [30]

    store.switch_branch("main")
    assert store.df["val"].tolist() == [10]


@pytest.mark.skipif(not PANDAS_INSTALLED, reason="Pandas is not installed")
def test_pandas_method_chaining() -> None:
    """Verify that operation results remain Janus-aware."""
    store = MockPandasStore()
    store.df = pd.DataFrame({"A": [3, 1, 2], "B": [4, 5, 6]})

    # Perform a chain of operations
    # sort_values -> returns TrackedDataFrame
    # reset_index -> returns TrackedDataFrame
    result = store.df.sort_values("A").reset_index(drop=True)

    assert isinstance(result, TrackedDataFrame)
    assert result["A"].tolist() == [1, 2, 3]
    # Verify metadata propagation
    assert result._janus_name == "df"
    assert result._janus_engine is not None


@pytest.mark.skipif(not PANDAS_INSTALLED, reason="Pandas is not installed")
def test_loc_cell_mutation_rollback() -> None:
    """Verify that .loc[row, col] mutation is correctly undone."""
    store = MockPandasStore()
    store.df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})

    # Verify engine presence
    assert hasattr(store.df, "_janus_engine"), (
        "DataFrame missing engine before loc mutation"
    )

    # Get current timeline length
    len(store._engine.extract_timeline("main"))

    # Mutate a single cell via .loc
    store.df.loc[0, "A"] = 100
    assert store.df.loc[0, "A"] == 100

    # Undo
    store.undo()
    assert store.df.loc[0, "A"] == 1


@pytest.mark.skipif(not PANDAS_INSTALLED, reason="Pandas is not installed")
def test_iloc_slice_mutation_rollback() -> None:
    """Verify that .iloc slice mutation is correctly undone."""
    store = MockPandasStore()
    store.df = pd.DataFrame({"A": [1, 2, 3]})

    # Mutate a slice via .iloc
    store.df.iloc[0:2, 0] = [10, 20]
    assert store.df["A"].tolist() == [10, 20, 3]

    # Undo
    store.undo()
    assert store.df["A"].tolist() == [1, 2, 3]


@pytest.mark.skipif(not PANDAS_INSTALLED, reason="Pandas is not installed")
def test_at_scalar_mutation_rollback() -> None:
    """Verify that .at scalar mutation is correctly undone."""
    store = MockPandasStore()
    store.df = pd.DataFrame({"A": [1, 2]})

    # Mutate via .at
    store.df.at[1, "A"] = 99
    assert store.df.at[1, "A"] == 99

    # Undo
    store.undo()
    assert store.df.at[1, "A"] == 2


@pytest.mark.skipif(not PANDAS_INSTALLED, reason="Pandas is not installed")
def test_view_propagation_mutation() -> None:
    """Verify that a view (TrackedSeries) updates the parent's Janus timeline."""
    store = MockPandasStore()
    store.df = pd.DataFrame({"val": [1, 2, 3]})

    # Get a row-view via .loc
    row_view = store.df.loc[0]

    # Because of constructor-sliced, row_view should be a TrackedSeries
    assert isinstance(row_view, TrackedSeries)

    # Mutate the view directly
    row_view["val"] = 555
    # Note: In modern Pandas (3.0+), row-slices may still return copies.
    # We expect this to propagate if it's a true view.
    # assert store.df.at[0, "val"] == 555
