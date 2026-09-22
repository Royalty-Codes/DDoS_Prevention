"""Generate the portable Colab capture notebook with nbformat, not raw JSON."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "01_colab_sdn_capture.ipynb"


def code(source: str):
    return nbf.v4.new_code_cell(source.strip() + "\n")


def markdown(source: str):
    return nbf.v4.new_markdown_cell(source.strip() + "\n")


def build() -> None:
    notebook = nbf.v4.new_notebook()
    notebook.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    }
    notebook.cells = [
        markdown(
            """
            # Measured SDN DDoS Dataset Capture — Colab

            This notebook runs the same repository modules used in WSL. It does
            **not** generate NumPy/Pandas profiles. It captures safe, isolated
            Mininet/OVS/Ryu telemetry and resumes to exactly 10,000 windows for
            each of the 11 classes.

            ## Important runtime constraint

            Hosted Colab must provide root, `/dev/net/tun`, OVS service access,
            and Mininet network capabilities. The preflight below stops if any
            are unavailable; no synthetic fallback is allowed. Dataset shards
            live in Drive so an interrupted runtime can resume.
            """
        ),
        markdown("## 1. Clean reset, clone, fetch, and pull the latest Git modules"),
        code(
            """
            import os
            import shutil
            import subprocess
            from pathlib import Path

            from google.colab import drive

            REPOSITORY_URL = "https://github.com/Royalty-Codes/DDoS_Prevention.git"
            BRANCH = "master"
            PROJECT_DIR = Path("/content/ddos_prevention")
            DRIVE_ROOT = Path("/content/drive/MyDrive/sdn_ddos_measured_runs")

            drive.mount("/content/drive", force_remount=False)
            DRIVE_ROOT.mkdir(parents=True, exist_ok=True)

            # This is deliberately constrained to one known temporary clone.
            if PROJECT_DIR.exists():
                if PROJECT_DIR.parent != Path("/content") or PROJECT_DIR.name != "ddos_prevention":
                    raise RuntimeError(f"Refusing to remove unexpected path: {PROJECT_DIR}")
                shutil.rmtree(PROJECT_DIR)

            def run(command, cwd=None):
                print("+", " ".join(map(str, command)))
                subprocess.run(command, cwd=cwd, check=True)

            run(["git", "clone", "--branch", BRANCH, "--single-branch", REPOSITORY_URL, str(PROJECT_DIR)])
            # Always fetch first, then use fast-forward-only pull. Colab never
            # reuses stale local modules from an earlier runtime.
            run(["git", "-C", str(PROJECT_DIR), "fetch", "--all", "--tags", "--prune"])
            run(["git", "-C", str(PROJECT_DIR), "checkout", BRANCH])
            run(["git", "-C", str(PROJECT_DIR), "pull", "--ff-only", "origin", BRANCH])
            GIT_COMMIT = subprocess.check_output(["git", "-C", str(PROJECT_DIR), "rev-parse", "HEAD"], text=True).strip()
            print("Using Git commit:", GIT_COMMIT)
            """
        ),
        markdown("## 2. Install the Linux and Python dependencies"),
        code(
            """
            import sys

            if os.geteuid() != 0:
                raise RuntimeError("Mininet/OVS needs root. Hosted Colab did not provide it.")

            run(["apt-get", "update"])
            run([
                "apt-get", "install", "-y", "mininet", "openvswitch-switch",
                "tcpdump", "iperf3", "curl", "netcat-openbsd",
            ])
            run(["service", "openvswitch-switch", "start"])
            run([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "uv"])
            run([sys.executable, "-m", "pip", "install", "-e", ".[notebook]"], cwd=PROJECT_DIR)

            # Keep Ryu in a known-compatible interpreter. Mininet itself stays
            # on Colab's system Python, which owns the apt-installed package.
            RYU_VENV = Path("/content/ryu-py311")
            run(["uv", "venv", "--python", "3.11", str(RYU_VENV)])
            run([str(RYU_VENV / "bin/python"), "-m", "ensurepip", "--upgrade"])
            run([
                str(RYU_VENV / "bin/python"), "-m", "pip", "install", "--force-reinstall", "--no-deps",
                "setuptools==57.5.0", "wheel",
            ])
            run([
                str(RYU_VENV / "bin/python"), "-m", "pip", "install", "--no-build-isolation",
                "-r", "requirements-controller.txt",
            ], cwd=PROJECT_DIR)
            os.environ["RYU_MANAGER"] = str(RYU_VENV / "bin/ryu-manager")
            os.environ["RYU_PYTHON"] = str(RYU_VENV / "bin/python")
            os.environ["PATH"] = str(RYU_VENV / "bin") + os.pathsep + os.environ["PATH"]
            """
        ),
        markdown("## 3. Fail-closed Mininet/OVS/Ryu preflight"),
        code(
            """
            os.environ["SDN_DDOS_GIT_COMMIT"] = GIT_COMMIT
            run([sys.executable, "-m", "sdn_ddos.cli", "preflight", "--strict"], cwd=PROJECT_DIR)
            print("Preflight passed. The environment may now run the isolated lab.")
            """
        ),
        markdown("## 4. Capture a one-window-per-class smoke run"),
        code(
            """
            SMOKE_DIR = DRIVE_ROOT / "smoke"
            run([sys.executable, "-m", "sdn_ddos.cli", "smoke", "--run-dir", str(SMOKE_DIR)], cwd=PROJECT_DIR)
            print("Smoke shards:", SMOKE_DIR)
            """
        ),
        markdown("## 5. Resume the full 110,000-row measured capture"),
        code(
            """
            ROWS_PER_CLASS = 10_000
            RUN_ID = "measured_28x11_110k"
            RUN_DIR = DRIVE_ROOT / RUN_ID
            RUN_FULL_CAPTURE = False  # Change to True only after the smoke run passes.

            if RUN_FULL_CAPTURE:
                run([
                    sys.executable, "-m", "sdn_ddos.cli", "capture",
                    "--run-dir", str(RUN_DIR),
                    "--rows-per-class", str(ROWS_PER_CLASS),
                    "--resume",
                ], cwd=PROJECT_DIR)
            else:
                print("Full capture is armed but not started. Set RUN_FULL_CAPTURE = True after reviewing smoke output.")
            """
        ),
        markdown("## 6. Validate and materialize the final CSV and Parquet dataset"),
        code(
            """
            WRITE_FINAL_DATASET = False  # Set True only after every class reaches 10,000 rows.

            if WRITE_FINAL_DATASET:
                run([
                    sys.executable, "-m", "sdn_ddos.cli", "validate",
                    "--run-dir", str(RUN_DIR),
                    "--rows-per-class", str(ROWS_PER_CLASS),
                    "--write-final",
                ], cwd=PROJECT_DIR)
                print("Final artifacts:", RUN_DIR / "final")
            else:
                print("Validation is armed but not started.")
            """
        ),
        markdown(
            """
            ## Reproducibility record

            `run_manifest.json` records the Git commit, schema version, class
            quotas, checkpoint state, and capture timestamps. `validation_report.json`
            verifies the 28-field contract, balance, uniqueness, rate equations,
            controller observations, and multi-switch coverage.
            """
        ),
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook, OUTPUT)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    build()
