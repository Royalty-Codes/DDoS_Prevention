"""Generate a high-resolution, publication-quality architecture diagram
for the SDN DDoS Detection and Prevention Framework.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path

def create_architecture_diagram(output_path: Path):
    # Create canvas with high DPI and 16:10 aspect ratio
    fig, ax = plt.subplots(figsize=(16, 11), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(100) if False else ax.set_ylim(0, 100)
    ax.axis('off')
    
    # Background styling
    fig.patch.set_facecolor('#F8FAFC')
    ax.set_facecolor('#F8FAFC')

    # Color Palette - Professional Slate & Modern Tech Accents
    c_data_plane = '#E2E8F0'       # Slate 200
    c_data_border = '#64748B'      # Slate 500
    c_southbound = '#FEF3C7'       # Amber 100
    c_south_border = '#D97706'     # Amber 600
    c_control = '#DBEAFE'          # Blue 100
    c_control_border = '#2563EB'    # Blue 600
    c_analytics = '#EDE9FE'        # Purple 100
    c_analytics_border = '#7C3AED'  # Purple 600
    c_ml = '#DCFCE7'               # Green 100
    c_ml_border = '#16A34A'        # Green 600
    c_mitigation = '#FEE2E2'       # Red 100
    c_mitigation_border = '#DC2626'# Red 600

    # Helper function for drawing rounded boxes
    def draw_box(x, y, w, h, bg, border, title="", subtitle="", radius=1.5, lw=1.8, title_color='#0F172A'):
        box = patches.FancyBboxPatch((x, y), w, h,
                                     boxstyle=f"round,pad={radius},rounding_size={radius}",
                                     facecolor=bg, edgecolor=border, linewidth=lw, zorder=2)
        ax.add_patch(box)
        if title:
            ax.text(x + w/2, y + h - 2.8, title, ha='center', va='center',
                    fontsize=11.5, fontweight='bold', color=title_color, zorder=5)
        if subtitle:
            ax.text(x + w/2, y + h - 5.5, subtitle, ha='center', va='center',
                    fontsize=8.5, style='italic', color='#475569', zorder=5)

    def draw_subcomponent(x, y, w, h, title, items=None, bg='#FFFFFF', border='#CBD5E1', lw=1.2):
        sub = patches.FancyBboxPatch((x, y), w, h,
                                     boxstyle="round,pad=0.8,rounding_size=0.8",
                                     facecolor=bg, edgecolor=border, linewidth=lw, zorder=3)
        ax.add_patch(sub)
        ax.text(x + w/2, y + h - 2.0, title, ha='center', va='center',
                fontsize=9.5, fontweight='bold', color='#1E293B', zorder=5)
        if items:
            for idx, item in enumerate(items):
                ax.text(x + 2.0, y + h - 4.5 - (idx * 2.2), f"• {item}", ha='left', va='center',
                        fontsize=7.8, color='#334155', zorder=5)

    # 1. Main Header
    ax.text(50, 97.5, "SDN DDoS Detection, Analytics & Closed-Loop Mitigation Framework",
            ha='center', va='center', fontsize=18, fontweight='bold', color='#0F172A')
    ax.text(50, 95.0, "Implemented SDN Lab and Offline ML Baseline with Proposed Streaming and Mitigation Extensions",
            ha='center', va='center', fontsize=10.5, color='#475569')

    # ==========================================
    # LAYER 1: DATA PLANE (MININET & OVS)
    # ==========================================
    draw_box(4, 3, 92, 22, c_data_plane, c_data_border,
             "1. DATA PLANE & INFRASTRUCTURE LAYER (Mininet / Open vSwitch)",
             "Emulated lab fabric: 4 OpenFlow 1.3 switches (s1-s4) and multi-path 100 Mbps links")
    
    # Clients Subcomponent
    draw_subcomponent(6, 4.5, 20, 15.5, "Legitimate Campus Hosts",
                      ["Clients c1, c2 (on Switch s1)",
                       "Clients c3, c4 (on Switch s2)",
                       "Normal Web Browsing (HTTP)",
                       "DNS Queries, NTP sync",
                       "Standard TCP 3-way handshakes"],
                      bg='#FFFFFF', border='#94A3B8')

    # Switches Subcomponent
    draw_subcomponent(28, 4.5, 44, 15.5, "Open vSwitch (OVS) Switching Fabric",
                      ["Access Layer: Switch s1 & Switch s2 (Host Ingress/Egress)",
                       "Core / Aggregation: Switch s3 & Switch s4 (100 Mbps Mesh)",
                       "Flow Tables: Priority-matched packet forwarding rules",
                       "Counters: Packet count, Byte count, Duration, Drop counters",
                       "Default Table-Miss Entry: Forwards unmatched frames to Controller"],
                      bg='#FFFFFF', border='#64748B')

    # Attackers & Target Servers Subcomponent
    draw_subcomponent(74, 4.5, 20, 15.5, "Attackers & Target Infrastructure",
                      ["Attack Nodes: a1-a4 (Botnet cluster)",
                       "12 DDoS Vectors (SYN/UDP/ICMP floods)",
                       "Reflectors: DNS (53), NTP (123), SSDP",
                       "Victim Server: Web Application (10.0.0.10)",
                       "Slowloris & Application Layer Stress"],
                      bg='#FFFFFF', border='#EF4444')

    # ==========================================
    # LAYER 2: SOUTHBOUND PROTOCOL INTERFACE
    # ==========================================
    draw_box(4, 29, 92, 10, c_southbound, c_south_border,
             "2. SOUTHBOUND INTERFACE & PROTOCOL LAYER (OpenFlow 1.3)",
             "TCP control channel (port 6653); TLS is not configured in the current lab")
    
    draw_subcomponent(6, 30.5, 26, 6.5, "Reactive Asynchronous Events",
                      ["OFPPacketIn (Table-miss packet forwarding)",
                       "OFPPortStatus (Link state alterations)"],
                      bg='#FFFBEB', border=c_south_border)

    draw_subcomponent(34, 30.5, 32, 6.5, "High-Frequency Telemetry Polling",
                      ["OFPFlowStatsRequest / OFPFlowStatsReply (10s)",
                       "OFPPortStatsRequest / OFPPortStatsReply (10s)"],
                      bg='#FFFBEB', border=c_south_border)

    draw_subcomponent(68, 30.5, 26, 6.5, "Flow Control & Programming",
                      ["OFPFlowMod (Proactive / Reactive Rules)",
                       "OFPPacketOut (Forward buffered frames)"],
                      bg='#FFFBEB', border=c_south_border)

    # ==========================================
    # LAYER 3: SDN CONTROL PLANE (RYU CONTROLLER)
    # ==========================================
    draw_box(4, 43, 92, 12, c_control, c_control_border,
             "3. SDN CONTROL PLANE LAYER (Ryu Controller Platform)",
             "Implemented learning switch, topology inventory, and periodic raw telemetry collection")

    draw_subcomponent(6, 44.5, 26, 8.5, "L2 Learning Switch & Flow Engine",
                      ["Dynamic MAC-to-Port table learning",
                       "Proactive path computation (s1-s4)",
                       "Idle-timeout flow installation (60s)",
                       "Table-miss rule manager"],
                      bg='#FFFFFF', border='#60A5FA')

    draw_subcomponent(34, 44.5, 32, 8.5, "Topology & State Manager",
                      ["Active datapath registry (dpid)",
                       "Link discovery via LLDP & EventLinkAdd",
                       "Port state & load monitoring",
                       "Controller load & latency proxy"],
                      bg='#FFFFFF', border='#60A5FA')

    draw_subcomponent(68, 44.5, 26, 8.5, "Telemetry Collector Module",
                      ["Threaded periodic polling (_monitor)",
                       "Raw metric aggregation & JSONL serialization",
                       "Flow duration, bytes, packets logging",
                       "Stream output: openflow_telemetry.jsonl"],
                      bg='#FFFFFF', border='#60A5FA')

    # ==========================================
    # LAYER 4: BIG DATA ANALYTICS & FEATURE EXTRACTION
    # ==========================================
    draw_box(4, 59, 92, 13, c_analytics, c_analytics_border,
             "4. BIG DATA INGESTION & FEATURE ENGINEERING ENGINE (PySpark Pipeline)",
             "Proposed raw-telemetry pipeline; current 63-column schema is generated synthetically")

    draw_subcomponent(6, 60.5, 20, 9.5, "Data Transformation",
                      ["Current: Parquet analytics notebooks",
                       "Current: schema checks and plots",
                       "Proposed: JSONL windowing",
                       "Proposed: streaming ingestion"],
                      bg='#FFFFFF', border='#A78BFA')

    draw_subcomponent(28, 60.5, 22, 9.5, "Volumetric & Rate Features",
                      ["packet_rate, byte_rate, flow_rate",
                       "mean_packet_size & std",
                       "inter_arrival_mean_ms & std",
                       "packet_rate_cv, new_flow_rate"],
                      bg='#FFFFFF', border='#A78BFA')

    draw_subcomponent(52, 60.5, 22, 9.5, "Statistical & Entropy Metrics",
                      ["src_ip_entropy, dst_ip_entropy",
                       "src_port_entropy, protocol_entropy",
                       "unique_src_count, unique_dst_count",
                       "active_flow_ratio"],
                      bg='#FFFFFF', border='#A78BFA')

    draw_subcomponent(76, 60.5, 18, 9.5, "SDN Control Telemetry",
                      ["flow_table_occupancy / size",
                       "packet_in_rate & count",
                       "controller_latency_ms",
                       "queue_occupancy & drops"],
                      bg='#FFFFFF', border='#A78BFA')

    # ==========================================
    # LAYER 5: MACHINE LEARNING DETECTION ENGINE (4 ALGORITHMS)
    # ==========================================
    draw_box(4, 76, 64, 16, c_ml, c_ml_border,
             "5. MACHINE LEARNING DDOS DETECTION ENGINE",
             "Offline 4-model evaluation on 13 classes (39,000 windows), stratified 70/15/15 split")

    draw_subcomponent(6, 78.0, 14, 11.5, "Preprocessing Pipeline",
                      ["Anti-Leakage Filter",
                       "Median Imputation",
                       "StandardScaler",
                       "OneHotEncoder",
                       "Held-out Validation"],
                      bg='#FFFFFF', border='#86EFAC')

    draw_subcomponent(21.5, 78.0, 14, 11.5, "Random Forest (Best F1)",
                      ["20 Estimators, d=12",
                       "min_samples_leaf=8",
                       "Acc: 81.59% | F1: 0.809",
                       "Fit Time: 13.28s",
                       "Latency: 0.026 ms"],
                      bg='#F0FDF4', border='#22C55E')

    draw_subcomponent(37, 78.0, 14, 11.5, "Decision Tree (Fast)",
                      ["CART (depth=14)",
                       "min_samples_leaf=5",
                       "Acc: 79.18% | F1: 0.789",
                       "Fit Time: 2.82s",
                       "Latency: 0.007 ms"],
                      bg='#F0FDF4', border='#22C55E')

    draw_subcomponent(52.5, 78.0, 14, 11.5, "KNN & Logistic",
                      ["KNN: k=11, dist",
                       "KNN: 75.16% | F1: 0.748",
                       "LogReg: C=2.0, L2",
                       "LogReg: 80.26% | F1: 0.798",
                       "Offline latency only"],
                      bg='#F0FDF4', border='#22C55E')

    # ==========================================
    # LAYER 6: CLOSED-LOOP MITIGATION & FEEDBACK
    # ==========================================
    draw_box(70, 76, 26, 16, c_mitigation, c_mitigation_border,
             "6. CLOSED-LOOP MITIGATION",
             "Proposed future controller-driven response")

    draw_subcomponent(72, 78.0, 22, 11.5, "Mitigation Actions",
                      ["Not yet implemented",
                       "Proposed: validated FlowMod rules",
                       "Proposed: ingress-port controls",
                       "Proposed: OpenFlow meters",
                       "Requires policy safeguards",
                       "Requires end-to-end testing"],
                      bg='#FEF2F2', border='#F87171')

    # ==========================================
    # CONNECTING ARROWS (INTER-LAYER DATA FLOWS)
    # ==========================================
    arrow_props_up = dict(arrowstyle="->", color="#1E293B", lw=2.2, mutation_scale=16)
    arrow_props_down = dict(arrowstyle="->", color="#DC2626", lw=2.2, mutation_scale=16, linestyle="--")

    # Layer 1 -> Layer 2
    ax.annotate("", xy=(30, 29), xytext=(30, 25), arrowprops=arrow_props_up)
    ax.text(32, 27, "OVS Packet-In & Flow Counter Signaling", fontsize=8, fontweight='semibold', color='#1E293B')

    # Layer 2 -> Layer 3
    ax.annotate("", xy=(30, 43), xytext=(30, 39), arrowprops=arrow_props_up)
    ax.text(32, 41, "OpenFlow 1.3 Event Delivery to Ryu Dispatcher", fontsize=8, fontweight='semibold', color='#1E293B')

    # Layer 3 -> Layer 4
    ax.annotate("", xy=(30, 59), xytext=(30, 55), arrowprops=arrow_props_up)
    ax.text(32, 57, "Raw telemetry JSONL available; pipeline integration proposed", fontsize=7.2, fontweight='semibold', color='#1E293B')

    # Layer 4 -> Layer 5
    ax.annotate("", xy=(30, 76), xytext=(30, 72), arrowprops=arrow_props_up)
    ax.text(32, 74, "Current synthetic 63-column dataset for offline train/test", fontsize=7.2, fontweight='semibold', color='#1E293B')

    # Layer 5 -> Layer 6
    ax.annotate("", xy=(70, 84), xytext=(68, 84), arrowprops=dict(arrowstyle="->", color="#16A34A", lw=2.2, mutation_scale=16))
    ax.text(68.5, 85.5, "Proposed model-to-controller policy path", fontsize=6.8, fontweight='semibold', color='#15803D', ha='center')

    # Layer 6 -> Downward Mitigation Feedback to Control Plane & Data Plane
    ax.annotate("", xy=(85, 43), xytext=(85, 76), arrowprops=arrow_props_down)
    ax.text(86, 50, "Proposed feedback loop:\nValidate policy then install FlowMod\nOptional ingress controls",
            fontsize=8, fontweight='bold', color='#DC2626', va='center')

    # Output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, facecolor=fig.get_facecolor(), bbox_inches='tight')
    plt.close()
    print(f"Architecture diagram successfully generated at: {output_path}")

if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "results/sdn_ddos_system_architecture.png"
    create_architecture_diagram(out)
