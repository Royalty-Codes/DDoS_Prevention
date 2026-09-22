# SDN DDoS Analytics

Install the local analysis dependencies once before generating data or opening the ML notebook:

```bash
python3 -m pip install -r requirements.txt
```

Run the versatile controlled-telemetry generator from the project root:

```bash
./network/scripts/generate_dataset.sh --rows-per-class 3000
```

This writes equal numbers of all 13 classes (benign plus 12 DDoS classes) to:

- `data/processed/sdn_ddos_versatile.parquet`
- `data/processed/sdn_ddos_versatile.csv`
- `data/processed/sdn_ddos_versatile.json`

Open the notebooks in order:

1. `01_dataset_overview.ipynb`: balance, families, protocols, rates, destinations.
2. `02_traffic_behavior.ipynb`: volume, TCP controls, flow pressure, intensity, correlations.
3. `03_sdn_telemetry.ipynb`: switch activity, Packet-In pressure, port load, controller proxy, services.
4. `04_ml_model_training.ipynb`: held-out training and evaluation of Decision Tree, Random Forest, KNN, and Logistic Regression, with metric, latency, confusion-matrix, and feature-importance plots.

Each notebook uses PySpark to load, deduplicate, remove nulls, cast numeric fields, and filter invalid measurements. Plotly and Plotly Express render five visualizations per notebook. Markdown immediately after each plot states the intended inference.

The v3 generator produces 63 columns across temporal context, flow distributions, protocol behavior, OpenFlow-table pressure, Packet-In activity, controller latency, queues, drops, and link utilization. It is a controlled synthetic dataset for pipeline development, not a packet capture and not a measurement of Internet traffic. Real OpenFlow JSONL telemetry from Ryu is the next ingestion boundary.

The training notebook deliberately excludes identifiers, labels, attack-family metadata, attack intensity, and attacker count from its features. It saves run artifacts in `analytics/results/`.
