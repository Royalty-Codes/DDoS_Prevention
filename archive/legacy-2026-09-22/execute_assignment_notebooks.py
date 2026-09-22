"""Execute and save the three assignment notebooks against the final dataset."""

from pathlib import Path

import nbformat
from nbclient import NotebookClient


ROOT = Path(__file__).resolve().parent
NOTEBOOKS = [
    ROOT / "24059_Roydon_LA1.ipynb",
    ROOT / "24063_Satya_LA1.ipynb",
    ROOT / "24076_Prithvi_LA1.ipynb",
]


for notebook_path in NOTEBOOKS:
    notebook = nbformat.read(notebook_path, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=600,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT)}},
    )
    client.execute()
    nbformat.write(notebook, notebook_path)
    figure_count = sum(
        "display(fig)" in cell.source
        for cell in notebook.cells
        if cell.cell_type == "code"
    )
    output_count = sum(
        bool(cell.get("outputs"))
        for cell in notebook.cells
        if cell.cell_type == "code"
    )
    print(f"{notebook_path.name}: executed, {figure_count} figure cells, {output_count} output cells")
