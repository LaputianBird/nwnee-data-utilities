
In Visual Studio Code (or similar editors) associate the file types/extensions to CoffeeScript for fitting syntax highlighting

---

<br><br>

# `.ndugff` format

### Overview

The `.ndugff` format is a human-readable, structured text format designed for representing Neverwinter Nights GFF (Generic File Format) data. It serves as an intermediate format between the raw binary GFF files and user-facing configuration or manual editing workflows.

### Goals and Design Principles

- **Clear separation of data types:** Numeric and string values are explicitly distinguished to reflect the semantics of GFF fields used in computations (e.g., positions, rotations).
- **Indented structure:** Supports indentation for easy visual parsing and code folding in text editors, important for very large GFF files.
- **No multiline strings:** All string data is serialized using explicit `\n` escape sequences for newlines. Text editors can enable line wrapping.
- **Compact syntax:** Field type, name, and value appear on the same line with minimal punctuation. No verbose JSON-like constructs.
- **Manual editing friendly:** Users can move blocks of data without needing to update internal references or indices. Lists do not require numbering.
- **Explicit node closing:** Nodes close with the keyword `end()`, avoiding fragile punctuation pairs such as braces or brackets, simplifying parsing and improving clarity.

### Syntax Summary

```
gff.Byte(FieldName): 42
gff.Float(PositionX): 52.5916
gff.ResRef(Portrait): "po_hu_m_14_"
gff.CExoLocString(Description)
    gff.Dword(strref): -1
    gff.Language(ENGLISH): "Some description text\nWith newline"
    gff.Language(SPANISH_F): "Description text for spanish feminine"
end()
gff.Struct(CombatInfo).id(51882)
    gff.Byte(NumAttacks): 1
end()
gff.List(AttackList)
    gff.Struct().id(100)
        gff.Byte(DamageDice): 1
    end()
end()
```

---

<br><br>

# `.recipes` format

### Overview

The `.recipes` format defines how game resource files are extracted from Neverwinter Nights KEY/BIF archives. Users configure one or more *sources* (game installs) and one or more *recipes* (file filters), selecting one of each at a time to control extraction behavior.

This format prioritizes readability and manual editing while supporting robust filtering logic tailored around the specifics of the game’s naming conventions, but without the complexity of regex patterns.

### Goals and Design Principles

- **Separation of concerns:** Sources define where to extract from; recipes define what to extract.
- **Single active pair:** Only one source and one recipe are active per run, defined by a top-level selector.
- **Library approach:** Supports multiple sources and recipes saved for reuse and combination.
- **Simple filtering primitives:** Recipes use name-based or extension-based match/exclude rules.
- **Modular filtering logic:** Multiple filters of the same type can be specified per recipe, avoiding embedding complex logic into single filters.
- **Wildcards for compactness:** Special symbols simplify multi-target patterns (e.g., `pm@`), idiomatic for NWN resources.
- **Manual editing support:** Comments, copyable blocks, and plain-text syntax allow fast prototyping and debugging.
- **Fallback-friendly sources:** If no keylist is specified, defaults (`nwn_retail`, `nwn_base`) are used automatically.

### Syntax Summary

```
# Select active source and recipe
selected.source_id(0).recipe_id(1000)

# Define sources
source.id(0).description("Stable")
    game.path("/path/to/nwn")
    game.keylist("nwn_retail, nwn_base")  # Optional

# Define recipes
recipe.id(1000).description("All GFF files")
    exclude.fullname()
    match.fullname()
    exclude.name_start().name_part().name_end().extension()
    match.name_start().name_part().name_end().extension()
```

### Filter Expressions

Each `recipe` uses four pattern types for filtering:

- `exclude.fullname()` – Always excluded (highest priority)
- `match.fullname()` – Always included (unless excluded above)
- `exclude.*()` – Conditional excludes by pattern
- `match.*()` – Conditional includes by pattern

Pattern fields:

- `name_start("foo")` → filename starts with "foo"
- `name_part("bar")` → filename contains "bar"
- `name_end("baz")` → filename ends with "baz"
- `extension("2da, mdl")` → file has one of the listed extensions
- `fullname("exact_filename.ext")` → exact match

### Wildcards

Wildcard characters within quoted strings allow compact batch rules:

| Symbol | Meaning                     | Example             |
|--------|-----------------------------|---------------------|
| `@`    | Any letter (A–Z, a–z)       | `"pm@"` → `pma`     |
| `#`    | Any digit (0–9)             | `"tile#"` → `tile2` |
| `?`    | Letter, digit, or underscore| `"gui_???"` → `gui_abc`, `gui_12_` |

### Rule Precedence

Rules are evaluated top-down by group priority:

1. `exclude.fullname()` — Blacklist, absolute
2. `match.fullname()` — Whitelist, absolute (unless excluded above)
3. All `exclude.*()` — Conditional exclude
4. All `match.*()` — Conditional include (last to apply)

Only files allowed by the final outcome are extracted.
