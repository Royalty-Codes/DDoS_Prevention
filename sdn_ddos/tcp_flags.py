"""Small tcpdump-backed TCP flag counter for measured capture windows."""

from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TcpFlagSnapshot:
    syn: int
    ack: int


class TcpFlagCounter:
    """Counts observed TCP SYN and ACK packets at the internal web host."""

    def __init__(self, host: Any) -> None:
        self.host = host
        self._syn = 0
        self._ack = 0
        self._lock = threading.Lock()
        self._process: Any | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        interface = f"{self.host.name}-eth0"
        self._process = self.host.popen(
            ["tcpdump", "-l", "-n", "-i", interface, "tcp"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self._thread = threading.Thread(target=self._consume, daemon=True)
        self._thread.start()

    def snapshot(self) -> TcpFlagSnapshot:
        with self._lock:
            return TcpFlagSnapshot(self._syn, self._ack)

    def delta(self, previous: TcpFlagSnapshot) -> TcpFlagSnapshot:
        current = self.snapshot()
        return TcpFlagSnapshot(max(0, current.syn - previous.syn), max(0, current.ack - previous.ack))

    def stop(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _consume(self) -> None:
        if self._process is None or self._process.stdout is None:
            return
        for line in self._process.stdout:
            flags = line.split("Flags ", 1)[-1]
            with self._lock:
                # tcpdump reports SYN/ACK as [S.]; count it as both a SYN and ACK.
                if "[S" in flags:
                    self._syn += 1
                if "." in flags:
                    self._ack += 1
