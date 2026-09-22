"""Fail-closed host checks before a Mininet/OVS capture starts."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


REQUIRED_BINARIES = ("mn", "ovs-vsctl", "ovs-ofctl", "iperf3", "tcpdump", "curl", "nc", "ryu-manager")


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    details: dict[str, str]


def _binary_status(binary: str) -> str:
    """Resolve the configured controller binary as well as normal PATH tools."""

    if binary == "ryu-manager":
        configured = os.environ.get("RYU_MANAGER")
        if configured:
            return "found" if Path(configured).is_file() else "missing"
    return "found" if shutil.which(binary) else "missing"


def run_preflight(strict: bool = False) -> PreflightResult:
    details = {binary: _binary_status(binary) for binary in REQUIRED_BINARIES}
    details["effective_uid"] = str(os.geteuid()) if hasattr(os, "geteuid") else "unsupported"
    details["tun_device"] = "found" if Path("/dev/net/tun").exists() else "missing"
    details["ovs_service"] = "unknown"
    if shutil.which("ovs-vsctl"):
        result = subprocess.run(["ovs-vsctl", "show"], capture_output=True, text=True, check=False)
        details["ovs_service"] = "ready" if result.returncode == 0 else f"unavailable ({result.returncode})"
    ok = (
        details["effective_uid"] == "0"
        and details["tun_device"] == "found"
        and details["ovs_service"] == "ready"
        and all(details[binary] == "found" for binary in REQUIRED_BINARIES)
    )
    if strict and ok:
        # This is the first real capability check: Mininet must create kernel
        # namespaces, attach an OVS bridge, and pass traffic. Always clean up.
        try:
            try:
                smoke = subprocess.run(
                    ["mn", "--switch", "ovsbr", "--test", "pingall"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=90,
                )
                details["mininet_smoke"] = "passed" if smoke.returncode == 0 else f"failed ({smoke.returncode})"
            except subprocess.TimeoutExpired:
                details["mininet_smoke"] = "timed out"
        finally:
            subprocess.run(["mn", "-c"], capture_output=True, text=True, check=False)
        ok = ok and details["mininet_smoke"] == "passed"
    if strict and not ok:
        failures = ", ".join(
            f"{name}={value}"
            for name, value in details.items()
            if value not in {"found", "ready", "0", "passed"}
        )
        raise RuntimeError(f"Mininet/OVS preflight failed: {failures}")
    return PreflightResult(ok=ok, details=details)
