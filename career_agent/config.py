from __future__ import annotations

import os
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


ProviderProtocol = Literal["openai_compatible", "anthropic"]


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    name: str
    protocol: ProviderProtocol
    model: str
    api_key_env: str
    base_url: str | None = None
    timeout_seconds: float = 60.0
    max_retries: int = 2

    def __post_init__(self) -> None:
        if self.protocol not in ("openai_compatible", "anthropic"):
            raise ValueError(f"unsupported provider protocol: {self.protocol}")
        if not self.name.strip() or not self.model.strip() or not self.api_key_env.strip():
            raise ValueError("provider name, model and api_key_env are required")

    def resolve_api_key(self) -> str:
        value = os.environ.get(self.api_key_env, "").strip()
        if not value:
            try:
                import keyring

                value = (keyring.get_password("jobtrace", self.name) or "").strip()
            except (ImportError, RuntimeError):
                value = ""
        if not value:
            raise RuntimeError(f"missing API key: set {self.api_key_env} or store it in the OS keyring")
        return value

    def as_public_dict(self) -> dict[str, object]:
        return asdict(self)


def load_provider_profiles(path: str | Path) -> dict[str, ProviderProfile]:
    config_path = Path(path).expanduser()
    if not config_path.exists():
        return {}
    with config_path.open("rb") as handle:
        payload = tomllib.load(handle)
    profiles: dict[str, ProviderProfile] = {}
    for name, raw in (payload.get("providers") or {}).items():
        profiles[name] = ProviderProfile(name=name, **raw)
    return profiles
