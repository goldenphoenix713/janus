from janus import JanusAdapter, MultiverseBase, register_adapter


class Data:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"Data({self.value})"


@register_adapter(Data)
class CustomDataAdapter(JanusAdapter):
    def get_delta(self, old_state, new_state):
        # old_state is now the SNAPSHOT (a string)
        # new_state is the live Data instance
        old_val = old_state
        new_val = new_state.value
        return (old_val, new_val)

    def apply_inverse(self, target, delta_blob):
        old_val, _ = delta_blob
        target.value = old_val

    def apply_forward(self, target, delta_blob):
        _, new_val = delta_blob
        target.value = new_val

    def get_snapshot(self, value):
        # For this mock, the snapshot is simply the value string
        return value.value


class Database(MultiverseBase):
    def __init__(self):
        super().__init__()
        self.record = None


def test_plugin_registration():
    db = Database()
    db.record = Data("initial")
    db.record = Data("updated")

    # Verify timeline contains the PluginOp
    timeline = db.extract_timeline("main")  # type: ignore
    plugin_ops = [op for op in timeline if op["type"] == "PluginOp"]
    assert len(plugin_ops) > 0
    assert plugin_ops[-1]["adapter"] == "CustomDataAdapter"
    # Note: now it captures ("initial", "updated") because the shadow was
    # "initial" when "updated" was assigned.


def test_plugin_state_restoration_inplace():
    """Verify that IN-PLACE mutations are correctly restored via Shadow Snapshots."""
    db = Database()
    record = Data("initial")
    db.record = record

    # Create a branch and perform an in-place mutation
    db.branch("feature-x")
    record.value = "mutated-in-place"

    # Trigger Janus tracking (same reference!)
    # The Shadow Snapshot in JanusBase will correctly see the delta from 'initial'
    db.record = record

    assert db.record.value == "mutated-in-place"

    # Jump back to main - should restore the original value via apply_inverse
    db.jump_to("main")
    assert db.record.value == "initial"

    # Jump forward back to feature-x - should apply the forward delta
    db.jump_to("feature-x")
    assert db.record.value == "mutated-in-place"
