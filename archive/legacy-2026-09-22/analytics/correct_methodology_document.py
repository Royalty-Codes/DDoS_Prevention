"""Create a factually corrected copy of the methodology document."""
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile
from docx import Document

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "SDN_DDoS_Proposed_Methodology_and_Implementation.docx"
OUTPUT = ROOT / "SDN_DDoS_Proposed_Methodology_and_Implementation_Corrected.docx"


def paragraphs(document):
    items = list(document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                items.extend(cell.paragraphs)
    for section in document.sections:
        items.extend(section.header.paragraphs)
        items.extend(section.footer.paragraphs)
    return items


def set_text(paragraph, text):
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(text)


updates = {
    "This project presents an end-to-end framework integrating": "This project presents a proposed end-to-end framework. The currently implemented scope is the emulated SDN topology, telemetry collection, synthetic dataset generation, analytics, and offline model evaluation; streaming feature extraction and automated mitigation are planned:",
    "The physical and emulated network fabric is implemented": "The emulated laboratory network is implemented in Mininet using Open vSwitch (OVS) switches configured with OpenFlow 1.3. The laboratory topology (SdnDdosLabTopology) is a switched campus network:",
    "High-volume transport-layer floods rapidly exhaust switch Ternary Content-Addressable Memory (TCAM) flow table capacities and choke physical links.": "High-volume transport-layer floods can create OVS flow-table pressure and saturate emulated links. Hardware TCAM capacity is not measured in this software-emulated lab.",
    "over a secure TCP channel (port 6653)": "over a TCP control channel on port 6653. TLS is not configured in the current laboratory code:",
    "When an access switch receives a frame that misses all installed TCAM flow entries": "When an access switch receives a frame that misses installed OVS flow entries",
    "capturing byte counts, packet counts, active flow durations, and hardware drops without interrupting line-rate switching.": "capturing byte counts, packet counts, active flow durations, and port-drop counters. This collection does not measure hardware or line-rate performance.",
    "The PySpark engine ingests telemetry streams, partitions records into sliding temporal observation windows, and extracts a comprehensive 63-dimensional feature space:": "The current Python dataset generator produces a 63-column controlled synthetic telemetry schema. PySpark notebooks currently analyze the generated Parquet dataset; raw JSONL-to-window feature extraction is a proposed next step:",
    "The machine learning engine consumes windowed feature records": "The offline machine learning notebook consumes generated feature records, applies median imputation, standard scaling, and one-hot encoding, and classifies traffic into one of 13 categories. It excludes identifiers, simulation constants, protocol/application fields, and generated time fields (day_of_week and hour_of_day) to reduce synthetic-data leakage.",
    "Unlike passive intrusion detection systems that merely alert operators, our architecture implements an automated closed-loop defense:": "The following closed-loop defense is proposed for the next implementation stage; it is not yet connected to the current Ryu controller:",
    "Upon detecting an attack, the classifier extracts": "In the proposed deployment, the classifier would extract the offending ingress switch, port, source identity, and predicted attack class before handing the decision to a policy module.",
    "The controller immediately transmits high-priority OFPFlowMod instructions": "The proposed controller would transmit high-priority OFPFlowMod DROP rules only after the model-to-controller policy path and safeguards have been implemented and tested.",
    "the controller temporarily isolates or throttles": "The proposed controller could temporarily isolate or throttle an ingress port for spoofed floods, subject to a policy that protects legitimate traffic.",
    "the controller routes flows through OpenFlow 1.3 Meter Tables": "The proposed controller could use OpenFlow 1.3 Meter Tables for rate limiting after meter support and enforcement logic are implemented.",
    "Decision Trees are uniquely suited for SDN because their conditional rules can be mapped directly into OpenFlow TCAM flow tables.": "Decision Trees are interpretable, but a trained tree cannot be mapped directly to the current OpenFlow rules without a separate policy-translation and validation step.",
    "To rigorously evaluate detection effectiveness and operational feasibility, we implemented, tuned, and evaluated four distinct algorithms representing different learning paradigms:": "To evaluate detection effectiveness on the controlled synthetic dataset, we implemented and evaluated four algorithms representing different learning paradigms. Model settings are fixed in the notebook rather than selected through a hyperparameter search:",
    "Random Forest builds an ensemble of B=40 decorrelated decision trees with bounded depth, each trained on a bootstrap sample of the training dataset. At each node, the split is chosen from a randomly sampled feature subspace (max_features=0.7), maximizing Gini Impurity reduction. Final classification is determined by majority voting across all 40 individual trees. Hyperparameters: n_estimators=40, max_depth=12, min_samples_leaf=8, max_features=0.7, class_weight='balanced_subsample', random_state=42.": "Random Forest builds an ensemble of B=20 decorrelated decision trees with bounded depth, each trained on a bootstrap sample of the training data. At each node, the split is chosen from a randomly sampled feature subspace (max_features=0.7), maximizing Gini impurity reduction. Final classification is determined by majority voting. Hyperparameters: n_estimators=20, max_depth=12, min_samples_leaf=8, max_features=0.7, class_weight='balanced_subsample', random_state=42.",
    "Multinomial Logistic Regression models the posterior probability of each traffic class using the normalized exponential (softmax) function: P(Y=k|x) = exp(w_k^T x + b_k) / sum_j exp(w_j^T x + b_j). The model is optimized by minimizing the cross-entropy loss with L2 Tikhonov regularization: L(W) = -sum_i sum_k y_ik log P(Y=k|x_i) + (1 / 2C) ||W||_2^2. Hyperparameters: C=2.0, max_iter=1200, class_weight='balanced', solver='lbfgs', random_state=42.": "Multinomial Logistic Regression models class probabilities with a softmax function and is optimized using regularized cross-entropy loss. Hyperparameters: C=2.0, max_iter=400, class_weight='balanced', solver='lbfgs', random_state=42.",
    "The evaluation was conducted on a held-out test partition consisting of 5,850 samples (15% of the total dataset), which remained completely unseen during model training and hyperparameter selection.": "The evaluation used a stratified held-out test partition of 5,850 samples (15% of the controlled synthetic dataset). Model settings are fixed in the notebook; no hyperparameter search was performed.",
    "Random Forest achieved the top overall performance": "On this controlled synthetic split, Random Forest achieved the top overall performance with 81.59% accuracy and 0.8085 macro F1. Logistic Regression achieved 80.26% accuracy and 0.7978 macro F1, Decision Tree achieved 79.18% accuracy and 0.7891 macro F1, and KNN achieved 75.16% accuracy and 0.7482 macro F1. These results measure within-generator separation only and must not be interpreted as live-network or cross-dataset performance.",
    "For real-time SDN deployment, prediction latency dictates whether": "The following timings are one local offline Python benchmark of `pipeline.predict` on the held-out batch; they are not end-to-end SDN deployment latency. They exclude telemetry polling, serialization, Kafka/Spark processing, controller decisioning, and FlowMod installation. Logistic Regression was the fastest measured model at 0.0098 ms per record, followed by Decision Tree at 0.0075 ms, Random Forest at 0.0255 ms, and KNN at 0.1211 ms. These values should not be used to claim line-rate or microsecond mitigation capability.",
    "The normalized confusion matrix reveals near-perfect diagonal dominance": "The normalized confusion matrix summarizes errors for the best controlled-split model. It should be interpreted as a synthetic-data diagnostic; it does not establish zero false positives or performance on live OpenFlow telemetry.",
    "Feature importance analysis demonstrates that SDN-specific control plane telemetry provides the strongest signal for DDoS detection:": "For the current controlled-split Random Forest, impurity-based importance ranks TCP SYN ratio first, followed by UDP fragmentation ratio, TCP ACK ratio, mean packet size, and protocol entropy. Feature importance is descriptive, not causal, and does not establish operational detection value.",
    "packet_in_rate & packet_in_count: Ranked #1. A sudden surge in Packet-In requests is the primary symptom of both table-miss floods and controller starvation attacks.": "packet_in_rate & packet_in_count: candidate SDN telemetry signal; it was not a top-ranked feature in the current controlled-split run and requires validation with real controller data.",
    "flow_table_occupancy & flow_table_size: Captures rapid TCAM saturation during SYN floods and random-port scanning.": "flow_table_occupancy & flow_table_size: synthetic flow-table proxies, not measurements of hardware TCAM saturation.",
    "We recommend deploying a Two-Tier Hybrid Architecture:": "Proposed future architecture: a two-tier design may use a low-latency model for candidate alerts and a second model for offline review. It must not be described as deployed until model loading, controller integration, policy enforcement, and end-to-end latency tests are implemented.",
    "This project successfully implemented an end-to-end DDoS detection and mitigation pipeline": "This project currently provides an emulated SDN topology and telemetry collector, a controlled synthetic 63-column dataset, analytics notebooks, and an offline four-model evaluation. Kafka/Spark streaming ingestion, raw-telemetry feature extraction, live model inference, and automated mitigation remain planned work.",
}

metrics = {
    "Random Forest": ["0.8159 (81.59%)", "0.8123", "0.8159", "0.8085", "13.275 s", "0.0255 ms"],
    "Decision Tree": ["0.7918 (79.18%)", "0.7885", "0.7918", "0.7891", "2.822 s", "0.0075 ms"],
    "K-Nearest Neighbors": ["0.7516 (75.16%)", "0.7464", "0.7516", "0.7482", "0.341 s", "0.1211 ms"],
    "Logistic Regression": ["0.8026 (80.26%)", "0.7965", "0.8026", "0.7978", "9.151 s", "0.0098 ms"],
}

document = Document(SOURCE)
changed = 0
for paragraph in paragraphs(document):
    text = paragraph.text.strip()
    for old, new in updates.items():
        if old in text:
            set_text(paragraph, new)
            changed += 1
            break
for table in document.tables:
    for row in table.rows:
        model = row.cells[0].text.strip() if row.cells else ""
        if model in metrics and len(row.cells) == 7:
            for cell, value in zip(row.cells[1:], metrics[model]):
                set_text(cell.paragraphs[0], value)
            changed += 6

if changed < 24:
    raise RuntimeError(f"Only {changed} updates were applied; source document may have changed")
document.save(OUTPUT)

# Refresh the five data-derived figures embedded in the original document.
replacement_media = {
    "word/media/image_101.png": ROOT / "analytics/results/sdn_ddos_system_architecture.png",
    "word/media/image_102.png": ROOT / "analytics/results/class_distribution.png",
    "word/media/image_103.png": ROOT / "analytics/results/model_comparison.png",
    "word/media/image_104.png": ROOT / "analytics/results/inference_latency.png",
    "word/media/image_105.png": ROOT / "analytics/results/best_model_confusion_matrix.png",
    "word/media/image_106.png": ROOT / "analytics/results/random_forest_feature_importance.png",
}
with NamedTemporaryFile(dir=OUTPUT.parent, suffix=".docx", delete=False) as temporary:
    temporary_path = Path(temporary.name)
with ZipFile(OUTPUT) as source_zip, ZipFile(temporary_path, "w", ZIP_DEFLATED) as target_zip:
    for item in source_zip.infolist():
        if item.filename in replacement_media:
            target_zip.writestr(item, replacement_media[item.filename].read_bytes())
        else:
            target_zip.writestr(item, source_zip.read(item.filename))
temporary_path.replace(OUTPUT)
print(f"Saved {OUTPUT} with {changed} corrections")
