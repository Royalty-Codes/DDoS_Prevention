"""Rewrite the three assignment notebooks against the captured Mininet dataset."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parent
DATA_CANDIDATES = [
    "data/processed/sdn_ddos_controlled_lab_mininet.parquet",
]

COMMON_SETUP = r'''
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from IPython.display import display

PROJECT_ROOT = Path.cwd()
for candidate_root in (PROJECT_ROOT, PROJECT_ROOT.parent, PROJECT_ROOT.parent.parent):
    for relative_path in DATA_CANDIDATES:
        candidate = candidate_root / relative_path
        if candidate.exists():
            DATA_PATH = candidate
            break
    else:
        continue
    break
else:
    raise FileNotFoundError(
        "The Mininet dataset was not found. Expected "
        "data/processed/sdn_ddos_controlled_lab_mininet.parquet."
    )

df = pd.read_parquet(DATA_PATH)
expected_columns = [
    "timestamp_utc", "experiment_id", "scenario_id", "switch_id", "src_host",
    "dst_host", "protocol", "application", "window_seconds", "packet_count",
    "byte_count", "flow_count", "packet_rate", "byte_rate", "flow_rate",
    "mean_packet_size", "tcp_syn_count", "tcp_ack_count",
    "tcp_handshake_completion_ratio", "flow_table_size", "packet_in_count",
    "controller_cpu_proxy_pct", "attack_intensity", "attacker_count",
    "background_traffic_level", "label", "attack_family", "data_source",
]
if list(df.columns) != expected_columns:
    raise ValueError(f"Expected the 28-column contract, got {len(df.columns)} columns")
if df["label"].nunique() != 11:
    raise ValueError(f"Expected 11 traffic classes, got {df['label'].nunique()}")
numeric_columns = [column for column in expected_columns if column not in {
    "timestamp_utc", "experiment_id", "scenario_id", "switch_id", "src_host",
    "dst_host", "protocol", "application", "label", "attack_family", "data_source",
}]
df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric, errors="raise")
print(f"Loaded {len(df):,} rows and {len(df.columns)} columns from {DATA_PATH}")
print(f"Source values: {sorted(df['data_source'].unique())}")
'''


def markdown(text: str):
    return nbf.v4.new_markdown_cell(text)


def code(text: str):
    return nbf.v4.new_code_cell(text.strip() + "\n")


def notebook(title: str, objective: str, plots: list[tuple[str, str]]) -> nbf.NotebookNode:
    cells = [
        markdown(f"# {title}\n\n{objective}\n\nThis notebook uses the captured Mininet/OVS dataset and keeps the project’s 28-column, 11-class schema."),
        code("DATA_CANDIDATES = " + repr(DATA_CANDIDATES) + "\n" + COMMON_SETUP),
    ]
    for heading, source in plots:
        cells.append(markdown(f"## {heading}"))
        cells.append(code(source))
    cells.append(markdown("## Interpretation\n\nThe figures describe measured packet/byte counters and derived window rates. Controller-only values are interpreted according to the capture metadata; they are not presented as Ryu measurements when Ryu was unavailable."))
    result = nbf.v4.new_notebook(cells=cells)
    result.metadata.kernelspec = {"display_name": "Python 3", "language": "python", "name": "python3"}
    result.metadata.language_info = {"name": "python", "version": "3"}
    return result


notebooks = {
    "24059_Roydon_LA1.ipynb": notebook(
        "24059 Roydon — Traffic Behaviour",
        "Explore how volume, packet sizes, and TCP behaviour differ across the traffic classes.",
        [
            ("Packet rate versus byte rate", r'''
sample = df.sample(n=min(8000, len(df)), random_state=7)
fig = px.scatter(
    sample, x="packet_rate", y="byte_rate", color="label",
    size="mean_packet_size", hover_data=["protocol", "src_host"],
    log_x=True, log_y=True, title="Measured Packet Rate versus Byte Rate",
)
fig.update_layout(template="plotly_white")
display(fig)
'''),
            ("Packet-rate distribution by class", r'''
fig = px.violin(
    df, x="label", y="packet_rate", color="label", box=True, points=False,
    log_y=True, title="Packet-Rate Shape by Traffic Class",
)
fig.update_xaxes(tickangle=45)
fig.update_layout(template="plotly_white", showlegend=False)
display(fig)
'''),
            ("TCP SYN and ACK counts", r'''
tcp_summary = (
    df[df["protocol"] == "TCP"]
    .groupby("label", as_index=False)[["tcp_syn_count", "tcp_ack_count"]]
    .mean()
    .melt(id_vars="label", var_name="metric", value_name="mean_count")
)
fig = px.bar(
    tcp_summary, x="label", y="mean_count", color="metric", barmode="group",
    title="Observed TCP SYN and ACK Counts per Window",
)
fig.update_xaxes(tickangle=45)
fig.update_layout(template="plotly_white")
display(fig)
'''),
            ("Mean packet size by protocol", r'''
fig = px.box(
    df, x="protocol", y="mean_packet_size", color="protocol", points=False,
    title="Measured Mean Packet Size by Protocol",
)
fig.update_layout(template="plotly_white", showlegend=False)
display(fig)
'''),
            ("Rate-feature correlation", r'''
rate_columns = ["packet_rate", "byte_rate", "flow_rate", "mean_packet_size", "flow_table_size", "packet_in_count"]
correlation = df[rate_columns].corr()
fig = px.imshow(
    correlation, text_auto=".2f", zmin=-1, zmax=1, color_continuous_scale="RdBu_r",
    title="Correlation of Measured Traffic and Flow Features",
)
fig.update_layout(template="plotly_white")
display(fig)
'''),
        ],
    ),
    "24063_Satya_LA1.ipynb": notebook(
        "24063 Satya — Dataset Overview",
        "Audit balance, class taxonomy, protocol composition, and target services in the measured dataset.",
        [
            ("Records by traffic class", r'''
counts = df["label"].value_counts().rename_axis("label").reset_index(name="records")
fig = px.bar(counts, x="label", y="records", color="label", text="records", title="Measured Records per Traffic Class")
fig.update_xaxes(tickangle=45)
fig.update_layout(template="plotly_white", showlegend=False)
display(fig)
'''),
            ("Records by attack family", r'''
families = df["attack_family"].value_counts().rename_axis("attack_family").reset_index(name="records")
fig = px.pie(families, names="attack_family", values="records", hole=0.35, title="Measured Records by Attack Family")
fig.update_layout(template="plotly_white")
display(fig)
'''),
            ("Protocol composition", r'''
protocols = df.groupby(["label", "protocol"], as_index=False).size().rename(columns={"size": "records"})
fig = px.bar(protocols, x="label", y="records", color="protocol", barmode="stack", title="Protocol Composition of Each Class")
fig.update_xaxes(tickangle=45)
fig.update_layout(template="plotly_white")
display(fig)
'''),
            ("Packet-rate distribution", r'''
fig = px.box(df, x="label", y="packet_rate", color="label", points=False, log_y=True, title="Measured Packet-Rate Distribution")
fig.update_xaxes(tickangle=45)
fig.update_layout(template="plotly_white", showlegend=False)
display(fig)
'''),
            ("Traffic directed to services", r'''
destinations = df.groupby(["dst_host", "attack_family"], as_index=False).size().rename(columns={"size": "records"})
fig = px.bar(destinations, x="dst_host", y="records", color="attack_family", barmode="stack", title="Measured Traffic Directed to Target Services")
fig.update_layout(template="plotly_white")
display(fig)
'''),
        ],
    ),
    "24076_Prithvi_LA1.ipynb": notebook(
        "24076 Prithvi — SDN Telemetry",
        "Inspect measured switch counters and the flow-table pressure features used by the SDN detection pipeline.",
        [
            ("Mean packet rate by switch and family", r'''
switch_summary = df.groupby(["switch_id", "attack_family"], as_index=False)["packet_rate"].mean()
fig = px.bar(switch_summary, x="switch_id", y="packet_rate", color="attack_family", barmode="group", title="Mean Measured Packet Rate by Switch and Family")
fig.update_layout(template="plotly_white")
display(fig)
'''),
            ("Packet pressure versus flow-table size", r'''
pressure = df.groupby("label", as_index=False)[["packet_in_count", "flow_table_size"]].mean()
fig = px.scatter(pressure, x="flow_table_size", y="packet_in_count", color="label", text="label", title="Packet-In Pressure versus Flow-Table Size")
fig.update_traces(textposition="top center")
fig.update_layout(template="plotly_white")
display(fig)
'''),
            ("Controller-pressure proxy by family", r'''
family_pressure = df.groupby("attack_family", as_index=False)[["controller_cpu_proxy_pct", "flow_table_size"]].mean()
long_pressure = family_pressure.melt(id_vars="attack_family", var_name="metric", value_name="mean_value")
fig = px.bar(long_pressure, x="attack_family", y="mean_value", color="metric", barmode="group", title="Captured Flow Pressure and Controller-Proxy Fields")
fig.update_xaxes(tickangle=45)
fig.update_layout(template="plotly_white")
display(fig)
'''),
            ("Measured telemetry feature space", r'''
sample = df.sample(n=min(6000, len(df)), random_state=23)
fig = px.scatter_3d(sample, x="byte_rate", y="packet_in_count", z="flow_table_size", color="label", title="Measured SDN Telemetry Feature Space")
fig.update_layout(template="plotly_white")
display(fig)
'''),
            ("Victim-side packet rate", r'''
service_summary = df.groupby(["dst_host", "attack_family"], as_index=False)[["packet_rate", "packet_in_count"]].mean()
fig = px.bar(service_summary, x="dst_host", y="packet_rate", color="attack_family", barmode="group", title="Mean Measured Packet Rate by Target Service")
fig.update_layout(template="plotly_white")
display(fig)
'''),
        ],
    ),
}


for filename, notebook_node in notebooks.items():
    path = ROOT / filename
    nbf.write(notebook_node, path)
    print(f"wrote {path}")
