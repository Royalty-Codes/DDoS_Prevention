"""Execute saved-artifact companion notebooks and export portable HTML."""
import json
import os
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter

ROOT = Path(__file__).resolve().parents[1]
os.environ['BDA_ROOT'] = str(ROOT)
os.environ['BDA_RUN_ID'] = 'lab2-synthetic-seed42'
os.environ['BDA_RETRAIN'] = '0'
os.environ['OMP_NUM_THREADS'] = '4'
os.environ['OPENBLAS_NUM_THREADS'] = '4'


def execute_all():
    from bda.extra_figures import build
    build(ROOT/'artifacts/bda/lab2-synthetic-seed42')
    paths = [ROOT/'analytics/05_lab_evaluation_2_nine_models.ipynb',
             *sorted((ROOT/'analytics').glob('*_LA2.ipynb'))]
    statuses = []
    for path in paths:
        print('Executing', path.name, flush=True)
        notebook = nbformat.read(path, as_version=4)
        client = NotebookClient(notebook, timeout=600, kernel_name='python3',
                                resources={'metadata': {'path': str(ROOT)}})
        client.execute()
        nbformat.validate(notebook)
        nbformat.write(notebook, path)
        errors = [output for cell in notebook.cells if cell.cell_type == 'code'
                  for output in cell.get('outputs', []) if output.output_type == 'error']
        assert not errors
        html, _ = HTMLExporter(template_name='lab').from_notebook_node(notebook)
        path.with_suffix('.html').write_text(html, encoding='utf-8')
        image_count = sum('image/png' in output.get('data', {}) for cell in notebook.cells
                          for output in cell.get('outputs', []))
        statuses.append({'notebook': path.name, 'cells': len(notebook.cells),
                         'rendered_image_outputs': image_count, 'errors': len(errors)})
        print('Completed', statuses[-1], flush=True)
    target = ROOT/'artifacts/bda/lab2-synthetic-seed42/notebook_validation.json'
    target.write_text(json.dumps(statuses, indent=2), encoding='utf-8')


if __name__ == '__main__':
    execute_all()
