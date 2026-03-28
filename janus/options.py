from dataclasses import dataclass, field


@dataclass
class PlottingOptions:
    backend: str = "mermaid"


@dataclass
class Options:
    plotting: PlottingOptions = field(default_factory=PlottingOptions)


options = Options()
