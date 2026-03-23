from janus import JanusAdapter, MultiverseBase, register_adapter


class Data:
    def __init__(self, value):
        self.value = value


class DataAdapter(JanusAdapter):
    def get_delta(self, old_state, new_state):
        return f"diff:{getattr(old_state, 'value', None)}->{new_state.value}"

    def apply_inverse(self, target, delta_blob):
        pass


@register_adapter(Data)
class CustomDataAdapter(DataAdapter):
    pass


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
