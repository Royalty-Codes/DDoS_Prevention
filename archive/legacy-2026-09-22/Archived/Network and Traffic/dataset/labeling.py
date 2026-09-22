"""Ground-truth labels come from the local experiment schedule."""
from .schema import LABELS

def label_for_window(scenario):
    label = scenario['label']
    if label not in LABELS:
        raise ValueError(f'Unknown label: {label}')
    return label, scenario['attack_family']
