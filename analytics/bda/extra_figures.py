"""Complete feature-distribution atlas for notebook presentation, using saved data."""
import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .feature_notes import FEATURE_NOTES
from .visuals import BLUE, GOLD, save


def build(run_dir):
    run = Path(run_dir)
    frame = pd.read_parquet(run/'clean_dataset.parquet')
    features = json.loads((run/'feature_contract.json').read_text())['features']
    benign = frame.label.eq('BENIGN')
    for page, start in enumerate(range(0, len(features), 8), 1):
        fig, axes = plt.subplots(2, 4, figsize=(18, 8))
        for ax, feature in zip(axes.flat, features[start:start+8]):
            bins = np.histogram_bin_edges(frame[feature].dropna(), bins=30)
            ax.hist(frame.loc[benign, feature], bins=bins, density=True, alpha=.6, color=BLUE, label='Benign (n=3,000)')
            ax.hist(frame.loc[~benign, feature], bins=bins, density=True, alpha=.45, color=GOLD, label='Attack (n=36,000)')
            ax.set(title=feature, xlabel=FEATURE_NOTES[feature][0], ylabel='Density')
            ax.tick_params(axis='x', labelsize=9)
        axes.flat[0].legend(fontsize=8)
        fig.suptitle(f'All-feature distribution atlas {page}/5 — each group normalized separately; all values retained', y=1.02)
        save(fig, run, f'atlas_{page}')
    fig, ax = plt.subplots(figsize=(15, 7))
    ax.axis('off')
    boxes = [(.03, .65, 'Original Parquet\n39,000 synthetic windows'),
             (.36, .65, 'Spark audit + cleaning\n63 columns → 40 features'),
             (.69, .65, 'Saved stratified split\n70% train / 15% val / 15% test'),
             (.69, .30, 'Training-only Spark pipeline\nMedian → vector → standardize'),
             (.36, .30, '5 Spark + 4 sklearn models\nValidation selects candidates'),
             (.03, .30, 'Frozen test evaluation\nErrors, timing, saved models')]
    for x, y, text in boxes:
        ax.text(x+.13, y+.07, text, ha='center', va='center', fontsize=12,
                bbox={'boxstyle':'round,pad=1', 'facecolor':'#edf3f7', 'edgecolor':BLUE}, transform=ax.transAxes)
    for start, end in [((.29,.72),(.35,.72)),((.62,.72),(.68,.72)),((.82,.60),(.82,.48)),
                       ((.68,.37),(.63,.37)),((.35,.37),(.30,.37))]:
        ax.annotate('', xy=end, xytext=start, xycoords='axes fraction', arrowprops={'arrowstyle':'->','color':BLUE,'lw':2})
    ax.text(.5,.08,'Offline inference: validate schema → reuse preprocessing → class + score → corroborate → policy decision',
            ha='center', fontsize=12, transform=ax.transAxes)
    ax.set_title('What the Big Data Analytics experiment actually executes', fontsize=16, pad=20)
    save(fig, run, '00_pipeline')
    (run/'figure_atlas_provenance.json').write_text(json.dumps({
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'data':'clean_dataset.parquet', 'features':len(features), 'pages':5,
        'notes':'Descriptive full-dataset EDA; not feature or hyperparameter selection.'}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    import sys
    build(sys.argv[1])
