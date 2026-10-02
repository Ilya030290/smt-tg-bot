from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

CFB_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
FREE = 0xFFFFFFFF
END = 0xFFFFFFFE

RAW_TO_MM = 0.0254 / 10000.0


def read_u32(b, off): return struct.unpack_from("<I", b, off)[0]
def read_i32(b, off): return struct.unpack_from("<i", b, off)[0]
def read_u16(b, off): return struct.unpack_from("<H", b, off)[0]
def read_i16(b, off): return struct.unpack_from("<h", b, off)[0]


class CFBReader:
    """Minimal reader for the regular streams used by Altium PcbDoc."""
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        if self.data[:8] != CFB_MAGIC:
            raise ValueError("Not an OLE Compound File")
        self.sector_size = 1 << read_u16(self.data, 30)
        self.mini_sector_size = 1 << read_u16(self.data, 32)
        self.mini_cutoff = read_u32(self.data, 56)
        self.first_mini_fat_sector = read_u32(self.data, 60)
        self.mini_fat_sector_count = read_u32(self.data, 64)
        self.fat = self._read_fat()
        self.entries = self._read_directory()
        self.paths = self._build_paths()
        self.mini_fat = self._read_mini_fat()
        self.mini_stream = self._read_mini_stream()

    def _sector(self, n: int) -> bytes:
        start = 512 + n * self.sector_size
        return self.data[start:start + self.sector_size]

    def _chain(self, start: int, table=None):
        table = self.fat if table is None else table
        out, seen = [], set()
        cur = start
        while cur not in (FREE, END) and cur < len(table):
            if cur in seen:
                raise ValueError("Corrupt CFB sector chain")
            seen.add(cur)
            out.append(cur)
            cur = table[cur]
        return out

    def _read_fat(self):
        fat_sectors = []
        for i in range(109):
            s = read_u32(self.data, 76 + i * 4)
            if s != FREE:
                fat_sectors.append(s)

        first_difat = read_u32(self.data, 68)
        difat_count = read_u32(self.data, 72)
        cur = first_difat
        for _ in range(difat_count):
            if cur in (FREE, END):
                break
            sec = self._sector(cur)
            for i in range(self.sector_size // 4 - 1):
                s = read_u32(sec, i * 4)
                if s != FREE:
                    fat_sectors.append(s)
            cur = read_u32(sec, self.sector_size - 4)

        fat = []
        for s in fat_sectors:
            fat.extend(struct.unpack_from(f"<{self.sector_size // 4}I", self._sector(s)))
        return fat

    def _read_directory(self):
        first_dir = read_u32(self.data, 48)
        raw = b"".join(self._sector(s) for s in self._chain(first_dir))
        entries = []
        for idx in range(0, len(raw), 128):
            d = raw[idx:idx + 128]
            if len(d) < 128:
                break
            nlen = read_u16(d, 64)
            name = d[:max(0, nlen - 2)].decode("utf-16le", "replace") if nlen >= 2 else ""
            entries.append({
                "id": idx // 128,
                "name": name,
                "type": d[66],
                "left": read_u32(d, 68),
                "right": read_u32(d, 72),
                "child": read_u32(d, 76),
                "start": read_u32(d, 116),
                "size": struct.unpack_from("<Q", d, 120)[0],
            })
        return entries

    def _build_paths(self):
        paths = {}

        def walk_siblings(root_id):
            if root_id in (FREE, END) or root_id >= len(self.entries):
                return []
            e = self.entries[root_id]
            return walk_siblings(e["left"]) + [root_id] + walk_siblings(e["right"])

        def walk_storage(storage_id, prefix=""):
            e = self.entries[storage_id]
            children = walk_siblings(e["child"])
            for cid in children:
                ce = self.entries[cid]
                name = ce["name"]
                full = f"{prefix}/{name}" if prefix else name
                paths[full] = cid
                if ce["type"] == 1:
                    walk_storage(cid, full)

        root = self.entries[0]
        walk_storage(root["id"])
        return paths

    def _read_mini_fat(self):
        """Read the MiniFAT sector chain into a normal FAT-like table."""
        if self.mini_fat_sector_count == 0 or self.first_mini_fat_sector in (FREE, END):
            return []
        raw = b"".join(
            self._sector(s) for s in
            self._chain(self.first_mini_fat_sector)[:self.mini_fat_sector_count]
        )
        count = len(raw) // 4
        return list(struct.unpack_from(f"<{count}I", raw)) if count else []

    def _read_mini_stream(self):
        """Read the root storage's Mini Stream (the container for < cutoff streams)."""
        if not self.entries:
            return b""
        root = self.entries[0]
        size = root["size"]
        if size == 0 or root["start"] in (FREE, END):
            return b""
        return b"".join(self._sector(s) for s in self._chain(root["start"]))[:size]

    def _read_mini_stream_data(self, start_sector, size):
        if size == 0:
            return b""
        if not self.mini_fat:
            raise ValueError("MiniFAT is missing but a mini-stream was requested")
        chain = self._chain(start_sector, self.mini_fat)
        chunks = []
        for mini_sector in chain:
            start = mini_sector * self.mini_sector_size
            end = start + self.mini_sector_size
            if end > len(self.mini_stream):
                raise ValueError("Mini-stream sector points outside the root Mini Stream")
            chunks.append(self.mini_stream[start:end])
        return b"".join(chunks)[:size]

    def read_stream(self, path: str) -> bytes:
        if path not in self.paths:
            raise KeyError(path)
        e = self.entries[self.paths[path]]
        size = e["size"]
        if size == 0:
            return b""
        if size < self.mini_cutoff:
            return self._read_mini_stream_data(e["start"], size)
        return b"".join(self._sector(s) for s in self._chain(e["start"]))[:size]


def parse_kv_records(data: bytes):
    records = []
    pos = 0
    while pos + 4 <= len(data):
        n = read_u32(data, pos)
        pos += 4
        if n == 0 or pos + n > len(data):
            raise ValueError(f"Invalid property record length at {pos - 4}: {n}")
        text = data[pos:pos + n].decode("utf-8", "replace")
        pos += n
        kv = dict(re.findall(r"\|([^=|]+)=([^|]*)", text))
        records.append(kv)
    if pos != len(data):
        raise ValueError("Property stream has trailing bytes")
    return records


def parse_components(data: bytes):
    return parse_kv_records(data)


def parse_pads(data: bytes):
    pads = []
    pos = 0
    while pos < len(data):
        if data[pos] != 2:
            raise ValueError(f"Pads6: unexpected record type 0x{data[pos]:02X} at {pos}")
        start = pos
        pos += 1
        lengths = []
        for _ in range(6):
            if pos + 4 > len(data):
                raise ValueError("Pads6: truncated subrecord length")
            n = read_u32(data, pos)
            lengths.append(n)
            pos += 4 + n
        starts_4 = start + 1
        for i in range(4):
            starts_4 += 4 + lengths[i]
        starts_4 += 4
        p = starts_4 - 23
        if p + 84 > len(data):
            raise ValueError("Pads6: truncated pad payload")
        name_data = data[start + 5:start + 5 + lengths[0]]
        name_len = name_data[0] if name_data else 0
        name = name_data[1:1 + name_len].decode("utf-8", "replace")
        pads.append({
            "name": name,
            "component": read_i16(data, p + 30),
            "x": read_i32(data, p + 36),
            "y": read_i32(data, p + 40),
        })
    return pads


def parse_texts(data: bytes):
    texts = []
    pos = 0
    while pos < len(data):
        if data[pos] != 5:
            raise ValueError(f"Texts6: unexpected record type 0x{data[pos]:02X} at {pos}")
        pos += 1
        n1 = read_u32(data, pos); pos += 4
        d = data[pos:pos + n1]; pos += n1
        if len(d) < 42:
            raise ValueError("Texts6: short properties subrecord")
        component = read_u16(d, 7)
        is_comment = bool(d[40])
        is_designator = bool(d[41])

        if pos + 4 > len(data):
            raise ValueError("Texts6: missing string subrecord")
        n2 = read_u32(data, pos); pos += 4
        sdata = data[pos:pos + n2]; pos += n2
        if not sdata:
            text = ""
        else:
            n = sdata[0]
            text = sdata[1:1 + n].decode("utf-8", "replace")
        texts.append({
            "component": component,
            "comment": text if is_comment else None,
            "designator": text if is_designator else None,
        })
    return texts


def decode_description(kv):
    unicode_value = kv.get("UNICODE__SOURCEDESCRIPTION", "")
    if unicode_value:
        try:
            return "".join(chr(int(x)) for x in unicode_value.split(",") if x != "")
        except ValueError:
            pass
    return kv.get("SOURCEDESCRIPTION", "")


def build_rows(ole: CFBReader):
    components = parse_components(ole.read_stream("Components6/Data"))
    pads = parse_pads(ole.read_stream("Pads6/Data"))
    texts = parse_texts(ole.read_stream("Texts6/Data"))

    comments = {}
    for t in texts:
        if t["comment"] is not None:
            comments[t["component"]] = t["comment"]

    pads_by_component = {}
    for pad in pads:
        pads_by_component.setdefault(pad["component"], []).append(pad)

    board = parse_kv_records(ole.read_stream("Board6/Data"))[0]
    origin_x = float(board["ORIGINX"].replace("mil", "")) * 0.0254
    origin_y = float(board["ORIGINY"].replace("mil", "")) * 0.0254

    rows = []
    for idx, comp in enumerate(components):
        cpads = pads_by_component.get(idx, [])
        if not cpads:
            raise ValueError(f"Component {idx} ({comp.get('SOURCEDESIGNATOR')}) has no pads")
        xmin = min(p["x"] for p in cpads)
        xmax = max(p["x"] for p in cpads)
        ymin = min(p["y"] for p in cpads)
        ymax = max(p["y"] for p in cpads)
        center_x = ((xmin + xmax) / 2) * RAW_TO_MM - origin_x
        center_y = ((ymin + ymax) / 2) * RAW_TO_MM - origin_y
        layer = comp.get("LAYER", "TOP").upper()
        layer = "TopLayer" if layer == "TOP" else "BottomLayer" if layer == "BOTTOM" else layer
        rows.append({
            "Designator": comp.get("SOURCEDESIGNATOR", ""),
            "Comment": comments.get(idx, ""),
            "Layer": layer,
            "Footprint": comp.get("PATTERN", ""),
            "Center-X(mm)": center_x,
            "Center-Y(mm)": center_y,
            "Rotation": float(comp.get("ROTATION", "0")),
            "Description": decode_description(comp),
        })
    return rows, (origin_x, origin_y)


def write_pnp(rows, output_path, source_path=None, export_dt=None):

    from datetime import datetime

    export_dt = export_dt or datetime.now()
    source_path = str(source_path) if source_path is not None else ""
    separator = "=" * 120

    def display_comment(value):
        value = str(value or "")
        return f'"{value}"' if any(ch.isspace() for ch in value) else value

    def display_description(value):
        value = str(value or "")
        return f'"{value}"' if (not value or any(ch.isspace() for ch in value)) else value

    display_comments = [display_comment(r["Comment"]) for r in rows]
    display_descriptions = [display_description(r["Description"]) for r in rows]
    footprints = [str(r["Footprint"] or "") for r in rows]
    layers = [str(r["Layer"] or "") for r in rows]

    designator_w = 11
    comment_w = max([len(x) for x in display_comments] + [len("Comment")]) + 1
    layer_w = max([len(x) for x in layers] + [len("Layer")]) + 1
    layer_w = max(layer_w, 9)
    footprint_w = max([len(x) for x in footprints] + [len("Footprint")]) + 1

    x_values = [f'{r["Center-X(mm)"]:.4f}' for r in rows]
    y_values = [f'{r["Center-Y(mm)"]:.4f}' for r in rows]
    rotation_values = [f'{r["Rotation"]:.0f}' for r in rows]
    x_w = max([len(x) for x in x_values] + [len("Center-X(mm)")]) + 1
    y_w = max([len(y) for y in y_values] + [len("Center-Y(mm)")]) + 1
    rotation_w = max([len(x) for x in rotation_values] + [len("Rotation")]) + 1

    header = (
        f'{"Designator":<{designator_w}}'
        f'{"Comment":<{comment_w}}'
        f'{"Layer":<{layer_w}}'
        f'{"Footprint":<{footprint_w}}'
        f'{"Center-X(mm)":<{x_w}}'
        f'{"Center-Y(mm)":<{y_w}}'
        f'{"Rotation":<{rotation_w}}'
        'Description'
    )

    lines = [
        "Altium Designer Pick and Place Locations",
        source_path,
        "",
        separator,
        "File Design Information:",
        "",
        f"Date:       {export_dt:%d.%m.%y}",
        f"Time:       {export_dt:%H:%M}",
        "Revision:   Not in VersionControl",
        "Variant:    No variations",
        "Units used: mm",
        "",
        header.ljust(289),
    ]

    for i, (r, comment, desc) in enumerate(zip(rows, display_comments, display_descriptions)):
        x = x_values[i]
        y = y_values[i]
        rotation = rotation_values[i]
        line = (
            f'{r["Designator"]:<{designator_w}}'
            f'{comment:<{comment_w}}'
            f'{r["Layer"]:<{layer_w}}'
            f'{r["Footprint"]:<{footprint_w}}'
            f'{x:<{x_w}}'
            f'{y:<{y_w}}'
            f'{rotation:<{rotation_w}}'
            f'{desc}'
        )
        lines.append(line.ljust(289))

    Path(output_path).write_text("\n".join(lines) + "\n", encoding="cp1251")

def main():
    if len(sys.argv) < 2:
        print("Usage: python pcbdoc_to_pnp.py <input.PcbDoc> [output.txt]")
        raise SystemExit(2)
    inp = Path(sys.argv[1])
    out_txt = Path(sys.argv[2]) if len(sys.argv) >= 3 else inp.with_name(inp.stem + " Pick and Place.txt")
    ole = CFBReader(inp)
    rows, origin = build_rows(ole)
    write_pnp(rows, out_txt, source_path=inp)
    print(f"Components: {len(rows)}")
    print(f"Origin: X={origin[0]:.4f} mm, Y={origin[1]:.4f} mm")
    print(f"TXT: {out_txt}")


if __name__ == "__main__":
    main()
