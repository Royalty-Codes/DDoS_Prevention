"""Deterministic features from cumulative OpenFlow counter snapshots."""
def compute_window_features(previous, current, seconds):
    seconds = max(float(seconds), 1.0)
    packets = max(int(current['packets']) - int(previous['packets']), 0)
    bytes_ = max(int(current['bytes']) - int(previous['bytes']), 0)
    flows = max(int(current['flows']) - int(previous['flows']), 0)
    syn = max(int(current.get('syn', 0)) - int(previous.get('syn', 0)), 0)
    ack = max(int(current.get('ack', 0)) - int(previous.get('ack', 0)), 0)
    return {
        'window_seconds': seconds, 'packet_count': packets, 'byte_count': bytes_,
        'flow_count': flows, 'packet_rate': packets / seconds,
        'byte_rate': bytes_ / seconds, 'flow_rate': flows / seconds,
        'mean_packet_size': bytes_ / max(packets, 1), 'tcp_syn_count': syn,
        'tcp_ack_count': ack, 'tcp_handshake_completion_ratio': ack / max(syn, 1),
        'flow_table_size': int(current.get('flow_table_size', 0)),
        'packet_in_count': int(current.get('packet_in', 0)),
        'controller_cpu_proxy_pct': min(100.0, 100.0 * int(current.get('packet_in', 0)) / max(int(current.get('flow_table_size', 1)), 1))
    }
