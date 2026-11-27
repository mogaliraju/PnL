#!/usr/bin/env python3
"""
Generate a Cloud4C-style 'To-Be Component Architecture' diagram (SVG -> PNG)
from a JSON spec. See references/diagrams.md for the spec schema.

Usage:
    python gen_component_diagram.py diagram_spec.json out.png
"""
import json
import sys
import os
import html

# Cloud4C palette
NAVY = "#15124B"      # medallion / fabric boxes
BLUE = "#0B63CE"      # arrows, accents
LIGHT = "#EAF1FB"     # workspace fill
GREY = "#6B7280"
WHITE = "#FFFFFF"
TEXT_DARK = "#1F2937"

W, H = 1500, 820


def esc(s):
    return html.escape(str(s))


def box(x, y, w, h, fill, label, text_fill=WHITE, fs=18, rx=8, bold=True):
    weight = "700" if bold else "400"
    # wrap label into up to 2 lines on space if long
    words = str(label).split()
    lines, cur = [], ""
    for word in words:
        if len(cur) + len(word) + 1 <= 14:
            cur = (cur + " " + word).strip()
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    lines = lines[:3]
    tspans = ""
    n = len(lines)
    start_dy = -(n - 1) * (fs * 0.6)
    for i, ln in enumerate(lines):
        dy = start_dy + i * (fs * 1.2)
        tspans += f'<tspan x="{x + w/2}" dy="{dy if i==0 else fs*1.2}">{esc(ln)}</tspan>'
    return f'''<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{BLUE}" stroke-width="1.5"/>
<text x="{x + w/2}" y="{y + h/2}" text-anchor="middle" dominant-baseline="middle" font-family="Arial" font-size="{fs}" font-weight="{weight}" fill="{text_fill}">{tspans}</text>'''


def arrow(x1, y1, x2, y2):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{BLUE}" stroke-width="2.5" marker-end="url(#ah)"/>'


def label_text(x, y, s, fs=15, fill=TEXT_DARK, anchor="middle", bold=False):
    weight = "700" if bold else "400"
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="Arial" font-size="{fs}" font-weight="{weight}" fill="{fill}">{esc(s)}</text>'


def build_svg(spec):
    title = spec.get("title", "To-Be Component Architecture")
    sources = spec.get("sources", [])[:6]
    ingestion = spec.get("ingestion", "Dataflow Gen2 & Pipelines")
    layers = spec.get("layers", ["Landing Zone", "Bronze", "Silver", "Gold"])[:4]
    engines = spec.get("engines", [])[:2]
    consumption = spec.get("consumption", ["Power BI Reports"])[:3]
    orchestration = spec.get("orchestration", "Orchestration using Data Factory")
    supporting = spec.get("supporting", ["Active Directory", "Monitor", "Key Vault", "Purview"])
    platform_label = spec.get("platform_label", "Microsoft Fabric")

    parts = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Arial">')
    parts.append(f'''<defs><marker id="ah" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
<path d="M0,0 L8,3 L0,6 Z" fill="{BLUE}"/></marker></defs>''')
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{WHITE}"/>')
    parts.append(f'<text x="{W/2}" y="48" text-anchor="middle" font-family="Arial" font-size="30" font-weight="700" fill="{TEXT_DARK}">{esc(title)}</text>')

    # Source column (left)
    sx, sw, sh = 40, 150, 54
    src_top = 110
    gap = 14
    parts.append(label_text(sx + sw/2, src_top - 18, "Source Systems", 16, BLUE, bold=True))
    src_centers = []
    for i, s in enumerate(sources):
        y = src_top + i * (sh + gap)
        parts.append(box(sx, y, sw, sh, WHITE, s, text_fill=TEXT_DARK, fs=14, bold=True))
        src_centers.append(y + sh/2)
    src_mid = sum(src_centers) / len(src_centers) if src_centers else 300

    # Ingestion box
    ix, iw, ih = sx + sw + 60, 130, 80
    iy = src_mid - ih/2
    parts.append(box(ix, iy, iw, ih, "#F3F4F6", ingestion, text_fill=TEXT_DARK, fs=13, bold=True))
    for c in src_centers:
        parts.append(arrow(sx + sw, c, ix, src_mid if abs(c-src_mid) < 1 else c))
        if abs(c - src_mid) >= 1:
            parts.append(f'<line x1="{ix-20}" y1="{c}" x2="{ix-20}" y2="{src_mid}" stroke="{BLUE}" stroke-width="2"/>')
    # consolidate arrows into ingestion: draw simple lines src->ingestion left edge
    # (above approximations are fine visually)

    # Fabric workspace big box
    wsx = ix + iw + 70
    wsy = 95
    wsw = W - wsx - 250
    wsh = 470
    parts.append(f'<rect x="{wsx}" y="{wsy}" width="{wsw}" height="{wsh}" rx="14" fill="{LIGHT}" stroke="{BLUE}" stroke-width="2"/>')
    parts.append(label_text(wsx + 16, wsy + 28, f"{platform_label} Workspace", 18, NAVY, anchor="start", bold=True))

    # OneLake label inside
    parts.append(label_text(wsx + 16, wsy + 54, "OneLake (unified storage)", 13, GREY, anchor="start"))

    # Medallion layer boxes inside workspace
    n = len(layers)
    lw, lh = 130, 80
    inner_pad = 40
    avail = wsw - 2 * inner_pad
    step = (avail - lw) / max(n - 1, 1)
    ly = wsy + 180
    layer_centers = []
    arrow_from = ingestion
    prev_cx = None
    for i, lab in enumerate(layers):
        lx = wsx + inner_pad + i * step
        parts.append(box(lx, ly, lw, lh, NAVY, lab, text_fill=WHITE, fs=15))
        cx = lx + lw/2
        layer_centers.append((cx, ly))
        if prev_cx is not None:
            parts.append(arrow(prev_cx_x + lw, ly + lh/2, lx, ly + lh/2))
        prev_cx = cx
        prev_cx_x = lx

    # arrow ingestion -> first layer
    if layer_centers:
        parts.append(arrow(ix + iw, iy + ih/2, wsx, ly + lh/2))
        parts.append(arrow(wsx, ly + lh/2, layer_centers[0][0] - lw/2, ly + lh/2))

    # engines above layers
    if engines:
        ew, eh = 150, 56
        for j, eng in enumerate(engines):
            # place above the silver/gold-ish positions
            idx = min(j + 1, n - 1)
            ex = layer_centers[idx][0] - ew/2 if layer_centers else wsx + 200
            ey = wsy + 80
            parts.append(box(ex, ey, ew, eh, WHITE, eng, text_fill=NAVY, fs=13, bold=True))
            parts.append(f'<line x1="{ex+ew/2}" y1="{ey+eh}" x2="{layer_centers[idx][0]}" y2="{ly}" stroke="{BLUE}" stroke-width="2"/>')

    # Lakehouse note
    parts.append(label_text(wsx + wsw/2, ly + lh + 40, "Lakehouse (Delta)", 13, GREY))

    # Orchestration band
    oy = wsy + wsh - 50
    parts.append(f'<rect x="{wsx+inner_pad}" y="{oy}" width="{wsw-2*inner_pad}" height="38" rx="6" fill="#E8F0E3" stroke="#5B8C3E" stroke-width="1.5"/>')
    parts.append(label_text(wsx + wsw/2, oy + 24, orchestration, 14, "#3F6B2A", bold=True))

    # Consumption column (right)
    cx0 = wsx + wsw + 60
    cw, ch = 160, 64
    con_top = ly - 30
    con_centers = []
    parts.append(label_text(cx0 + cw/2, con_top - 16, "Consumption", 16, BLUE, bold=True))
    for i, c in enumerate(consumption):
        y = con_top + i * (ch + 18)
        parts.append(box(cx0, y, cw, ch, WHITE, c, text_fill=TEXT_DARK, fs=14, bold=True))
        con_centers.append(y + ch/2)
        # arrow from last layer
        if layer_centers:
            parts.append(arrow(layer_centers[-1][0] + lw/2, ly + lh/2, cx0, y + ch/2))

    # Supporting services row (bottom)
    syl = wsy + wsh + 60
    parts.append(label_text(60, syl - 18, "Supporting Services", 15, GREY, anchor="start", bold=True))
    n2 = len(supporting)
    bw = 200
    total = n2 * bw + (n2 - 1) * 30
    startx = (W - total) / 2
    for i, s in enumerate(supporting):
        x = startx + i * (bw + 30)
        parts.append(box(x, syl, bw, 50, "#F3F4F6", s, text_fill=NAVY, fs=14, rx=6, bold=True))

    parts.append('</svg>')
    return "\n".join(parts)


def main():
    if len(sys.argv) < 3:
        print("Usage: gen_component_diagram.py diagram_spec.json out.png", file=sys.stderr)
        sys.exit(1)
    spec_path, out_png = sys.argv[1], sys.argv[2]
    with open(spec_path) as f:
        spec = json.load(f)
    svg = build_svg(spec)
    out_svg = os.path.splitext(out_png)[0] + ".svg"
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    with open(out_svg, "w") as f:
        f.write(svg)
    # Render to PNG
    rendered = False
    try:
        import cairosvg
        cairosvg.svg2png(url=out_svg, write_to=out_png, scale=2, background_color="white")
        rendered = True
    except Exception as e:
        sys.stderr.write(f"cairosvg unavailable ({e}); trying rsvg-convert/inkscape\n")
    if not rendered:
        import subprocess
        for cmd in (["rsvg-convert", "-z", "2", "-o", out_png, out_svg],
                    ["inkscape", out_svg, "--export-filename", out_png, "--export-width", str(W*2)]):
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                rendered = True
                break
            except Exception:
                continue
    if not rendered:
        sys.stderr.write("Could not render PNG. SVG written at " + out_svg + "\n")
        sys.exit(2)
    print("Wrote", out_png, "and", out_svg)


if __name__ == "__main__":
    main()
