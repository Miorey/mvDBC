#!/usr/bin/env python3
"""Generate a schema/<Table>.json from a WoWDBDefs .dbd definition.

Usage:
    curl -LO https://raw.githubusercontent.com/wowdev/WoWDBDefs/master/definitions/Spell.dbd
    python3 tools/gen_schema.py Spell.dbd > schema/Spell.json

The generated schema is a starting point and is meant to be committed and
hand-edited (rename columns, set "hex": true on flag fields, ...).
"""
import json
import re
import sys

BUILD = "3.3.5.12340"
HEX_HINT = re.compile(r"(Flags|Attributes|Mask)", re.IGNORECASE)


def ver(s):
    return tuple(int(x) for x in s.strip().split("."))


def build_matches(line, target):
    t = ver(target)
    for part in line[len("BUILD "):].split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            if ver(lo) <= t <= ver(hi):
                return True
        elif part and ver(part) == t:
            return True
    return False


def parse(path, build):
    text = open(path, encoding="utf-8").read()
    blocks = [b.strip().splitlines() for b in re.split(r"\n\s*\n", text) if b.strip()]
    coltypes = {}
    for line in blocks[0][1:]:  # COLUMNS block
        m = re.match(r"(\w+)(<[^>]*>)?\s+(\w+)", line.strip())
        if m:
            coltypes[m.group(3)] = m.group(1)
    for block in blocks[1:]:
        if not any(l.startswith("BUILD ") and build_matches(l, build) for l in block):
            continue
        fields = []
        for line in block:
            if line.startswith(("BUILD", "LAYOUT", "COMMENT")):
                continue
            line = line.split("//")[0].strip()
            m = re.match(r"(?:\$[^$]*\$)?(\w+)(?:<(u?)(\d+)>)?(?:\[(\d+)\])?$", line)
            if not m:
                raise SystemExit(f"cannot parse layout line: {line!r}")
            name, unsigned, bits, count = m.groups()
            kind = coltypes.get(name, "int")
            f = {"name": name.removesuffix("_lang")}
            if kind == "locstring":
                f["type"] = "loc"
            elif kind == "string":
                f["type"] = "str"
            elif kind == "float":
                f["type"] = "float"
            else:
                f["type"] = ("u" if unsigned else "i") + (bits or "32")
                if HEX_HINT.search(name):
                    f["hex"] = True
            if count:
                f["count"] = int(count)
            fields.append(f)
        return fields
    raise SystemExit(f"no layout for build {build} in {path}")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    path = sys.argv[1]
    build = sys.argv[2] if len(sys.argv) > 2 else BUILD
    table = path.rsplit("/", 1)[-1].removesuffix(".dbd")
    schema = {"table": table, "build": build, "source": "WoWDBDefs", "fields": parse(path, build)}
    lines = ['{', f'  "table": {json.dumps(table)},', f'  "build": {json.dumps(build)},',
             '  "source": "WoWDBDefs",', '  "fields": [']
    lines += ["    " + json.dumps(f) + ("," if i < len(schema["fields"]) - 1 else "")
              for i, f in enumerate(schema["fields"])]
    lines += ["  ]", "}"]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
