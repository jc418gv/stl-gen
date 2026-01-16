# stl-gen

Repository for small scripts that generate STL files for 3D printing.

Folders:
- `stl-draft/` — temporary outputs and drafts. These are ignored by git (use `.gitkeep` to keep the folder).
- `stl-final/` — move validated/printed STL files here so they are tracked by git.

Setup:
- Install dependencies listed in `requirements.txt`:

  ```bash
  # activate the .venv first, then:
  pip install -r requirements.txt
  ```

Generating STLs:
- Run the script, e.g.:

  ```bash
  python rag-basket.py
  ```

- Draft STLs will be placed into `stl-draft/`. Once a print is validated, move the file to `stl-final/` to keep it in the repo.
