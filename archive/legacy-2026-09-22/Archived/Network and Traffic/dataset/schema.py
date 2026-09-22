"""Canonical flow-window schema shared by lab collection and analytics."""
REQUIRED_COLUMNS = [
    'timestamp_utc', 'experiment_id', 'scenario_id', 'switch_id', 'src_host',
    'dst_host', 'protocol', 'application', 'window_seconds', 'packet_count',
    'byte_count', 'flow_count', 'packet_rate', 'byte_rate', 'flow_rate',
    'mean_packet_size', 'tcp_syn_count', 'tcp_ack_count',
    'tcp_handshake_completion_ratio', 'flow_table_size', 'packet_in_count',
    'controller_cpu_proxy_pct', 'attack_intensity', 'attacker_count',
    'background_traffic_level', 'label', 'attack_family', 'data_source'
]

LABELS = [
    'BENIGN', 'UDP_FLOOD', 'ICMP_FLOOD', 'UDP_AMPLIFICATION_STYLE',
    'SYN_FLOOD', 'PING_OF_DEATH_STYLE', 'SMURF_STYLE', 'HTTP_FLOOD',
    'SLOWLORIS_STYLE', 'LAND_STYLE', 'PACKET_IN_FLOOD_STYLE'
]
