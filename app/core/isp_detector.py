import re

import httpx

# Order matters: "SLT Mobitel" must resolve to Mobitel before the SLT rule runs.
# Patterns are matched on word boundaries so e.g. "slt" does not match "consulting".
ISP_PATTERNS = {
    "Mobitel": ("mobitel",),
    "Dialog": ("dialog", "axiata"),
    "SLT": ("sri lanka telecom", "slt"),
    "Hutch": ("hutch", "hutchison"),
}

_COMPILED = {
    isp: re.compile(r"\b(?:" + "|".join(re.escape(p) for p in patterns) + r")\b")
    for isp, patterns in ISP_PATTERNS.items()
}


def identify_isp(org: str) -> str:
    value = (org or "").lower()
    for isp, pattern in _COMPILED.items():
        if pattern.search(value):
            return isp
    return "Unknown"


def detect_current_isp():
    """Return public IP, organization and best-effort ISP classification."""
    with httpx.Client(timeout=10.0, follow_redirects=True, trust_env=False) as client:
        response = client.get("https://ipinfo.io/json")
        response.raise_for_status()
        info = response.json()

    org = str(info.get("org") or "")
    return {
        "ip": str(info.get("ip") or "Unavailable"),
        "organization": org or "Unavailable",
        "isp": identify_isp(org),
        "city": str(info.get("city") or ""),
        "country": str(info.get("country") or ""),
    }
