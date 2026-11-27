# Architecture Diagrams

Three diagrams appear in Solution Overview:

1. **Reference Architecture** — reuse `assets/reference_architecture.png` as-is.
2. **Logical Architecture** — reuse `assets/logical_architecture.png` as-is.
3. **Component Architecture & Data Flow** — **generate fresh per project** from the intake inputs.

## Generating the component diagram

The component diagram shows the actual data flow for *this* client: the real source systems on the left, the ingestion mechanism, OneLake + medallion layers (or Bronze-only), the transformation engines, and the consumption targets on the right, with supporting services (Active Directory, Monitor, Key Vault, Purview) underneath.

Use `scripts/gen_component_diagram.py` to render a clean SVG → PNG. It takes a JSON spec describing the boxes and renders the Cloud4C-style "To be Component Architecture" layout (matching the Fabric component diagrams in the reference proposals).

```bash
cd <skill-dir>
python scripts/gen_component_diagram.py diagram_spec.json /mnt/user-data/outputs/_assets/component_arch.png
```

### diagram_spec.json schema
```json
{
  "title": "To-Be Component Architecture",
  "sources": ["SAP S/4HANA", "Oracle", "REST APIs", "Salesforce", "Excel / Files"],
  "ingestion": "AXConnect + Dataflow Gen2 & Pipelines",
  "layers": ["Landing Zone", "Bronze", "Silver", "Gold / Star Schema"],
  "engines": ["Synapse / Spark Engineering"],
  "consumption": ["Power BI Reports", "Excel Reports"],
  "orchestration": "Orchestration using Data Factory",
  "supporting": ["Active Directory", "Monitor", "Key Vault", "Purview"],
  "platform_label": "Microsoft Fabric"
}
```

Field guidance:
- **sources** — the actual systems from intake. Keep labels short.
- **ingestion** — the mechanism (AXConnect for SAP, Dataflow Gen2, Data Factory copy, REST connectors). Mention AXConnect when SAP is a source and the client uses it.
- **layers** — the medallion layers actually built. For a Bronze-only/archive foundation, use `["Landing Zone", "Bronze", "Archive Zone"]` and label Silver/Gold as future in the prose, not the diagram.
- **engines** — transformation engines (Synapse/Spark notebooks, Dataflows).
- **consumption** — Power BI, Excel, downstream systems, REST API — only what's in scope.
- **supporting** — the Azure-native services row.

After rendering, verify the PNG visually (view it) before embedding. Embed it in §7.3 and reference the numbered flow in the prose.

## Fallback
If the Python renderer is unavailable, build the SVG by hand following the same left-to-right layout (Sources → Ingestion → Fabric workspace box containing OneLake + Landing/Bronze/Silver/Gold + engines → Consumption; Orchestration band below; supporting-services row at the bottom), then convert with:
```bash
python -c "import cairosvg; cairosvg.svg2png(url='component_arch.svg', write_to='component_arch.png', scale=2)"
```
or rsvg-convert / Inkscape if cairosvg is unavailable. Keep colors in the Cloud4C palette: Fabric navy `#15124B` boxes, blue `#0B63CE` arrows/labels, white background.
