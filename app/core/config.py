"""Typed loader for app/config/isps.json."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path


def _base_dir() -> Path:
    # PyInstaller one-file builds unpack data files under sys._MEIPASS.
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "app"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


CONFIG_PATH = _base_dir() / "config" / "isps.json"


@dataclass(frozen=True)
class IspServer:
    name: str
    display_name: str
    host: str
    port: int
    heartbeat_method: str
    heartbeat_path: str
    org_patterns: tuple[str, ...]
    scheme: str = "https"  # only tests use plain http

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    @property
    def heartbeat_url(self) -> str:
        return self.base_url + self.heartbeat_path


def load_isps(path: Path = CONFIG_PATH) -> dict[str, IspServer]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, IspServer] = {}
    for name, cfg in data["isps"].items():
        hb = cfg.get("heartbeat", {})
        method = str(hb.get("method", "GET")).upper()
        if method not in ("GET", "HEAD"):
            raise ValueError(f"{name}: heartbeat method must be GET or HEAD, got {method}")
        out[name] = IspServer(
            name=name,
            display_name=cfg.get("display_name", name),
            host=cfg["host"],
            port=int(cfg["port"]),
            heartbeat_method=method,
            heartbeat_path=hb.get("path", "/"),
            org_patterns=tuple(p.lower() for p in cfg.get("org_patterns", ())),
        )
    return out
