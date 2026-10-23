"""
config_utils.py -- small shared helpers with no heavy imports (safe to import anywhere).

parse_bool:  configuration values. YAML `enabled: false` is already a bool, but a QUOTED
             "false" (or an env-style "0"/"off") is a non-empty string and therefore truthy in
             Python. Accepts the usual spellings; anything else raises ValueError naming the
             setting, so a typo stops the run instead of silently switching a feature on.
strict_true: MODEL OUTPUT. True only for an unambiguous yes (True, "true", "yes", "1", ...);
             everything else, including garbage, is False. Fail closed: an unparseable
             verification result is never treated as a pass.
"""
from typing import Any

_TRUE = {"true", "yes", "y", "on", "1"}
_FALSE = {"false", "no", "n", "off", "0"}


def parse_bool(value: Any, default: bool, name: str = "value") -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if s == "":
            return default
        if s in _TRUE:
            return True
        if s in _FALSE:
            return False
    raise ValueError(f"{name}: expected a boolean (true/false, yes/no, on/off, 1/0), got {value!r}")


def strict_true(value: Any) -> bool:
    try:
        return parse_bool(value, False) is True
    except ValueError:
        return False
