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
    _extra: dict[str, object] = field(default_factory=dict, repr=False)


_CONFIG_PATH = Path.home() / ".config" / "vdl" / "config.toml"

_CONVERTERS: dict[str, object] = {
    "output_dir": str,
    "default_format": lambda v: str(v) if v else None,
    "default_quality": str,
    "embed_thumbnail": bool,
    "sponsorblock": bool,
    "subs": bool,
    "subs_lang": str,
    "output_template": str,
    "retries": lambda v: int(str(v)),
}


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

    try:
        with path.open("rb") as f:
            raw = tomllib.load(f)
    except Exception:
        print(f"Warning: invalid config file {path}, using defaults.", file=sys.stderr)
        return VdlConfig()

    cfg = VdlConfig()
    for key, value in raw.items():
        converter = _CONVERTERS.get(key)
        if converter:
            setattr(cfg, key, converter(value))  # type: ignore[operator]
    return cfg
