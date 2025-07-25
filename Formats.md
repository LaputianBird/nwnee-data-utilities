# NDU GFF DSL Specification

## Overview

The NDU GFF DSL is a human-readable, structured text format designed for representing Neverwinter Nights GFF (Generic File Format) data. It serves as an intermediate format between the raw binary GFF files and user-facing configuration or editing workflows.

---

## Goals and Design Principles

- **Clear separation of data types:** Numeric and string values are explicitly distinguished to reflect the semantics of GFF fields used in computations (e.g., positions, rotations).
- **Indented structure:** The DSL supports indentation to enable easy visual parsing and code folding in text editors, important for very large GFF files.
- **No multiline strings:** All string data is serialized using explicit `\n` escape sequences for newlines. Text editors can enable line wrapping for user convenience.
- **Compact syntax:** Field type, name, and value appear on the same line with minimal punctuation. No verbose JSON-like constructs.
- **Manual editing friendly:** Users can move blocks of data without needing to update internal references or indices. Lists do not require numbering.
- **Explicit node closing:** Nodes close with the keyword `end()`, avoiding reliance on punctuation such as braces or brackets. This simplifies parsing and improves clarity.

---

## Syntax Summary

```coffeescript
gff.Byte(FieldName): 42
gff.Float(PositionX): 52.5916
gff.ResRef(Portrait): "po_hu_m_14_"
gff.CExoLocString(Description)
    gff.Dword(strref): -1
    gff.Language(ENGLISH): "Some description text\nWith newline"
end()
gff.Struct(CombatInfo).id(51882)
    gff.Byte(NumAttacks): 1
end()
gff.List(AttackList)
    gff.Struct().id(100)
        gff.Byte(DamageDice): 1
    end()
end()
