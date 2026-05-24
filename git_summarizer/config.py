import tomllib
from pathlib import Path
from typing import Any

CONFIG_PATH = Path.home() / ".config" / "git-summarizer" / "config.toml"

VALID_KEYS: dict[str, type] = {
    "author":  str,
    "days":    int,
    "weeks":   int,
    "repo":    str,
    "base":    str,
    "no_ai":   bool,
    "model":   str,
}


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def save_config(cfg: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for key, value in sorted(cfg.items()):
        if isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        elif isinstance(value, int):
            lines.append(f"{key} = {value}")
        else:
            escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
    CONFIG_PATH.write_text("\n".join(lines) + "\n" if lines else "")


def set_key(key: str, raw_value: str) -> None:
    if key not in VALID_KEYS:
        raise ValueError(
            f"Unknown key {key!r}. Valid keys: {', '.join(VALID_KEYS)}"
        )
    target = VALID_KEYS[key]
    cfg = load_config()
    if target is bool:
        if raw_value.lower() in ("true", "1", "yes"):
            cfg[key] = True
        elif raw_value.lower() in ("false", "0", "no"):
            cfg[key] = False
        else:
            raise ValueError(f"{key} must be true/false")
    elif target is int:
        try:
            cfg[key] = int(raw_value)
        except ValueError:
            raise ValueError(f"{key} must be an integer")
    else:
        cfg[key] = raw_value
    save_config(cfg)


def unset_key(key: str) -> None:
    cfg = load_config()
    cfg.pop(key, None)
    save_config(cfg)


def build_default_map(cfg: dict[str, Any]) -> dict[str, dict]:
    """Return a Click default_map populated from config file values."""
    shared: dict[str, Any] = {}
    if "repo"   in cfg: shared["repo"]   = cfg["repo"]
    if "author" in cfg: shared["author"] = cfg["author"]
    if "no_ai"  in cfg: shared["no_ai"]  = cfg["no_ai"]

    return {
        "changelog": {**shared},
        "standup":   {**shared, **({"days":  cfg["days"]}  if "days"  in cfg else {})},
        "digest":    {**shared, **({"weeks": cfg["weeks"]} if "weeks" in cfg else {})},
        "pr":        {**shared, **({"base":  cfg["base"]}  if "base"  in cfg else {})},
    }
