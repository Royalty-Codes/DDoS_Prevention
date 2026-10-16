"""Static, portable notebook figures from measured experiment artifacts."""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import confusion_matrix, precision_recall_curve, roc_curve

BLUE = '#245b85'
GOLD = '#c98625'
PINK = '#a44770'
COLORS = [BLUE, GOLD, '#65804c', PINK, '#61778b', '#965a31', '#644d80', '#3e7c78', '#777044']
sns.set_theme(style='whitegrid', font_scale=1.05)
plt.rcParams.update({'figure.dpi': 110, 'savefig.dpi': 160, 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.titleweight': 'bold'})


def save(fig, out, name):
    fig.tight_layout()
    fig.savefig(Path(out) / 'figures' / f'{name}.png', bbox_inches='tight', facecolor='white')
    plt.close(fig)


def dataset_figures(frame, features, parts, timings, out):
    counts = frame.label.value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.barh(counts.index, counts.values, color=BLUE)
    ax.set(xlabel='Synthetic observation windows', title=f'Class distribution: {len(frame):,} windows, {len(counts)} classes')
    for i, value in enumerate(counts):
        ax.text(value + 25, i, f'{value:,}', va='center')
    ax.set_xlim(0, counts.max() * 1.17)
    save(fig, out, '01_class_distribution')

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    for ax, column in zip(axes, ['attack_family', 'protocol', 'application']):
        value = frame[column].value_counts().sort_values()
        ax.barh(value.index, value.values, color=BLUE)
        ax.set(xlabel='Windows', title=column.replace('_', ' ').title())
    fig.suptitle('Scenario composition: synthetic context fields are excluded from modeling', y=1.03)
    save(fig, out, '02_context_distribution')

    fig, ax = plt.subplots(figsize=(12, 4))
    sequence = frame.sort_values('window_sequence')
    ax.scatter(sequence.window_sequence, pd.Categorical(sequence.label, categories=counts.index).codes,
               s=2, color=BLUE)
    ax.set(yticks=range(len(counts)), yticklabels=counts.index, xlabel='Generator sequence (excluded feature)',
           title='Generation-order shortcut: each class occupies its own contiguous time block')
    save(fig, out, '03_time_leakage')

    fig, axes = plt.subplots(2, 3, figsize=(17, 10))
    for ax, column in zip(axes.flat, ['packet_rate', 'mean_packet_size', 'flow_rate', 'tcp_syn_ratio',
                                     'controller_latency_ms', 'flow_table_occupancy']):
        sns.boxplot(data=frame, y='label', x=column, order=counts.index, color='#b9d0df',
                    showfliers=False, ax=ax)
        ax.set(ylabel='', title=column)
        if column in ['packet_rate', 'flow_rate']:
            ax.set_xscale('log')
    fig.suptitle('Class behavior distributions; boxes show IQR, whiskers 1.5 IQR; outlier markers hidden', y=1.02)
    save(fig, out, '04_behavior_boxplots')

    columns = ['packet_rate', 'byte_rate', 'flow_rate', 'mean_packet_size', 'tcp_syn_ratio',
               'tcp_ack_ratio', 'packet_in_rate', 'flow_table_occupancy', 'controller_latency_ms',
               'queue_occupancy_ratio', 'src_ip_entropy', 'flow_duration_mean_s']
    fig, ax = plt.subplots(figsize=(11, 9))
    sns.heatmap(parts['train'][columns].corr(method='spearman'), cmap='vlag', vmin=-1, vmax=1,
                center=0, square=True, ax=ax)
    ax.set_title('Training-only Spearman correlation: derived counters and rates are redundant')
    save(fig, out, '05_correlation')

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for label, color in [('BENIGN', BLUE), ('SLOW_HTTP', GOLD), ('UDP_FLOOD', PINK)]:
        group = frame[frame.label == label].sample(n=min(400, (frame.label == label).sum()), random_state=42)
        axes[0].scatter(group.packet_rate, group.flow_rate, s=12, alpha=.55, label=label, color=color)
        axes[1].hist(group.packet_rate, bins=30, alpha=.4, label=label, color=color)
    axes[0].set(xscale='log', yscale='log', xlabel='Packets/s', ylabel='Flows/s', title='Slow HTTP: low packet volume can hide many flows')
    axes[1].set(xlabel='Packets/s', ylabel='Sampled windows', title='Selected-class rate overlap (400 windows/class)')
    for ax in axes:
        ax.legend(fontsize=9)
    save(fig, out, '06_overlap_scatter')

    count_table = pd.DataFrame({name: part.label.value_counts() for name, part in parts.items()}).loc[counts.index]
    count_table.to_csv(Path(out) / 'split_counts.csv')
    fig, ax = plt.subplots(figsize=(12, 6))
    count_table.plot.barh(stacked=True, color=[BLUE, GOLD, '#8a9caa'], ax=ax)
    ax.set(xlabel='Windows', title='Same stratified 70% / 15% / 15% split for all nine algorithms', ylabel='')
    save(fig, out, '07_split_counts')

    fig, ax = plt.subplots(figsize=(9, 4))
    sns.boxplot(data=timings, x='engine', y='seconds', color='#b9d0df', ax=ax)
    sns.stripplot(data=timings, x='engine', y='seconds', color=BLUE, size=7, ax=ax)
    ax.set(xlabel='', ylabel='Wall-clock seconds (completed action)',
           title='Parquet read + per-class count/mean: 3 trials, startup excluded')
    save(fig, out, '08_engine_benchmark')

    fig, axes = plt.subplots(1, 2, figsize=(13, 4))
    missing = frame.isna().sum().sort_values(ascending=False).head(12)
    axes[0].barh(missing.index, missing.values, color=BLUE)
    axes[0].set(xlabel='Null cells', title='Missing-value audit (12 columns shown)')
    if missing.max() == 0:
        axes[0].text(.5, .5, 'No missing values in any column', transform=axes[0].transAxes, ha='center', bbox={'facecolor': 'white'})
    axes[1].scatter(frame.flow_table_capacity, frame.flow_table_size, s=4, alpha=.08, color=BLUE)
    axes[1].plot([0, 2000], [0, 2000], color=GOLD, linestyle='--', label='Size = capacity')
    axes[1].set(xlabel='Reported capacity (entries)', ylabel='Reported size (entries)', title='Synthetic inconsistency: table sizes may exceed capacity')
    axes[1].legend()
    save(fig, out, '09_data_quality')


def result_figures(metrics, classes, predictions, fitted, labels, parts, features, arrays, winner, out):
    names = metrics.model.tolist()
    fig, ax = plt.subplots(figsize=(12, 7))
    y = np.arange(len(metrics))
    ax.barh(y - .18, metrics.validation_macro_f1, height=.35, color=BLUE, label='Validation (selection)')
    ax.barh(y + .18, metrics.f1_macro, height=.35, color=GOLD, label='Test (reporting)')
    ax.errorbar(metrics.f1_macro, y + .18,
                xerr=[np.maximum(0, metrics.f1_macro - metrics.f1_ci_low), np.maximum(0, metrics.f1_ci_high - metrics.f1_macro)],
                fmt='none', ecolor='#333333', capsize=3)
    ax.set(yticks=y, yticklabels=names, xlim=(0, 1.04), xlabel='Macro F1',
           title=f'Nine-model comparison; validation-selected model: {winner}')
    ax.legend()
    save(fig, out, '10_model_comparison')

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    axes[0].barh(names, metrics.fit_seconds, color=BLUE)
    axes[0].set(xlabel='Selected candidate fit time (seconds)', title='Fit wall time; preprocessing and discarded candidates excluded')
    axes[1].barh(names, metrics.amortized_prediction_ms, color=GOLD)
    axes[1].set(xlabel='Median batch ms / row', title='Amortized batch prediction; includes Spark collection')
    save(fig, out, '11_runtime')

    fig, ax = plt.subplots(figsize=(15, 7))
    recalls = classes.pivot(index='class', columns='model', values='recall').loc[labels, names]
    sns.heatmap(recalls, cmap='Blues', vmin=0, vmax=1, annot=True, fmt='.2f', ax=ax)
    ax.set(title='Per-class recall: which attacks are confused?', xlabel='', ylabel='Actual class')
    save(fig, out, '12_recall_heatmap')

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    truth = parts['test'].target.to_numpy() != labels.index('BENIGN')
    for i, name in enumerate(names):
        score = predictions[name]['score']
        fpr, tpr, _ = roc_curve(truth, score)
        precision, recall, _ = precision_recall_curve(truth, score)
        axes[0].plot(fpr, tpr, label=name, color=COLORS[i], linestyle='-' if i < 5 else '--')
        axes[1].plot(recall, precision, color=COLORS[i], linestyle='-' if i < 5 else '--')
    axes[0].plot([0, 1], [0, 1], ':', color='#555555')
    axes[1].axhline(truth.mean(), color='#555555', linestyle=':', label='Attack prevalence')
    axes[0].set(xlabel='Benign false-positive rate', ylabel='Attack recall', title='Attack-vs-benign ROC (test)')
    axes[1].set(xlabel='Attack recall', ylabel='Attack precision', title=f'Attack PR (test prevalence {truth.mean():.1%})')
    axes[0].legend(fontsize=8, loc='lower right')
    axes[1].legend(fontsize=8)
    save(fig, out, '13_roc_pr')

    fig, ax = plt.subplots(figsize=(10, 6))
    for i, row in metrics.reset_index(drop=True).iterrows():
        ax.scatter(row.amortized_prediction_ms, row.f1_macro, s=80, color=COLORS[i])
        ax.annotate(row.model, (row.amortized_prediction_ms, row.f1_macro), xytext=(5, 5), textcoords='offset points', fontsize=8)
    ax.set(xscale='log', xlabel='Amortized batch prediction milliseconds / row (log scale)', ylabel='Test macro F1',
           ylim=(0, 1.05), title='Accuracy/runtime tradeoff on this machine; not an end-to-end SDN latency benchmark')
    save(fig, out, '14_tradeoff')

    for name in names:
        slug = name.lower().replace(' ', '_')
        table = predictions[name]['table']
        matrix = confusion_matrix(table.actual, table.predicted, labels=labels)
        normalized = matrix / matrix.sum(axis=1, keepdims=True)
        fig, ax = plt.subplots(figsize=(11, 9))
        sns.heatmap(normalized, xticklabels=labels, yticklabels=labels, cmap='Blues', vmin=0, vmax=1,
                    annot=True, fmt='.2f', annot_kws={'fontsize': 7}, ax=ax)
        ax.set(title=f'{name}: test row-normalized confusion matrix (450 windows/class)',
               xlabel='Predicted class', ylabel='Actual class')
        save(fig, out, 'cm_' + slug)
        pd.DataFrame(matrix, index=labels, columns=labels).to_csv(Path(out) / ('confusion_' + slug + '.csv'))

    importance_rows = []
    for name in ['Random Forest', 'Extra Trees']:
        model = fitted[name]['model']
        importance = model.featureImportances.toArray() if name == 'Random Forest' else model.feature_importances_
        for feature, value in zip(features, importance):
            importance_rows.append({'model': name, 'feature': feature, 'importance': value})
    importance_table = pd.DataFrame(importance_rows)
    importance_table.to_csv(Path(out) / 'feature_importance.csv', index=False)
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    for ax, name in zip(axes, ['Random Forest', 'Extra Trees']):
        data = importance_table[importance_table.model == name].nlargest(15, 'importance').sort_values('importance')
        ax.barh(data.feature, data.importance, color=BLUE)
        ax.set(xlabel='Impurity-based importance', title=f'{name}: top 15 features')
    save(fig, out, '15_feature_importance')

    # Reliability is descriptive: no calibrator is fitted on test data.
    fig, ax = plt.subplots(figsize=(8, 5))
    prob = predictions[winner]['proba']
    if prob is not None:
        table = predictions[winner]['table'].copy()
        table['confidence'] = prob.max(axis=1)
        table['correct'] = table.actual == table.predicted
        table['bin'] = pd.cut(table.confidence, np.linspace(0, 1, 11), include_lowest=True)
        reliability = table.groupby('bin', observed=True).agg(confidence=('confidence', 'mean'), accuracy=('correct', 'mean'), windows=('correct', 'size'))
        ax.plot(reliability.confidence, reliability.accuracy, marker='o', color=BLUE)
        reliability.to_csv(Path(out) / 'reliability.csv')
    else:
        ax.text(.5, .5, 'Selected SVM has margins, not probabilities.\nNo probability calibration claim.', ha='center', transform=ax.transAxes)
    ax.plot([0, 1], [0, 1], '--', color='#777777')
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel='Mean top-class confidence', ylabel='Observed accuracy', title=f'Descriptive confidence check: {winner}')
    save(fig, out, '16_reliability')

    scenarios = pd.read_csv(Path(out) / 'prevalence_scenarios.csv')
    selected = scenarios[scenarios.model == winner]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar([f'{p:.1%}' for p in selected.assumed_attack_prevalence], selected.expected_alert_precision, color=BLUE)
    ax.set(ylim=(0, 1.05), xlabel='Assumed deployment attack prevalence', ylabel='Expected alert precision',
           title='Hypothetical prevalence shift, assuming unchanged class-conditional error rates')
    save(fig, out, '17_prevalence')

    winner_table = predictions[winner]['table']
    wrong = winner_table[winner_table.actual != winner_table.predicted]
    pairs = wrong.groupby(['actual', 'predicted']).size().sort_values(ascending=False).head(12)
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.barh([f'{actual} → {predicted}' for actual, predicted in pairs.index][::-1], pairs.values[::-1], color=PINK)
    ax.set(xlabel='Test errors (windows)', title=f'{winner}: most frequent confusion pairs')
    save(fig, out, '18_error_pairs')
