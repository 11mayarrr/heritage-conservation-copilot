# knowledge_base — closed treatment library

The agent may recommend **only** treatments listed in these JSON files (challenge brief, step 5).
It never generates treatments, materials or references.

- `sources.json` — every source document, with `status`: `read` (entries may cite it) or `not_read`
  (listed for future work; nothing may cite it until someone reads it).
- `treatments_*.json` — treatment entries. Each needs: `id`, `damage_types`, `title_ar`, `method_ar`,
  `usage_ar`, `materials`, `tools`, `cautions_ar`, `sources[]` (title, publisher, year, locator, url, and
  either `quote` or `summary_ar`) and `approval` (`demo_unapproved` or `approved`).
- **Quote or paraphrase:** a source in the public domain (e.g. US federal documents) is cited with a verbatim `quote`.
  A source whose copyright status is unknown or restrictive is marked `"quote_policy": "summary_only"` in `sources.json`;
  its entries carry an Arabic paraphrase in `summary_ar` plus the exact section/part in `locator`, and no copied text.
- **Do not put commas (`،` or `,`) inside `materials` / `tools` items**: the review panel splits those lists on commas.

Current content (15 entries, all `demo_unapproved`):
- `treatments_atturaif_manual.json` — 7 entries from the *Atturaif Living Museum Conservation Manual* (Lord Cultural
  Resources, 2008; UNESCO document 168965): crack fill, plaster renewal, plaster stabilization, wall-base repair,
  void/hole repair, wall-top cap, routine maintenance. Site-specific, cited by section/part with Arabic paraphrase
  (`summary_only`). Read through an automated PDF reader (~200k of 297k characters), so a specialist must check each
  number against the original. The source contradicts itself on lime (forbidden in brick/plaster, allowed in crack
  filling) and the entries say so.
- `treatments_nps_brief5.json` — 8 entries from NPS *Preservation Brief 5: Preservation of Historic Adobe Buildings*
  (1978), with verbatim quotes and approximate page numbers. A US adobe reference, not Najdi or At-Turaif specific.

Neither is the approved library from the challenge organizers. Replace or extend them with the approved treatment
library from the conservation authority; set `approval: "approved"` only for entries that authority approved.

A test (`tests/test_knowledge_base.py`) fails if an entry cites a source not marked `read`, lacks a locator, lacks a quote
(public-domain source) or a paraphrase (`summary_only` source), or if a `summary_only` entry contains a quote.
