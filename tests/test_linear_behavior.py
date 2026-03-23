import pytest

from janus import TimelineBase


class Document(TimelineBase):
    def __init__(self):
        super().__init__()
        self.text = ""


def test_linear_pruning_on_mutation():
    doc = Document()

    # Sequence of states: "" -> "A" -> "AB"
    doc.text = "A"
    doc.text = "AB"
    assert doc.text == "AB"

    # Undo back to "A"
    doc.undo()
    assert doc.text == "A"

    # Mutate to "AC". This should PRUNE the future ("AB")
    doc.text = "AC"
    assert doc.text == "AC"

    # Verify that redo() does nothing (future "AB" is gone)
    doc.redo()
    assert doc.text == "AC"

    # Undo once should take us back to "A"
    doc.undo()
    assert doc.text == "A"

    # Undo again should take us back to ""
    doc.undo()
    assert doc.text == ""


def test_label_pruning_in_linear_mode():
    doc = Document()

    doc.text = "State 1"
    doc.text = "State 2"
    doc.create_moment_label("future-label")  # Label on State 2

    assert "future-label" in doc.get_labeled_moments()

    # Undo back to State 1
    doc.undo()

    # Overwrite by mutating
    doc.text = "State 3"

    # The label "future-label" (which was on the discarded State 2) should be gone
    labels = doc.get_labeled_moments()
    assert "future-label" not in labels
    assert len(labels) == 1  # Only "__genesis__"


def test_multiple_undo_pruning():
    doc = Document()
    doc.text = "1"
    doc.text = "2"
    doc.text = "3"
    doc.text = "4"

    # Undo 3 times back to "1"
    doc.undo()
    doc.undo()
    doc.undo()
    assert doc.text == "1"

    # Mutate to "1-New"
    doc.text = "1-New"

    # Verify we can't redo back to "2", "3", or "4"
    doc.redo()
    assert doc.text == "1-New"

    # Verify timeline is now: "" -> "1" -> "1-New"
    doc.undo()
    assert doc.text == "1"
    doc.undo()
    assert doc.text == ""


if __name__ == "__main__":
    pytest.main([__file__])
