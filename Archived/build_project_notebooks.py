from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parent

def notebook(path, cells):
    nb = nbf.v4.new_notebook()
    nb.metadata = {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}}
    nb.cells = [nbf.v4.new_markdown_cell(value) if kind == 'md' else nbf.v4.new_code_cell(value) for kind, value in cells]
    nbf.write(nb, ROOT / path)

generator = [
('md', '# SDN DDoS Dataset Generation\n\n## tl;dr\n\nBuilds a 110,000-row Parquet dataset for the isolated Mininet/OVS/Ryu project. This baseline is produced from the controlled local-lab schedule and is explicitly labeled `controlled_lab_profile`; it is not captured public-network DDoS traffic.'),
('md', '## Context & Methods\n\nThe canonical schema supports real OpenFlow snapshots when the Ryu controller is running. This notebook first validates the project location, then generates reproducible per-window records for benign, volumetric, protocol, application, and SDN-control-plane stress profiles.\n\n### Key Assumptions\n- Run in Ubuntu WSL from the project directory.\n- The experiment is local to Mininet; no external target is permitted.'),
('code', """from pathlib import Path\nimport os, sys\nROOT = Path.cwd().resolve().parent if Path.cwd().name == 'notebooks' else Path.cwd().resolve()\nNETWORK = ROOT / 'Network and Traffic'\nsys.path.insert(0, str(NETWORK))\nassert (NETWORK / 'dataset' / 'dataset_builder.py').exists(), ROOT\nprint('Project:', ROOT)\nprint('Data destination:', ROOT / 'data' / 'processed')"""),
('md', '## Generate and validate'),
('code', """from pathlib import Path\nimport yaml\nfrom traffic.scenarios import SCENARIOS\nfrom dataset.dataset_builder import build_lab_dataset\nconfig = yaml.safe_load((NETWORK / 'config' / 'experiment.yaml').read_text())\noutput_path = (NETWORK / 'config' / config['dataset_output']).resolve()\ndataset = build_lab_dataset(SCENARIOS, config['rows_per_scenario'], output_path, config['seed'])\nprint(f'Rows: {len(dataset):,}; columns: {len(dataset.columns)}')\nprint(dataset.label.value_counts().sort_index())\nassert len(dataset) == len(SCENARIOS) * config['rows_per_scenario']\nassert dataset.isna().sum().sum() == 0\nassert dataset.packet_rate.ge(0).all()\ndisplay(dataset.head())"""),
('md', '## Outputs\n\nThe Parquet file is saved under `data/processed/`. Metadata records the source distinction and class set. Use notebook 02 to load this dataset with PySpark.'),
('code', """metadata_path = output_path.with_suffix('.json')\nprint(output_path)\nprint(metadata_path.read_text())"""),
('md', '## Takeaways\n\nThis is a large, balanced, reproducible project baseline containing 11 labeled classes. For a fully captured dataset, start the Ryu and Mininet scripts, collect OpenFlow snapshots into `data/raw`, then build the same canonical schema with `data_source=real_openflow`.')]

analytics = [
('md', '# PySpark SDN DDoS Analytics\n\n## tl;dr\n\nLoads the generated Parquet dataset through PySpark, cleans and preprocesses it, then renders five Plotly charts. Interpret findings as characteristics of this controlled experimental dataset.'),
('md', '## Context & Methods\n\nIdentifiers and ground-truth labels are never used as model features. Spark owns data preparation; only limited analysis samples are converted to pandas for Plotly.\n\n### Key Assumptions\n- Run after notebook 01.\n- Dataset path is `data/processed/sdn_ddos_controlled_lab.parquet`.'),
('code', """from pathlib import Path\nimport os\nfrom pyspark.sql import SparkSession, functions as F\nfrom pyspark.ml import Pipeline\nfrom pyspark.ml.feature import VectorAssembler, StandardScaler\nROOT = Path.cwd().resolve().parent if Path.cwd().name == 'notebooks' else Path.cwd().resolve()\nDATASET = ROOT / 'data' / 'processed' / 'sdn_ddos_controlled_lab.parquet'\nif not DATASET.exists(): raise FileNotFoundError('Run notebook 01 first: ' + str(DATASET))\nspark = SparkSession.builder.appName('SDN-DDoS-Analytics').master('local[*]').config('spark.sql.shuffle.partitions','16').getOrCreate()\nspark.sparkContext.setLogLevel('WARN')\nraw_df = spark.read.parquet(str(DATASET))\nprint('Rows:', raw_df.count(), 'Columns:', len(raw_df.columns)); raw_df.printSchema()"""),
('md', '## Clean data and enforce types'),
('code', """numeric = ['window_seconds','packet_count','byte_count','flow_count','packet_rate','byte_rate','flow_rate','mean_packet_size','tcp_syn_count','tcp_ack_count','tcp_handshake_completion_ratio','flow_table_size','packet_in_count','controller_cpu_proxy_pct','attack_intensity','attacker_count','background_traffic_level']\nclean_df = raw_df.dropDuplicates()\nfor column in numeric: clean_df = clean_df.withColumn(column, F.col(column).cast('double'))\nclean_df = clean_df.fillna(0.0, subset=numeric).filter((F.col('packet_rate') >= 0) & (F.col('byte_rate') >= 0) & F.col('tcp_handshake_completion_ratio').between(0,1))\nprint('Clean rows:', clean_df.count())\nclean_df.groupBy('label').count().orderBy('label').show(20, False)"""),
('md', '## Preprocess numerical features'),
('code', """features = [c for c in numeric if c not in ['attack_intensity']]\npipeline = Pipeline(stages=[VectorAssembler(inputCols=features, outputCol='features_raw', handleInvalid='keep'), StandardScaler(inputCol='features_raw', outputCol='features_scaled', withMean=False, withStd=True)])\nprocessed_df = pipeline.fit(clean_df).transform(clean_df).cache()\nprint('Feature count:', len(features), 'Processed rows:', processed_df.count())"""),
('md', '## Results: bounded Plotly data'),
('code', """import plotly.express as px\nclass_counts = clean_df.groupBy('label').count().orderBy('label').toPandas()\nsummary = clean_df.groupBy('label').agg(F.avg('packet_rate').alias('mean_packet_rate'),F.avg('byte_rate').alias('mean_byte_rate'),F.avg('tcp_handshake_completion_ratio').alias('mean_completion'),F.avg('controller_cpu_proxy_pct').alias('mean_controller_pressure')).orderBy('label').toPandas()\nplot_data = clean_df.select('label','attack_family','packet_rate','byte_rate','tcp_handshake_completion_ratio','packet_in_count','controller_cpu_proxy_pct','flow_table_size').sample(False, .1, seed=42).limit(12000).toPandas()\nprint(summary.to_string(index=False))"""),
('md', '### 1. Class distribution\n\n**Inference:** the equal bars are intentional. They make comparative ML experiments easier, but they do not represent deployment prevalence.'),
('code', "fig=px.bar(class_counts,x='label',y='count',color='label',title='Records by Ground-Truth Class'); fig.update_layout(showlegend=False,xaxis_tickangle=-35); fig.show()"),
('md', '### 2. Packet rate by scenario\n\n**Inference:** volumetric and control-plane-stress profiles should sit above benign traffic; slow-rate behavior proves a single rate threshold is insufficient.'),
('code', "fig=px.box(plot_data,x='label',y='packet_rate',color='attack_family',points=False,title='Packet Rate by Scenario'); fig.update_layout(xaxis_tickangle=-35); fig.show()"),
('md', '### 3. Packet rate versus byte rate\n\n**Inference:** this view separates small-packet rate pressure from high-byte-rate payload behavior.'),
('code', "px.scatter(plot_data,x='packet_rate',y='byte_rate',color='label',hover_data=['attack_family'],title='Packet Rate vs Byte Rate').show()"),
('md', '### 4. TCP handshake completion\n\n**Inference:** SYN and slow-rate profiles are expected to have lower TCP completion than normal TCP. Do not interpret non-TCP zero values as failed TCP handshakes.'),
('code', "tcp=plot_data[plot_data.label.isin(['BENIGN','SYN_FLOOD','HTTP_FLOOD','SLOWLORIS_STYLE','LAND_STYLE'])]; px.violin(tcp,x='label',y='tcp_handshake_completion_ratio',color='label',box=True,points=False,title='TCP Handshake Completion Ratio').show()"),
('md', '### 5. SDN control-plane pressure\n\n**Inference:** packet-in activity paired with the controller pressure proxy connects the analysis to SDN-specific impact, beyond generic flow features.'),
('code', "px.scatter(plot_data,x='packet_in_count',y='controller_cpu_proxy_pct',color='label',size='flow_table_size',title='Packet-In Activity vs Controller Pressure Proxy').show()"),
('md', '## Takeaways\n\nThe clean and scaled Spark DataFrame is ready for model development. Re-run the same notebook with captured Ryu/OpenFlow records and `data_source=real_openflow` before making claims about live-network accuracy.'),
('code', 'spark.stop(); print("Analytics complete.")')]

(ROOT / 'notebooks').mkdir(exist_ok=True)
notebook('notebooks/01_SDN_DDoS_Dataset_Generator.ipynb', generator)
notebook('notebooks/02_PySpark_DDoS_Analytics.ipynb', analytics)
print('notebooks created')
