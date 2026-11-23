#!/usr/bin/env python3
"""dbctool — CSV <-> DBC (WDBC, WoW 3.3.5a) converter. Python 3.9+, stdlib only.

The CSV files in tables/ are the source of truth; .dbc files are build outputs.
Column names and types come from schema/<Table>.json, build targets from dbc.json.

Commands:
  build  [--out DIR]                 build every table/target listed in dbc.json
  check                              validate all CSVs (schema, IDs, format, round-trip)
  fmt                                rewrite all CSVs in canonical form
  import TABLE LOC=FILE.dbc [...]    (re)create tables/TABLE.csv from one DBC per locale
  dump   TABLE FILE.dbc              print a DBC as CSV (inspect/diff any DBC)
"""
import argparse
import csv
import io
import json
import math
import os
import struct
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Locale string slots of a 3.3.5a "locstring": 16 slots followed by a flags/mask field.
LOCALE_SLOTS = ["enUS", "koKR", "frFR", "deDE", "zhCN", "zhTW", "esES", "esMX",
                "ruRU", "jaJP", "ptPT", "itIT", "unk12", "unk13", "unk14", "unk15"]
INT_FMT = {("i", 8): "b", ("u", 8): "B", ("i", 16): "h", ("u", 16): "H", ("i", 32): "i", ("u", 32): "I"}


class DbcError(Exception):
    pass


# --------------------------------------------------------------------------- schema

class Col:
    """One physical field in a DBC record."""

    def __init__(self, csv_name, kind, fmt="I", signed=False, bits=32, hex_=False, locale=None):
        self.csv_name = csv_name  # None = hidden (unused locale slot)
        self.kind = kind          # int | float | str
        self.fmt, self.signed, self.bits, self.hex, self.locale = fmt, signed, bits, hex_, locale


def load_config():
    with open(os.path.join(ROOT, "dbc.json"), encoding="utf-8") as fh:
        return json.load(fh)


def load_columns(table, locales):
    """Expand schema/<table>.json into physical columns. `locales` = locales kept in the CSV."""
    with open(os.path.join(ROOT, "schema", table + ".json"), encoding="utf-8") as fh:
        schema = json.load(fh)
    cols = []
    for f in schema["fields"]:
        count, name, typ = f.get("count", 1), f["name"], f["type"]
        for k in range(count):
            cname = f"{name}_{k + 1}" if count > 1 else name
            if typ == "loc":
                for slot in LOCALE_SLOTS:
                    cols.append(Col(f"{cname}_{slot}" if slot in locales else None, "str", locale=slot))
                cols.append(Col(f"{cname}_flags", "int", "I", hex_=True))
            elif typ == "str":
                cols.append(Col(cname, "str"))
            elif typ == "float":
                cols.append(Col(cname, "float", "f"))
            else:
                sign, bits = typ[0], int(typ[1:])
                cols.append(Col(cname, "int", INT_FMT[(sign, bits)], sign == "i", bits, f.get("hex", False)))
    return cols


def record_format(cols):
    return "<" + "".join("I" if c.kind == "str" else c.fmt for c in cols)


# --------------------------------------------------------------------------- DBC I/O

def read_dbc(path, cols):
    """Return records as lists of Python values (str for strings) in physical column order."""
    with open(path, "rb") as fh:
        data = fh.read()
    magic, nrec, nfield, recsize, strsize = struct.unpack_from("<4s4I", data)
    if magic != b"WDBC":
        raise DbcError(f"{path}: not a WDBC file")
    fmt = record_format(cols)
    if nfield != len(cols) or recsize != struct.calcsize(fmt):
        raise DbcError(f"{path}: has {nfield} fields/{recsize} bytes per record, "
                       f"schema expects {len(cols)}/{struct.calcsize(fmt)}")
    sbase = 20 + nrec * recsize
    if len(data) != sbase + strsize:
        raise DbcError(f"{path}: file size does not match header")

    def string(off):
        end = data.index(b"\0", sbase + off)
        return data[sbase + off:end].decode("utf-8")

    out = []
    for i in range(nrec):
        raw = struct.unpack_from(fmt, data, 20 + i * recsize)
        out.append([string(v) if c.kind == "str" else v for c, v in zip(cols, raw)])
    return out


def write_dbc(path, cols, records):
    fmt = record_format(cols)
    strings, block = {"": 0}, bytearray(b"\0")
    body = bytearray()
    for rec in records:
        vals = []
        for c, v in zip(cols, rec):
            if c.kind == "str":
                if v not in strings:
                    strings[v] = len(block)
                    block += v.encode("utf-8") + b"\0"
                v = strings[v]
            vals.append(v)
        body += struct.pack(fmt, *vals)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<4s4I", b"WDBC", len(records), len(cols), struct.calcsize(fmt), len(block)))
        fh.write(body)
        fh.write(block)


# --------------------------------------------------------------------------- CSV values

def fmt_float(x):
    if not math.isfinite(x):
        raise DbcError(f"non-finite float {x}")
    bits = struct.pack("<f", x)
    for p in range(1, 10):
        s = "%.*g" % (p, x)
        if struct.pack("<f", float(s)) == bits:
            return s
    return repr(x)


def escape(s):
    return s.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n")


def unescape(s):
    out, i = [], 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            out.append({"\\": "\\", "n": "\n", "r": "\r"}.get(nxt, "\\" + nxt))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def to_text(c, v):
    if c.kind == "str":
        return escape(v)
    if c.kind == "float":
        return fmt_float(v)
    if c.hex:
        return "0x%X" % (v & ((1 << c.bits) - 1))
    return str(v)


def from_text(c, s):
    s = s.strip() if c.kind != "str" else s
    if c.kind == "str":
        return unescape(s)
    if s == "":
        return 0.0 if c.kind == "float" else 0
    if c.kind == "float":
        return struct.unpack("<f", struct.pack("<f", float(s)))[0]
    neg = s.startswith("-")
    body = s[1:] if neg else s
    v = int(body, 16) if body.lower().startswith("0x") else int(body)
    v = -v if neg else v
    lo = -(1 << (c.bits - 1))
    if not lo <= v < (1 << c.bits):
        raise ValueError(f"{s} out of range for {c.bits}-bit field")
    v &= (1 << c.bits) - 1  # normalise to unsigned bit pattern ...
    if c.signed and v >= 1 << (c.bits - 1):
        v -= 1 << c.bits      # ... then back to the signed value struct expects
    return v


# --------------------------------------------------------------------------- tables

def csv_path(table):
    return os.path.join(ROOT, "tables", table + ".csv")


def table_columns(table, cfg):
    return load_columns(table, cfg["tables"][table].get("locales", []))


def rows_to_csv(cols, rows):
    """rows: lists over *visible* columns (python values)."""
    vis = [c for c in cols if c.csv_name]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([c.csv_name for c in vis])
    for r in rows:
        w.writerow([to_text(c, v) for c, v in zip(vis, r)])
    return buf.getvalue()


def read_csv(table, cols):
    path = csv_path(table)
    vis = [c for c in cols if c.csv_name]
    with open(path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    reader = csv.reader(io.StringIO(text))
    header = next(reader)
    expected = [c.csv_name for c in vis]
    if header != expected:
        missing = [h for h in expected if h not in header]
        extra = [h for h in header if h not in expected]
        raise DbcError(f"{path}: header does not match schema (missing: {missing}, unexpected: {extra})")
    rows = []
    for lineno, line in enumerate(reader, start=2):
        if not line:
            continue
        if len(line) != len(vis):
            raise DbcError(f"{path}:{lineno}: {len(line)} values, expected {len(vis)}")
        row = []
        for c, s in zip(vis, line):
            try:
                row.append(from_text(c, s))
            except ValueError as e:
                raise DbcError(f"{path}:{lineno}: column {c.csv_name}: {e}") from None
        rows.append(row)
    return rows, text


def to_records(cols, rows, locale):
    """Expand visible CSV rows into full physical records for one client locale."""
    recs = []
    for r in rows:
        it = iter(r)
        rec = []
        for c in cols:
            v = next(it) if c.csv_name else ""
            if c.locale is not None and c.locale != locale:
                v = ""  # each client DBC only carries its own locale's strings
            rec.append(v)
        recs.append(rec)
    return recs


def import_dbcs(table, cols, sources):
    """Merge one DBC per locale into visible rows; fail if numeric data disagrees."""
    loaded = {loc: read_dbc(p, cols) for loc, p in sources.items()}
    first_loc = next(iter(loaded))
    base = loaded[first_loc]
    for loc, recs in loaded.items():
        if len(recs) != len(base):
            raise DbcError(f"{table}: {loc} has {len(recs)} records, {first_loc} has {len(base)}")
    rows = []
    for i, rec in enumerate(base):
        row = []
        for j, c in enumerate(cols):
            if c.locale is not None:
                # A client DBC only carries text in its own locale slot; anything
                # else would be silently dropped on rebuild, so refuse it.
                for loc, recs in loaded.items():
                    if recs[i][j] and (loc != c.locale or c.csv_name is None):
                        raise DbcError(f"{table} ID {rec[0]}: {loc} DBC has text in locale slot "
                                       f"{c.locale}, which the CSV does not keep (check dbc.json locales)")
                if c.csv_name:
                    src = loaded.get(c.locale)
                    row.append(src[i][j] if src is not None else "")
            else:
                for loc, recs in loaded.items():
                    if recs[i][j] != rec[j]:
                        raise DbcError(f"{table} ID {rec[0]}: column {c.csv_name} differs "
                                       f"between {first_loc} and {loc}")
                row.append(rec[j])
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- commands

def cmd_import(args, cfg):
    cols = table_columns(args.table, cfg)
    sources = dict(s.split("=", 1) for s in args.sources)
    rows = import_dbcs(args.table, cols, sources)
    os.makedirs(os.path.join(ROOT, "tables"), exist_ok=True)
    with open(csv_path(args.table), "w", encoding="utf-8", newline="") as fh:
        fh.write(rows_to_csv(cols, rows))
    print(f"wrote tables/{args.table}.csv ({len(rows)} rows)")


def cmd_dump(args, cfg):
    cols = load_columns(args.table, LOCALE_SLOTS)
    sys.stdout.write(rows_to_csv(cols, read_dbc(args.file, cols)))


def targets(table, tcfg, cfg):
    """Yield (output path relative to build dir, locale) pairs for a table."""
    for t in tcfg.get("targets", []):
        if t == "client":
            for loc in cfg["locales"]:
                yield os.path.join("client", loc, "DBFilesClient", table + ".dbc"), loc
        elif t == "server":
            yield os.path.join("server", table + ".dbc"), cfg["server_locale"]
        elif t == "optional":
            yield os.path.join("optional", "DBFilesClient", table + ".dbc"), cfg["server_locale"]
        else:
            raise DbcError(f"dbc.json: unknown target {t!r} for {table}")


def cmd_build(args, cfg):
    for table, tcfg in cfg["tables"].items():
        cols = table_columns(table, cfg)
        rows, _ = read_csv(table, cols)
        for rel, loc in targets(table, tcfg, cfg):
            if tcfg.get("locales") and loc not in tcfg["locales"]:
                raise DbcError(f"{table}: target needs locale {loc} but CSV only has {tcfg['locales']}")
            out = os.path.join(args.out, rel)
            write_dbc(out, cols, to_records(cols, rows, loc))
            print(f"built {out}")


def cmd_check(args, cfg):
    import tempfile
    ok = True
    for table, tcfg in cfg["tables"].items():
        try:
            cols = table_columns(table, cfg)
            rows, text = read_csv(table, cols)
            dup = [i for i, n in Counter(r[0] for r in rows).items() if n > 1]
            if dup:
                raise DbcError(f"{table}: duplicate IDs {sorted(dup)[:20]}")
            if rows_to_csv(cols, rows) != text:
                raise DbcError(f"{table}: CSV is not in canonical form, run `make fmt`")
            locs = tcfg.get("locales") or [cfg["server_locale"]]
            with tempfile.TemporaryDirectory() as tmp:
                for loc in locs:
                    p = os.path.join(tmp, f"{table}.{loc}.dbc")
                    recs = to_records(cols, rows, loc)
                    write_dbc(p, cols, recs)
                    if read_dbc(p, cols) != recs:
                        raise DbcError(f"{table}: {loc} round-trip mismatch")
            print(f"ok    {table} ({len(rows)} rows)")
        except DbcError as e:
            ok = False
            print(f"FAIL  {e}")
    if not ok:
        sys.exit(1)


def cmd_fmt(args, cfg):
    for table in cfg["tables"]:
        cols = table_columns(table, cfg)
        rows, text = read_csv(table, cols)
        new = rows_to_csv(cols, rows)
        if new != text:
            with open(csv_path(table), "w", encoding="utf-8", newline="") as fh:
                fh.write(new)
            print(f"formatted tables/{table}.csv")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", default=os.path.join(ROOT, "build"))
    sub.add_parser("check")
    sub.add_parser("fmt")
    i = sub.add_parser("import")
    i.add_argument("table")
    i.add_argument("sources", nargs="+", metavar="LOC=FILE.dbc")
    d = sub.add_parser("dump")
    d.add_argument("table")
    d.add_argument("file")
    args = p.parse_args()
    cfg = load_config()
    try:
        {"build": cmd_build, "check": cmd_check, "fmt": cmd_fmt,
         "import": cmd_import, "dump": cmd_dump}[args.cmd](args, cfg)
    except DbcError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
