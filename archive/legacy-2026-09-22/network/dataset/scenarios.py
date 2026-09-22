"""Balanced, bounded scenario definitions for the isolated SDN lab."""

SCENARIOS = [
    {"label": "BENIGN", "family": "BENIGN", "protocol": "TCP", "application": "HTTP", "pps": (20, 180), "flows": (5, 40), "packet_size": (400, 1200), "syn_ratio": (.05, .2), "ack_ratio": (.7, .99), "intensity": 0.0},
    {"label": "UDP_FLOOD", "family": "VOLUMETRIC", "protocol": "UDP", "application": "UDP", "pps": (800, 5000), "flows": (30, 250), "packet_size": (256, 900), "syn_ratio": (0, 0), "ack_ratio": (0, 0), "intensity": .7},
    {"label": "ICMP_FLOOD", "family": "VOLUMETRIC", "protocol": "ICMP", "application": "ICMP", "pps": (600, 4000), "flows": (15, 120), "packet_size": (64, 1200), "syn_ratio": (0, 0), "ack_ratio": (0, 0), "intensity": .7},
    {"label": "TCP_SYN_FLOOD", "family": "PROTOCOL_TRANSPORT", "protocol": "TCP", "application": "TCP", "pps": (500, 4000), "flows": (150, 900), "packet_size": (40, 100), "syn_ratio": (.7, .99), "ack_ratio": (.01, .15), "intensity": .8},
    {"label": "TCP_ACK_FLOOD", "family": "PROTOCOL_TRANSPORT", "protocol": "TCP", "application": "TCP", "pps": (500, 3500), "flows": (100, 700), "packet_size": (40, 100), "syn_ratio": (.01, .08), "ack_ratio": (.75, .99), "intensity": .75},
    {"label": "TCP_RST_FLOOD", "family": "PROTOCOL_TRANSPORT", "protocol": "TCP", "application": "TCP", "pps": (450, 3200), "flows": (100, 650), "packet_size": (40, 100), "syn_ratio": (.01, .08), "ack_ratio": (.01, .1), "intensity": .75},
    {"label": "HTTP_FLOOD", "family": "APPLICATION_LAYER", "protocol": "TCP", "application": "HTTP", "pps": (300, 2500), "flows": (80, 500), "packet_size": (300, 1400), "syn_ratio": (.1, .35), "ack_ratio": (.4, .9), "intensity": .7},
    {"label": "SLOW_HTTP", "family": "APPLICATION_LAYER", "protocol": "TCP", "application": "HTTP", "pps": (10, 120), "flows": (200, 1200), "packet_size": (50, 400), "syn_ratio": (.2, .6), "ack_ratio": (.01, .25), "intensity": .55},
    {"label": "DNS_AMPLIFICATION", "family": "REFLECTION_AMPLIFICATION", "protocol": "UDP", "application": "DNS", "pps": (700, 4500), "flows": (20, 150), "packet_size": (700, 1400), "syn_ratio": (0, 0), "ack_ratio": (0, 0), "intensity": .85},
    {"label": "NTP_AMPLIFICATION", "family": "REFLECTION_AMPLIFICATION", "protocol": "UDP", "application": "NTP", "pps": (700, 4500), "flows": (20, 150), "packet_size": (500, 1200), "syn_ratio": (0, 0), "ack_ratio": (0, 0), "intensity": .85},
    {"label": "SSDP_AMPLIFICATION", "family": "REFLECTION_AMPLIFICATION", "protocol": "UDP", "application": "SSDP", "pps": (600, 4000), "flows": (20, 180), "packet_size": (400, 1500), "syn_ratio": (0, 0), "ack_ratio": (0, 0), "intensity": .8},
    {"label": "UDP_AMPLIFICATION", "family": "REFLECTION_AMPLIFICATION", "protocol": "UDP", "application": "UDP", "pps": (600, 4200), "flows": (20, 200), "packet_size": (500, 1500), "syn_ratio": (0, 0), "ack_ratio": (0, 0), "intensity": .8},
    {"label": "MIXED_DDOS", "family": "MULTI_VECTOR", "protocol": "MIXED", "application": "MIXED", "pps": (1000, 6000), "flows": (150, 1000), "packet_size": (64, 1400), "syn_ratio": (.2, .8), "ack_ratio": (.05, .7), "intensity": .95},
]

LABELS = [scenario["label"] for scenario in SCENARIOS]