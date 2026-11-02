"""ISP detection: ipinfo.io org lookup → supported ISP, cached per network.

The lookup happens at most once per network fingerprint and TTL, instead of
on every monitoring cycle as in 0.1.0. Public IPs are never persisted.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import socket
import time
from pathlib import Path

import httpx
import psutil

from app.core.config import load_isps
from app.core.paths import data_dir

log = logging.getLogger(__name__)
CACHE_TTL_S = 6 * 3600
UNKNOWN = "Unknown"

# Order matters: "SLT Mobitel" must resolve to Mobitel before the SLT rule.
# Word boundaries so e.g. "slt" does not match "consulting".
_COMPILED = {
    name: re.compile(r"\b(?:" + "|".join(re.escape(p) for p in srv.org_patterns) + r")\b")
    for name, srv in load_isps().items() if srv.org_patterns
}


def identify_isp(org: str) -> str:
    value = (org or "").lower()
    for isp, pattern in _COMPILED.items():
        if pattern.search(value):
            return isp
    return UNKNOWN


def network_fingerprint() -> str:
    """Hash of local non-loopback interface addresses; changes when the network changes."""
    addrs: list[str] = []
    for nic, entries in psutil.net_if_addrs().items():
        if nic == "lo" or nic.lower().startswith("loopback"):
            continue
        for a in entries:
            # Compare with socket constants: on Windows psutil reports MAC
            # entries with a plain int family (-1) that has no .name.
            if a.family in (socket.AF_INET, socket.AF_INET6) and not a.address.startswith("fe80"):
                addrs.append(f"{nic}={a.address}")
    return hashlib.sha256("|".join(sorted(addrs)).encode()).hexdigest()[:16]


def _cache_path() -> Path:
    return data_dir() / "isp_cache.json"


def _lookup() -> dict:
    with httpx.Client(timeout=10.0, follow_redirects=True, trust_env=False) as client:
        response = client.get("https://ipinfo.io/json")
        response.raise_for_status()
        info = response.json()
    org = str(info.get("org") or "")
    return {
        "ip": str(info.get("ip") or ""),          # shown in UI only, never cached
        "organization": org or "Unavailable",
        "isp": identify_isp(org),
        "city": str(info.get("city") or ""),
        "country": str(info.get("country") or ""),
    }


def detect_current_isp(force: bool = False) -> dict:
    """Return {"isp", "organization", ..., "cached": bool}. Uses the cache
    unless forced, expired, or the network fingerprint changed."""
    fp = network_fingerprint()
    path = _cache_path()
    if not force and path.exists():
        try:
            c = json.loads(path.read_text(encoding="utf-8"))
            if c.get("fingerprint") == fp and time.time() - c.get("at", 0) < CACHE_TTL_S:
                return {**c["info"], "ip": "", "cached": True}
        except (OSError, ValueError, KeyError):
            log.warning("ignoring unreadable ISP cache")
    info = _lookup()
    stored = {k: v for k, v in info.items() if k != "ip"}
    try:
        path.write_text(json.dumps({"fingerprint": fp, "at": time.time(), "info": stored}),
                        encoding="utf-8")
    except OSError:
        log.warning("could not write ISP cache", exc_info=True)
    return {**info, "cached": False}
