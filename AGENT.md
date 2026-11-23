# AGENT.md — Murloc Village DBC

This file documents conventions and workflows for AI agents working on this repository.

---

## Ground rules for agents

- **Never merge pull requests.** Open PRs and push branches freely, but merging is a human decision only.
- **Never force-push** to `master`.
- **Always create a new branch** for changes — never commit directly to `master`.

---

## What this repo does

It manages custom **DBC** files (WoW client build 3.3.5a/12340) for the **Murloc Village** private server.
**`tables/*.csv` is the only source of truth**; `.dbc` files are generated into `build/` (git-ignored) by
`tools/dbctool.py`, driven by `schema/<Table>.json` (column names/types) and `dbc.json` (locales + targets).

The repo ships:
- **Client patches**: MPQ archives (`Data/enUS/`, `Data/frFR/`), packed by `make mpq` from `build/client/<locale>/`
- **Server DBCs**: `make server_dbc` → `prod_serve_dbc/`

---

## File ownership rules

| Path | When to edit |
|------|-------------|
| `tables/*.csv` | Any data change. Localised text lives in `*_enUS` / `*_frFR` columns of the same row |
| `schema/*.json` | Only to rename columns or toggle `"hex"`; field order/types must match the client build |
| `dbc.json` | Adding a table, locale or build target |
| `build/`, `prod_serve_dbc/` | Generated, never commit |
| `legacy/` | Unmigrated old files, see README "Known issues" |

Always run `make fmt && make check` before committing a CSV change. Never commit `.dbc` files.

---

## Conventions

### Custom item IDs
Custom items start at ID **60000** and increment upward. Always check the highest existing ID in `tables/Item.csv` before assigning a new one.

### Spell damage scaling
When adapting retail/Cataclysm spell damage values down to vanilla tuning, the convention used in this project is **÷10**. Document both the original value and the replacement (with the column name) in the commit/PR description.

Example from `modified_DBC_history/Valentine_Vanilla_Spell_Update.txt`:
```
col. 75: 2401 -> 241    ; #1/10 Damage range over time
col. 81: 10799 -> 1079  ; #1/10 Damage minimum over time
```

### Locale parity
Numeric data is shared by all locales (one row per record). When adding or changing text, fill **both** `*_enUS` and `*_frFR` columns.

### MPQ patch slots
- Patch **K** — Valentine's Day event (enUS: `patch-enUS-K.mpq`, frFR: `patch-frFR-K.mpq`)
- Patch **L** — Halloween event

When adding a new seasonal event, assign the next available letter slot and update this file.

---

## How to add a new seasonal event

1. **Plan IDs**: pick a free item ID range (≥ 60000) and note which existing spell IDs will be reused or modified.
2. **Edit CSVs**: update `tables/Item.csv` and `tables/Spell.csv`, filling both `_enUS` and `_frFR` text columns.
3. **Validate**: `make fmt && make check`.
4. **Document changes**: describe every modified spell/item (old → new values and why) in the commit message / PR description.
5. **Build**: add the new letter to `MPQ_SLOTS` in the `Makefile`, then `make mpq` (packs the full client tables into every slot).
6. **Server files**: `make server_dbc` and verify `prod_serve_dbc/`.
7. **Update README**: add the new event to the "Events shipped so far" table.

---

## Makefile targets

| Target | Effect |
|--------|--------|
| `make build` | Compile `tables/*.csv` into `build/` |
| `make check` | Validate CSVs (header vs schema, duplicate IDs, canonical format, round-trip) |
| `make fmt` | Normalise CSV formatting |
| `make server_dbc` | Build, then assemble `prod_serve_dbc/` from `build/server/` |
| `make mpq` | Build, then pack `Data/<locale>/patch-<locale>-<slot>.mpq` for each slot in `MPQ_SLOTS` |
| `make clean` | Delete `build/` and `prod_serve_dbc/` |

---

## Key domain facts for agents

- **Columns are named** (WoWDBDefs names); arrays are 1-indexed (`Effect_1..3`). Column numbers in `modified_DBC_history/` refer to the old positional layout, so map them by name.
- Strings are escaped on one line: `\n`, `\r`, `\\`. Flags/masks are hex; empty numeric cell = 0.
- **`-1` means "none"** in most integer fields (e.g. item slots, display IDs).
- **`LFGDungeons`** is server-side only; clients do not need it patched.
- **Client and server must match** for anything the server validates (area restrictions, spell values): ship `make server_dbc` output to the worldserver along with the MPQ.
- **`CharStartOutfit`** is keyed on `(race, class, sex)`; not yet migrated (see README).
