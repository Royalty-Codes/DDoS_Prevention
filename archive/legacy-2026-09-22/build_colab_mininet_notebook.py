"""Build a Colab companion that checks Mininet prerequisites before capture."""

from pathlib import Path

import nbformat as nbf


def md(text: str):
    return nbf.v4.new_markdown_cell(text)


def code(text: str):
    return nbf.v4.new_code_cell(text.strip() + "\n")


cells = [
    md("""# Mininet/OVS Dataset Capture in Google Colab

## tl;dr

This notebook attempts to install Mininet, Open vSwitch, tcpdump, and iperf3, then performs a **hard preflight** for the Linux privileges and kernel support required by Mininet. Standard hosted Colab runtimes commonly lack the required OVS/kernel networking access. If that happens, the notebook stops with an explicit explanation instead of generating NumPy/Pandas profiles and mislabeling them as Mininet telemetry.

For a genuine capture, run this notebook on a privileged Linux VM or self-hosted Colab runtime, or use the included WSL runner. All traffic remains inside the isolated Mininet namespace and the output keeps the project’s 28-column, 11-class schema."""),
    md("## 1. Install runtime packages"),
    code(r'''
import os
import subprocess
import sys
from pathlib import Path


def run(command, check=True):
    print("$", " ".join(command))
    return subprocess.run(command, check=check, text=True)


print("Python:", sys.version)
print("Effective UID:", os.geteuid())
run(["apt-get", "update", "-qq"])
run(["apt-get", "install", "-y", "-qq", "mininet", "openvswitch-switch", "tcpdump", "iperf3"])
run(["python", "-m", "pip", "install", "-q", "pandas", "pyarrow", "plotly", "nbformat"])
'''),
    md("## 2. Hard Mininet/OVS preflight"),
    code(r'''
import shutil

checks = {
    "running_as_root": os.geteuid() == 0,
    "mn_binary": shutil.which("mn") is not None,
    "ovs_vsctl_binary": shutil.which("ovs-vsctl") is not None,
    "ovs_ofctl_binary": shutil.which("ovs-ofctl") is not None,
    "tcpdump_binary": shutil.which("tcpdump") is not None,
    "tun_device": Path("/dev/net/tun").exists(),
}
for name, passed in checks.items():
    print(f"{name}: {'PASS' if passed else 'FAIL'}")

if not all(checks.values()):
    raise RuntimeError(
        "This hosted runtime cannot run a genuine Mininet/OVS capture. "
        "Use a privileged Linux VM, a self-hosted Colab runtime, or the WSL "
        "command documented below. Do not use the synthetic generator as a "
        "replacement for captured telemetry."
    )
'''),
    md("## 3. Mount persistent results and fetch the source tree"),
    code(r'''
from google.colab import drive

drive.mount("/content/drive")
RESULT_ROOT = Path("/content/drive/MyDrive/sdn_ddos_mininet_results")
RESULT_ROOT.mkdir(parents=True, exist_ok=True)

REPO_URL = "https://github.com/Royalty-Codes/DDoS_Prevention.git"
REPO_ROOT = Path("/content/DDoS_Prevention")
if REPO_ROOT.exists():
    run(["rm", "-rf", str(REPO_ROOT)])
run(["git", "clone", REPO_URL, str(REPO_ROOT)])
os.chdir(REPO_ROOT)
print("Source checkout:", subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip())
'''),
    md("## 4. Smoke-test the isolated Mininet namespace"),
    code(r'''
run(["mn", "-c"], check=False)
smoke = subprocess.run(["mn", "--test", "pingall"], text=True, capture_output=True)
print(smoke.stdout[-4000:])
if smoke.returncode != 0 or "0% dropped" not in smoke.stdout:
    raise RuntimeError(
        "Mininet package installation succeeded, but the isolated topology "
        "smoke test did not pass. Inspect the captured output before running "
        "the 110k-row experiment."
    )
'''),
    md("## 5. Capture the 110k-row measured dataset"),
    code(r'''
raw_path = Path("/content/mininet_ovs_110k.csv")
command = [
    "python", "-m", "network.dataset.capture_mininet_ovs",
    "--rows-per-class", "10000",
    "--source-count", "20",
    "--sample-interval", "0.25",
    "--output", str(raw_path),
]
print("Expected runtime: approximately 0.5–0.85 hours on a comparable privileged VM; measure the actual wall time here.")
run(command)
if not raw_path.exists():
    raise FileNotFoundError(raw_path)
'''),
    md("## 6. Validate, convert, and persist"),
    code(r'''
processed_path = Path("/content/sdn_ddos_controlled_lab_mininet.parquet")
run([
    "python", "-m", "network.dataset.finalize_mininet_dataset",
    "--input", str(raw_path),
    "--output", str(processed_path),
    "--rows-per-class", "10000",
])

import pandas as pd
captured = pd.read_parquet(processed_path)
print("Shape:", captured.shape)
print(captured["label"].value_counts().sort_index())
destination = RESULT_ROOT / processed_path.name
destination.write_bytes(processed_path.read_bytes())
(RESULT_ROOT / "sdn_ddos_controlled_lab_mininet.csv").write_bytes(
    processed_path.with_suffix(".csv").read_bytes()
)
print("Persisted:", destination)
'''),
    md("## Supported execution path when hosted Colab fails") ,
    code(r'''
print("Run the real capture from WSL/Ubuntu instead:")
print(
    "wsl.exe -d Ubuntu-26.04 -u root -- bash -c "
    "'cd /mnt/d/Bunker/BaseCamp/WirelessCommunication/DDoS_Prevention; "
    "python3 -m network.dataset.capture_mininet_ovs "
    "--rows-per-class 10000 --source-count 20 --sample-interval 0.25 "
    "--output data/raw/mininet_ovs_110k.csv'"
)
'''),
]

notebook = nbf.v4.new_notebook(cells=cells)
notebook.metadata.kernelspec = {"display_name": "Python 3", "language": "python", "name": "python3"}
notebook.metadata.language_info = {"name": "python", "version": "3"}
nbf.write(notebook, Path(__file__).resolve().parent / "colab_mininet_dataset_generator.ipynb")
print("wrote colab_mininet_dataset_generator.ipynb")
