# knowledge_base — closed treatment library

The agent may recommend **only** treatments listed in these JSON files (challenge brief, step 5).
It never generates treatments, materials or references.

- `sources.json` — every source document, with `status`: `read` (entries may cite it) or `not_read`
  (listed for future work; nothing may cite it until someone reads it).
- `treatments_*.json` — treatment entries. Each needs: `id`, `damage_types`, `title_ar`, `method_ar`,
  `usage_ar`, `materials`, `tools`, `cautions_ar`, `sources[]` (title, publisher, year, locator, url, quote)
  and `approval` (`demo_unapproved` or `approved`).

Current content: 8 entries derived from NPS *Preservation Brief 5: Preservation of Historic Adobe Buildings*
(1978), with verbatim quotes and approximate page numbers. This is a US adobe reference, not a Najdi or
At-Turaif specific source, so every entry is `demo_unapproved`. Replace or extend it with the approved treatment
library from the conservation authority; set `approval: "approved"` only for entries that authority approved.

A test (`tests/test_knowledge_base.py`) fails if an entry cites a source not marked `read`, or lacks a locator or quote.
