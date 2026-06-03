# AGENT.md — Murloc Village DBC

This file documents conventions and workflows for AI agents working on this repository.

---

## Ground rules for agents

- **Never merge pull requests.** Open PRs and push branches freely, but merging is a human decision only.
- **Never force-push** to `master`.
- **Always create a new branch** for changes — never commit directly to `master`.

---

## What this repo does

It manages custom **DBC (DataBase Client)** files for the **Murloc Village** WoW vanilla private server. DBC files are binary data tables used by both the game client and server. The canonical editable form is CSV; binary `.dbc` files are compiled outputs.

The repo ships two kinds of artifacts:
- **Client patches** — MPQ archives (`Data/enUS/`, `Data/frFR/`) distributed to players
- **Server DBCs** — assembled by `make server_dbc` into `prod_serve_dbc/`

---

## File ownership rules

| Path | When to edit |
|------|-------------|
| `enUS/CSV/*.csv` | Adding or modifying English item/spell data |
| `frFR/CSV/*.csv` | Adding or modifying French item/spell data (names, descriptions) |
| `enUS/DBC/` / `frFR/DBC/` | Output only — compiled from the CSVs, do not hand-edit |
| `Server/csv/LFGDungeons.csv` | Adding or adjusting dungeon finder entries |
| `CharStartOutfit.dbc.csv` | Changing starting gear for any race/class combination |
| `modified_DBC_history/` | **Always update** when changing Item or Spell data |
| `Optional/` | Cosmetic/optional client tweaks; not required for gameplay |

Never commit `.dbc` binary files without a corresponding CSV change — the CSV is the source of truth.

---

## Conventions

### Custom item IDs
Custom items start at ID **60000** and increment upward. Always check the highest existing ID in `enUS/CSV/Item.csv` before assigning a new one.

### Spell damage scaling
When adapting retail/Cataclysm spell damage values down to vanilla tuning, the convention used in this project is **÷10**. Document both the original column value and the replacement in the history file.

Example from `modified_DBC_history/Valentine_Vanilla_Spell_Update.txt`:
```
col. 75: 2401 -> 241    ; #1/10 Damage range over time
col. 81: 10799 -> 1079  ; #1/10 Damage minimum over time
```

### Locale parity
`Item.dbc` and `Spell.dbc` must be updated for **both** `enUS` and `frFR`. The numeric data is identical; only the string columns (names, descriptions) differ between locales.

### MPQ patch slots
- Patch **K** — Valentine's Day event (enUS: `patch-enUS-K.mpq`, frFR: `patch-frFR-K.mpq`)
- Patch **L** — Halloween event

When adding a new seasonal event, assign the next available letter slot and update this file.

---

## How to add a new seasonal event

1. **Plan IDs**: pick a free item ID range (≥ 60000) and note which existing spell IDs will be reused or modified.
2. **Edit CSVs**: update `enUS/CSV/Item.csv` and `enUS/CSV/Spell.csv`. Mirror changes in `frFR/CSV/` with translated strings.
3. **Document changes**: create a new file in `modified_DBC_history/` named `<EventName>_Item_Update.txt` and `<EventName>_Spell_Update.txt`. List every modified column with old → new values and a short comment.
4. **Compile DBCs**: use MyDbcEditor to export updated CSVs to `.dbc` in the matching `DBC/DBFilesClient/` folders.
5. **Pack MPQ**: use MPQEditor to insert the new `.dbc` files into the appropriate `Data/<locale>/patch-<locale>-<letter>.mpq`.
6. **Build server files**: run `make server_dbc` and verify `prod_serve_dbc/` contains the expected files.
7. **Update README**: add the new event to the "Events shipped so far" table.

---

## Makefile targets

| Target | Effect |
|--------|--------|
| `make server_dbc` | Assembles `prod_serve_dbc/` from `Server/dbc/` + `enUS/DBC/DBFilesClient/` |
| `make clean` | Deletes `prod_serve_dbc/` |

---

## Key domain facts for agents

- **DBC row 1 is the header** — the first CSV row names the column types (`long`, `str`, `flags`, etc.), not actual game data.
- **Spell columns are positional** — there is no named-column schema in the binary format; column numbers referenced in the history files correspond to 1-indexed CSV columns.
- **`-1` means "none"** in most integer fields (e.g. item slots, display IDs).
- **`LFGDungeons.dbc`** is server-side only; clients do not need it patched.
- **`CharStartOutfit.dbc`** is keyed on `(race, class, gender)` — rows 1–N map to specific combinations; check existing rows before adding new ones.
