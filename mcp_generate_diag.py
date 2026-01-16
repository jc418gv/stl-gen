import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'cadquery-mcp-server'))
import server

prompt = '''Create a robust standalone Python diagnostic script for a rag-basket CadQuery model.
The script should:
- Define a function `make_rag_basket(...)` with parameters for width, depth, height, wall_thickness, slot_width, slot_depth_ratio, lattice params.
- Recreate the basket step-by-step (box, shell, slot, lattice) with a function `run_steps(output_dir, force=False)` that exports an STL at each step using `cq.exporters.export` to files `step1_base.stl`, `step2_shell.stl`, `step3_slot.stl`, `step4_lattice.stl`.
- Use script-local `Path(__file__).parent / 'stl-draft'` for outputs (idempotent: skip export if file exists unless `force=True`).
- Emit clear print/log messages and return non-zero exit codes on failures.
- End the file with a simple `if __name__ == '__main__'` CLI that accepts `--force`.
'''

print('Calling server.generate_cad_query...')
res = server.generate_cad_query(prompt, parameters='')
print('Status:', res.get('status'))
code = res.get('generated_code') or ''
with open('diagnose_generated.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Wrote diagnose_generated.py (length:', len(code), ')')
