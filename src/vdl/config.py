from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VdlConfig:
    output_dir: str = str(Path.home() / "Downloads")
    default_format: str | None = None
    default_quality: str = "best"
    embed_thumbnail: bool = True
    sponsorblock: bool = False
    subs: bool = False
    subs_lang: str = "fr"
    output_template: str = "%(title)s.%(ext)s"
    retries: int = 3
    # Unused field kept for forward compatibility
    _extra: dict[str, object] = field(default_factory=dict, repr=False)


_CONFIG_PATH = Path.home() / ".config" / "vdl" / "config.toml"


def load_config(path: Path = _CONFIG_PATH) -> VdlConfig:
    if not path.exists():
        return VdlConfig()

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            return VdlConfig()

    with path.open("rb") as f:
        raw = tomllib.load(f)

    cfg = VdlConfig()
    _apply(cfg, raw)
    return cfg


def _apply(cfg: VdlConfig, raw: dict[str, object]) -> None:
    for key, value in raw.items():
        if key == "output_dir":
            cfg.output_dir = str(value)
        elif key == "default_format":
            cfg.default_format = str(value) if value else None
        elif key == "default_quality":
            cfg.default_quality = str(value)
        elif key == "embed_thumbnail":
            cfg.embed_thumbnail = bool(value)
        elif key == "sponsorblock":
            cfg.sponsorblock = bool(value)
        elif key == "subs":
            cfg.subs = bool(value)
        elif key == "subs_lang":
            cfg.subs_lang = str(value)
        elif key == "output_template":
            cfg.output_template = str(value)
        elif key == "retries":
            cfg.retries = int(str(value))
