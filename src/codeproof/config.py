"""Validated scan policies, with partial files layered over safe defaults."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

TOOL_INFO = {
    "imports": ("Import smoke", "Executes each source module in a subprocess", None),
    "ruff": ("Lint", "Fast Python lint checks", "checkers"),
    "mypy": ("Types", "Static type analysis", "checkers"),
    "pytest": ("Tests", "Executes the repository test suite", "checkers"),
    "bandit": ("Security", "Python security analysis", "checkers"),
    "semgrep": (
        "Patterns",
        "Security rules (auto rules may use the network)",
        "checkers",
    ),
    "syntax": (
        "Syntax",
        "Compiles source without executing it or writing bytecode",
        None,
    ),
    "pip-audit": (
        "Dependencies",
        "Audits requirements.txt against vulnerability services",
        "audit",
    ),
}


class CheckConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    weight: float = Field(default=1, ge=0, allow_inf_nan=False)
    config: str | None = None


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    fail_under: float = Field(default=70, ge=0, le=100, allow_inf_nan=False)
    source_paths: list[str] = Field(default_factory=lambda: ["src"])
    test_paths: list[str] = Field(default_factory=lambda: ["tests"])
    timeout_seconds: int = Field(default=300, ge=1)
    jobs: int = Field(default=1, ge=1, le=8)
    required_tools: list[str] = Field(default_factory=lambda: ["ruff", "pytest"])
    checks: dict[str, CheckConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_policy(self):
        unknown = (set(self.checks) | set(self.required_tools)) - TOOL_INFO.keys()
        if unknown:
            raise ValueError("Unknown tools: " + ", ".join(sorted(unknown)))
        if not self.source_paths or not self.test_paths:
            raise ValueError("source_paths and test_paths must not be empty")
        if any(not path.strip() for path in self.source_paths + self.test_paths):
            raise ValueError("Source and test paths must not be blank")
        return self


DEFAULT = Config(
    checks={
        "imports": CheckConfig(weight=10),
        "ruff": CheckConfig(weight=15),
        "mypy": CheckConfig(weight=15),
        "pytest": CheckConfig(weight=30),
        "bandit": CheckConfig(weight=15),
        "semgrep": CheckConfig(weight=15, config="auto"),
    }
)


def load(root: Path, explicit: Path | None = None) -> Config:
    path = explicit if explicit is not None else root / ".codeproof.yml"
    if not path.exists():
        if explicit is not None:
            raise ValueError(f"Policy file not found: {path}")
        return DEFAULT.model_copy(deep=True)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise TypeError("Policy must be a YAML mapping")
    defaults = DEFAULT.model_dump()
    overrides = data.get("checks", {})
    if not isinstance(overrides, dict):
        raise TypeError("checks must be a YAML mapping")
    checks = defaults["checks"]
    for name, settings in overrides.items():
        if not isinstance(settings, dict):
            raise TypeError(f"Check {name} must be a YAML mapping")
        checks[name] = {**checks.get(name, {}), **settings}
    return Config.model_validate({**defaults, **data, "checks": checks})
