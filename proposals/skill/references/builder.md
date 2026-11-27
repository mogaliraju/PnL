# Document Builder — `build_proposal.js`

`scripts/build_proposal.js` turns a JSON content spec into a brand-styled `.docx`. It supports two brands via the `brand` field: **`cloud4c`** (default) and **`automatonsx`**. The brand drives palette, font, logo, cover layout, header, and footer; everything else (blocks, tables, TOC, US Letter, full-page border) works the same for both.

- **cloud4c** — Arial, royal blue `#0024CA` border/accents, navy `#1F3864` sub-headings + table band, heading blue `#0000CC` H1/cover title. Header: "Cloud4C | {client} | {docType}" with a blue rule. Footer: "Confidential – Cloud4C & {client}" + page number.
- **automatonsx** — Calibri, magenta `#C201B0` border + H1 + cover band, navy `#262262` sub-headings + table band. Cover: AX logo top-left, magenta band wrapping a light-gray title block, centered "Technical Proposal to". Header: AX logo top-right. Footer: dashed rule, "Automatonsx | Confidential | {footerSection}" centered, page number bottom-right.

```bash
node scripts/build_proposal.js spec.json /mnt/user-data/outputs/<Client>_Proposal_<vN>.docx
```

## Top-level spec
```json
{
  "brand": "automatonsx",                     // "automatonsx" | "cloud4c" (default cloud4c)
  "client": "Sobha Siniya",
  "clientShort": "Sobha",
  "docType": "Techno-Commercial Proposal",    // cover title / "Technical Proposal to" verb
  "subtitle": "DataLake Implementation in Microsoft Fabric",
  "version": "V0.1",
  "date": "23 June 2026",
  "footerSection": "Scope of Work",           // AutomatonsX footer label only; optional
  "clientLogo": "/path/to/client_logo.png",   // optional, centered on cover
  "assetsDir": "<skill-dir>/assets",          // where the brand logos live
  "toc": true,
  "body": [ /* array of blocks, in order */ ]
}
```

The builder always prepends the cover page and document-control front matter is provided via blocks. Put Confidentiality, Copyright, Intro, Scope, Solution, Timelines, Commercials, Conclusion as blocks in `body`.

## Block types

**Heading** — `outlineLevel` 0/1/2 maps to H1/H2/H3 (numbered automatically? No — pass explicit numbers in text if you want "4.3.1").
```json
{ "type": "heading", "level": 1, "text": "Scope of Work" }
{ "type": "heading", "level": 2, "text": "4.1 Executive Summary" }
```

**Paragraph** — supports inline bold via `**…**`.
```json
{ "type": "para", "text": "Cloud4C proposes an enterprise-grade **Microsoft Fabric** data platform…" }
```

**Bullets / Numbered** — array of strings (inline `**bold**` supported). Use `numbered: true` for 1,2,3.
```json
{ "type": "list", "items": ["First **point**", "Second point"] }
{ "type": "list", "numbered": true, "items": ["Step one", "Step two"] }
```

**Table** — first row treated as navy header. `widths` optional (DXA, must sum sensibly); else equal.
```json
{ "type": "table",
  "header": ["Sr. No.", "Component", "Cost Type", "Cost (USD)"],
  "rows": [["1","Project Implementation Cost","OTC","55,200"],
           ["2","Microsoft Funding","Funded","5,200"]],
  "widths": [1200, 4800, 1600, 1760] }
```

**Image** — embed a PNG (architecture diagrams, logos). `width` in inches (default 6.0).
```json
{ "type": "image", "path": "<skill-dir>/assets/reference_architecture.png", "width": 6.2, "caption": "Reference Architecture" }
```

**Page break**
```json
{ "type": "pagebreak" }
```

**Spacer** — small vertical gap: `{ "type": "spacer" }`

## Worked example (fragment)
```json
{
  "client": "ACME Corp", "clientShort": "ACME",
  "docType": "Techno-Commercial Proposal",
  "subtitle": "Enterprise Data Platform on Microsoft Fabric",
  "version": "V0.1", "date": "23 June 2026",
  "assetsDir": "/tmp/dataeng-proposal/assets",
  "toc": true,
  "body": [
    { "type": "heading", "level": 1, "text": "1. Confidentiality" },
    { "type": "para", "text": "This document contains confidential and proprietary information about Cloud4C. …" },
    { "type": "pagebreak" },
    { "type": "heading", "level": 1, "text": "4. Scope of Work" },
    { "type": "heading", "level": 2, "text": "4.1 Executive Summary" },
    { "type": "para", "text": "ACME Corp is seeking to establish …" },
    { "type": "heading", "level": 2, "text": "4.2 Objective" },
    { "type": "list", "items": ["**Integrate sources** – …", "**Governed lakehouse** – …"] },
    { "type": "heading", "level": 1, "text": "5. Solution Overview" },
    { "type": "heading", "level": 2, "text": "5.1 Reference Architecture" },
    { "type": "image", "path": "/tmp/dataeng-proposal/assets/reference_architecture.png", "width": 6.2 },
    { "type": "heading", "level": 1, "text": "7. Commercials" },
    { "type": "table", "header": ["Sr. No.","Component","Cost Type","Cost (USD)"],
      "rows": [["1","Project Implementation Cost","OTC","95,800"]] }
  ]
}
```

## Notes
- Write the spec to a temp file, then call the builder. For large proposals, assemble the `body` array programmatically in a small Node or Python snippet, or just write the JSON directly.
- After building, **validate** with `python /mnt/skills/public/docx/scripts/office/validate.py <file>`.
- If you need a construct the builder doesn't support (footnotes, tracked changes, complex merged cells), fall back to docx-js directly per the docx skill.
