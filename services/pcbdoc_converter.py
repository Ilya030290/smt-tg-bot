import os
import sys

_SERVICES_DIR = os.path.dirname(os.path.abspath(__file__))
if _SERVICES_DIR not in sys.path:
    sys.path.insert(0, _SERVICES_DIR)
    
from pcbdoc_to_pnp import CFBReader, build_rows, write_pnp

def convert_pcbdoc_to_pnp(pcbdoc_path: str, output_dir: str = None) -> str:
    
    if not os.path.exists(pcbdoc_path):
        raise FileNotFoundError(f"Файл не найден: {pcbdoc_path}")

    if output_dir is None:
        output_dir = os.path.dirname(pcbdoc_path)
    else:
        os.makedirs(output_dir, exist_ok=True)

    ole = CFBReader(pcbdoc_path)
    rows, origin = build_rows(ole)

    base_name = os.path.splitext(os.path.basename(pcbdoc_path))[0]
    out_txt = os.path.join(output_dir, base_name + "_PnP.txt")

    write_pnp(rows, out_txt, source_path=pcbdoc_path)

    return str(out_txt)
