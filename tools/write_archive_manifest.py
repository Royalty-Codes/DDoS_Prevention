"""Create a content-hash manifest for the preserved pre-rebuild tree."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archive" / "legacy-2026-09-22"
OUTPUT = ARCHIVE / "archive_manifest.json"


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def main() -> None:
    records = []
    for path in sorted(ARCHIVE.rglob("*")):
        if not path.is_file() or path == OUTPUT:
            continue
        records.append(
            {
                "path": path.relative_to(ARCHIVE).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": digest(path),
            }
        )
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "archive_root": "archive/legacy-2026-09-22",
        "files": records,
        "file_count": len(records),
    }
    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=ARCHIVE) as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, OUTPUT)
    print(f"Wrote {len(records)} archive hashes to {OUTPUT}")


if __name__ == "__main__":
    main()
