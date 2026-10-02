import os
import shutil
from pathlib import Path

try:
    from pcbdoc_to_pnp import CFBReader, build_rows, write_pnp
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from pcbdoc_to_pnp import CFBReader, build_rows, write_pnp


def convert_pcbdoc_to_pnp(pcbdoc_path: str, output_dir: str = None) -> str:
    pcbdoc_path = Path(pcbdoc_path)
    if not pcbdoc_path.exists():
        raise FileNotFoundError(f"Файл не найден: {pcbdoc_path}")

    if output_dir is None:
        output_dir = pcbdoc_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    ole = CFBReader(pcbdoc_path)
    rows, origin = build_rows(ole)

    out_txt = output_dir / (pcbdoc_path.stem + "_PnP.txt")

    write_pnp(rows, out_txt, source_path=pcbdoc_path)

    return str(out_txt)
