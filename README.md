# mvDBC — Murloc Village DBC Files

This repository manages the custom **DBC (DataBase Client)** files for the **Murloc Village** WoW vanilla private server.

DBC files are binary data tables read by the WoW game client to define core game content: items, spells, dungeons, character start outfits, etc. This repo stores the modified versions of those files for both the server and the client (as distributable MPQ patches), in English (`enUS`) and French (`frFR`).

---

## Repository structure

```
mvDBC/
├── enUS/
│   ├── CSV/                    # Human-readable CSV versions of the DBC files (enUS)
│   └── DBC/DBFilesClient/      # Compiled binary DBC files for the enUS client patch
├── frFR/
│   ├── CSV/                    # Human-readable CSV versions of the DBC files (frFR)
│   └── DBC/DBFilesClient/      # Compiled binary DBC files for the frFR client patch
├── Server/
│   ├── csv/                    # Server-side DBC sources (CSV)
│   └── dbc/                    # Server-side DBC binaries (e.g. LFGDungeons.dbc)
├── Data/
│   ├── enUS/                   # MPQ client patch archives for English players
│   └── frFR/                   # MPQ client patch archives for French players
├── Optional/
│   └── dbc/DBFilesClient/      # Optional client DBC tweaks (e.g. lighting)
├── modified_DBC_history/       # Changelogs for each event/patch (what was changed and why)
├── CharStartOutfit.dbc.csv     # Defines starting gear for each race/class combination
├── MyDbcEditor 1.2.2.42/       # Windows tool for editing DBC files
├── mpqeditor_en/               # Windows tool for building and editing MPQ archives
└── Makefile
```

---

## File types

| Extension | Description |
|-----------|-------------|
| `.dbc` | Binary DataBase Client file — loaded directly by the WoW client or server |
| `.csv` | Human-readable export of a DBC file — edit these, then recompile to `.dbc` |
| `.mpq` | MPQ archive — distributable client patch containing the compiled DBC files |

---

## Locales

Two locales are maintained in parallel:

- **enUS** — English client
- **frFR** — French client

Each locale has its own `CSV/`, `DBC/`, and `Data/` (MPQ) directories. Server-side DBC files in `Server/` are locale-independent.

---

## Workflow

### Editing data

1. Open the relevant `.csv` file under `enUS/CSV/` or `frFR/CSV/` with **MyDbcEditor** (or any spreadsheet tool).
2. Make your changes (add/modify items, spells, etc.).
3. Use **MyDbcEditor** to export the result as a `.dbc` binary into the matching `DBC/DBFilesClient/` folder.
4. Repeat for the other locale if the change is locale-specific (e.g. spell/item names).

### Building client patches

Use **MPQEditor** to open the appropriate `Data/enUS/patch-enUS-K.mpq` (or `-L.mpq`) archive and replace the updated `.dbc` files inside it.

### Building server DBC files

```bash
make server_dbc
```

This copies `Server/dbc/` and `enUS/DBC/DBFilesClient/` into a `prod_serve_dbc/` folder ready to deploy to the game server.

```bash
make clean
```

Removes the `prod_serve_dbc/` output folder.

---

## Tracked DBC tables

| File | Scope | Description |
|------|-------|-------------|
| `Item.dbc` | Client (enUS + frFR) | Custom item definitions |
| `Spell.dbc` | Client (enUS + frFR) | Custom and modified spell data |
| `LFGDungeons.dbc` | Server | Dungeon finder entries and level ranges |
| `CharStartOutfit.dbc` | Server | Starting gear per race/class combination |
| `LightIntBand.dbc` | Optional / Client | Ambient lighting intensity bands |

---

## Event history

Changes are documented in `modified_DBC_history/`. Each file records:
- Which spell or item IDs were added or modified
- Which columns were changed and what the old/new values are
- Notes on spells that are referenced but not modified, and unused spells

### Events shipped so far

| Event | Patch | Description |
|-------|-------|-------------|
| Valentine's Day (Vanilla) | K | Custom perfume/cologne items (ID 60000+) and rebalanced seasonal spells |
| Halloween | L | Halloween-themed patch |

---

## Tools

Both tools are Windows executables bundled in the repo for convenience.

- **MyDbcEditor 1.2.2.42** — Edit and compile DBC/CSV files. Profiles are stored in `Profiles.ini`.
- **MPQEditor** — Build and inspect MPQ patch archives. Available in 32-bit (`Win32/`) and 64-bit (`x64/`) variants.
