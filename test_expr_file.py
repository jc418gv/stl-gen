# Test expression wrapper that imports make_rag_basket and shows the Workplane
from pathlib import Path
import sys
# `show_object` is provided by CQGI runtime; do NOT import it here.
# No sys.path modification; CQGI exposes the script's context for imports
from rag_basket import make_rag_basket
show_object(make_rag_basket())
