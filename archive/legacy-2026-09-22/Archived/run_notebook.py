import nbformat
from nbclient import NotebookClient

notebook_file = "DDoS_Traffic_Analysis_Plotly.ipynb"

print(f"Reading notebook {notebook_file}...")
with open(notebook_file, "r", encoding="utf-8") as f:
    nb = nbformat.read(f, as_version=4)

client = NotebookClient(nb, timeout=300, kernel_name="python3")
print("Executing notebook cells (this may take ~20-30s to load data and render plots)...")
client.execute()

print("Saving executed notebook with rendered outputs...")
with open(notebook_file, "w", encoding="utf-8") as f:
    nbformat.write(nb, f)

print(f"Notebook successfully executed and saved to {notebook_file}!")
