from dataclasses import asdict, dataclass, field


@dataclass
class ToolResult:
    ok: bool
    summary: str
    changed_paths: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    reversible: bool = False

    def as_dict(self):
        return asdict(self)
