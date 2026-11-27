#!/usr/bin/env node
/*
 * build_proposal.js — assemble a brand-styled .docx from a JSON content spec.
 * Supports two brands via spec.brand: "cloud4c" (default) and "automatonsx".
 * Usage: node build_proposal.js spec.json out.docx
 * See references/builder.md for the spec schema.
 */
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, Header, Footer, AlignmentType, LevelFormat, HeadingLevel,
  BorderStyle, WidthType, ShadingType, VerticalAlign, PageNumber, PageBreak,
  TableOfContents, Tab,
} = require("docx");

// ---- Brand themes ----
// Each theme defines the palette, fonts, logo, company name, and footer label.
// Cloud4C is the default; AutomatonsX is selected via spec.brand === "automatonsx".
const THEMES = {
  cloud4c: {
    company: "Cloud4C",
    font: "Arial",
    accent: "0024CA",     // logo royal blue — page border, header/footer rule
    h1: "0000CC",         // heading blue — H1 + cover title
    h2: "1F3864",         // navy — H2/H3
    headerFill: "1F3864", // table header band
    headerText: "FFFFFF",
    altFill: "EAF1FB",    // zebra row
    logo: "cloud4c_logo.png",
    logoCoverWidth: 2.2,
    coverStyle: "cloud4c",
  },
  automatonsx: {
    company: "AutomatonsX",
    font: "Calibri",
    accent: "C201B0",     // magenta — page border, section headings, cover band
    h1: "C201B0",         // magenta — H1 + cover client title
    h2: "262262",         // navy — H2/H3
    headerFill: "262262", // table header band (navy)
    headerText: "FFFFFF",
    altFill: "F6E6F4",    // light magenta zebra row
    logo: "automatonsx_logo.png",
    logoCoverWidth: 1.0,
    coverBand: "C201B0",  // magenta band behind title block
    coverTitleFill: "F2F2F2", // light-gray title block
    coverStyle: "automatonsx",
  },
};

const FOOTER_GREY = "595959";
const BORDER = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const CELL_BORDERS = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER };
const PAGE_W = 12240, MARGIN = 1440;
const CONTENT_W = PAGE_W - 2 * MARGIN; // 9360

const args = process.argv.slice(2);
if (args.length < 2) {
  console.error("Usage: node build_proposal.js spec.json out.docx");
  process.exit(1);
}
const spec = JSON.parse(fs.readFileSync(args[0], "utf8"));
const outPath = args[1];
const assetsDir = spec.assetsDir || path.join(__dirname, "..", "assets");
const client = spec.client || "Client";
const year = new Date().getFullYear();

// Resolve theme. Accept "ax"/"automatonsx" aliases; default to cloud4c.
const brandKey = (() => {
  const b = String(spec.brand || "cloud4c").toLowerCase().replace(/[^a-z0-9]/g, "");
  if (b === "ax" || b === "automatonsx") return "automatonsx";
  return "cloud4c";
})();
const T = THEMES[brandKey];

// Derived palette aliases (kept for readability below).
const NAVY = T.h2;
const BLUE = T.h1;
const ACCENT = T.accent;
const HEADER_FILL = T.headerFill;
const HEADER_TEXT = T.headerText;
const ALT_FILL = T.altFill;
const FONT = T.font;

// Page border in the brand accent colour on every page (thin single frame).
const PAGE_BORDER_SIDE = { style: BorderStyle.SINGLE, size: 4, color: ACCENT, space: 24 };
const PAGE_BORDERS = {
  pageBorders: { offsetFrom: "page" },
  pageBorderTop: PAGE_BORDER_SIDE,
  pageBorderBottom: PAGE_BORDER_SIDE,
  pageBorderLeft: PAGE_BORDER_SIDE,
  pageBorderRight: PAGE_BORDER_SIDE,
};

// ---- inline **bold** parser ----
function runs(text, base = {}) {
  const out = [];
  const parts = String(text).split(/(\*\*[^*]+\*\*)/g);
  for (const p of parts) {
    if (!p) continue;
    if (p.startsWith("**") && p.endsWith("**")) {
      out.push(new TextRun({ text: p.slice(2, -2), bold: true, ...base }));
    } else {
      out.push(new TextRun({ text: p, ...base }));
    }
  }
  return out.length ? out : [new TextRun({ text: "", ...base })];
}

function imageRun(p, widthIn) {
  const data = fs.readFileSync(p);
  const ext = path.extname(p).slice(1).toLowerCase();
  const type = ext === "jpg" ? "jpeg" : ext;
  // get pixel size to preserve aspect ratio
  let w = widthIn * 96, h = (widthIn * 96) * 0.5;
  try {
    if (type === "png") {
      const buf = data;
      const pw = buf.readUInt32BE(16), ph = buf.readUInt32BE(20);
      h = (widthIn * 96) * (ph / pw);
    }
  } catch (e) {}
  return new ImageRun({ data, type, transformation: { width: Math.round(widthIn * 96), height: Math.round(h) } });
}

// ---- block renderers ----
function renderBlock(b) {
  switch (b.type) {
    case "heading": {
      const lvl = b.level === 1 ? HeadingLevel.HEADING_1
        : b.level === 2 ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_3;
      return [new Paragraph({ heading: lvl, children: [new TextRun({ text: b.text })] })];
    }
    case "para":
      return [new Paragraph({ spacing: { after: 120 }, children: runs(b.text) })];
    case "list":
      return b.items.map((it) => new Paragraph({
        numbering: { reference: b.numbered ? "numbers" : "bullets", level: 0 },
        spacing: { after: 60 },
        children: runs(it),
      }));
    case "image": {
      const out = [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, children: [imageRun(b.path, b.width || 6.0)] })];
      if (b.caption) out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 }, children: [new TextRun({ text: b.caption, italics: true, size: 18, color: "595959" })] }));
      return out;
    }
    case "pagebreak":
      return [new Paragraph({ children: [new PageBreak()] })];
    case "spacer":
      return [new Paragraph({ spacing: { after: 120 }, children: [new TextRun("")] })];
    case "table":
      return [buildTable(b)];
    default:
      return [new Paragraph({ children: runs(b.text || "") })];
  }
}

function buildTable(b) {
  const ncol = b.header ? b.header.length : (b.rows[0] || []).length;
  let widths = b.widths;
  if (!widths || widths.length !== ncol) {
    const each = Math.floor(CONTENT_W / ncol);
    widths = Array(ncol).fill(each);
  }
  const rows = [];
  if (b.header) {
    rows.push(new TableRow({
      tableHeader: true,
      children: b.header.map((c, i) => new TableCell({
        width: { size: widths[i], type: WidthType.DXA },
        borders: CELL_BORDERS,
        shading: { fill: HEADER_FILL, type: ShadingType.CLEAR },
        margins: { top: 60, bottom: 60, left: 120, right: 120 },
        verticalAlign: VerticalAlign.CENTER,
        children: [new Paragraph({ children: [new TextRun({ text: String(c), bold: true, color: HEADER_TEXT })] })],
      })),
    }));
  }
  (b.rows || []).forEach((r, ri) => {
    rows.push(new TableRow({
      children: r.map((c, i) => new TableCell({
        width: { size: widths[i] || widths[0], type: WidthType.DXA },
        borders: CELL_BORDERS,
        shading: ri % 2 === 1 ? { fill: ALT_FILL, type: ShadingType.CLEAR } : undefined,
        margins: { top: 60, bottom: 60, left: 120, right: 120 },
        verticalAlign: VerticalAlign.CENTER,
        children: String(c).split("\n").map((line) => new Paragraph({ children: runs(line, { size: 20 }) })),
      })),
    }));
  });
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: widths,
    rows,
  });
}

// ---- cover page ----
function coverChildren() {
  if (T.coverStyle === "automatonsx") return coverAutomatonsX();
  return coverCloud4C();
}

function coverCloud4C() {
  const out = [];
  const logoPath = path.join(assetsDir, T.logo);
  if (fs.existsSync(logoPath)) {
    out.push(new Paragraph({ alignment: AlignmentType.LEFT, spacing: { after: 600 }, children: [imageRun(logoPath, T.logoCoverWidth)] }));
  }
  out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 600, after: 120 },
    children: [new TextRun({ text: spec.docType || "Technical Proposal", bold: true, size: 56, color: BLUE, font: FONT })] }));
  out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 },
    children: [new TextRun({ text: client, bold: true, size: 44, color: BLUE, font: FONT })] }));
  if (spec.subtitle) {
    out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [new TextRun({ text: spec.subtitle, bold: true, size: 28, color: "404040", font: FONT })] }));
  }
  if (spec.clientLogo && fs.existsSync(spec.clientLogo)) {
    out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 300 }, children: [imageRun(spec.clientLogo, 2.4)] }));
  }
  const meta = [];
  if (spec.version) meta.push(spec.version);
  if (spec.date) meta.push(spec.date);
  out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 400 },
    children: [new TextRun({ text: meta.join("  |  "), size: 24, color: FOOTER_GREY, font: FONT })] }));
  out.push(new Paragraph({ children: [new PageBreak()] }));
  return out;
}

// AutomatonsX cover: AX logo top-left, magenta band wrapping a light-gray title
// block (client name in magenta, subtitle in black), then a centered
// "Technical Proposal to" block with the client name and a date/version line.
function coverAutomatonsX() {
  const out = [];
  const logoPath = path.join(assetsDir, T.logo);
  if (fs.existsSync(logoPath)) {
    out.push(new Paragraph({ alignment: AlignmentType.LEFT, spacing: { after: 360 }, children: [imageRun(logoPath, T.logoCoverWidth)] }));
  }
  // Magenta top rule of the band.
  out.push(new Paragraph({ spacing: { before: 0, after: 0 }, shading: { type: ShadingType.CLEAR, fill: T.coverBand }, children: [new TextRun({ text: "", size: 16 })] }));
  // Light-gray title block: client name (magenta) + subtitle (black).
  out.push(new Paragraph({ shading: { type: ShadingType.CLEAR, fill: T.coverTitleFill }, spacing: { before: 240, after: 80 }, indent: { left: 200 },
    children: [new TextRun({ text: client.toUpperCase(), bold: true, size: 52, color: T.h1, font: FONT })] }));
  out.push(new Paragraph({ shading: { type: ShadingType.CLEAR, fill: T.coverTitleFill }, spacing: { before: 0, after: 320 }, indent: { left: 200 },
    children: [new TextRun({ text: spec.subtitle || spec.docType || "Technical Proposal", bold: true, size: 28, color: "000000", font: FONT })] }));
  // Magenta bottom rule of the band.
  out.push(new Paragraph({ spacing: { before: 0, after: 600 }, shading: { type: ShadingType.CLEAR, fill: T.coverBand }, children: [new TextRun({ text: "", size: 16 })] }));
  // Centered "Technical Proposal to" + client.
  out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 800, after: 240 },
    children: [new TextRun({ text: `${spec.docType || "Technical Proposal"} to`, bold: true, size: 30, color: "000000", font: FONT })] }));
  out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 },
    children: [new TextRun({ text: client.toUpperCase(), bold: true, size: 44, color: T.h1, font: FONT })] }));
  if (spec.clientLogo && fs.existsSync(spec.clientLogo)) {
    out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 300 }, children: [imageRun(spec.clientLogo, 2.4)] }));
  }
  const meta = [];
  if (spec.date) meta.push(`Date: ${spec.date}`);
  if (spec.version) meta.push(`Version ${String(spec.version).replace(/^v/i, "")}`);
  out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200 },
    children: [new TextRun({ text: meta.join("  "), size: 22, color: "000000", font: FONT })] }));
  out.push(new Paragraph({ children: [new PageBreak()] }));
  return out;
}

// ---- assemble ----
const children = [];
children.push(...coverChildren());
if (spec.toc) {
  children.push(new Paragraph({ children: [new TextRun({ text: "Contents", bold: true, size: 32, color: NAVY })], spacing: { after: 160 } }));
  children.push(new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" }));
  children.push(new Paragraph({ children: [new PageBreak()] }));
}
for (const b of spec.body || []) {
  for (const el of renderBlock(b)) children.push(el);
}

const footerSection = spec.footerSection || spec.docType || "Proposal";

// ---- brand-aware header/footer ----
function buildHeader() {
  if (T.coverStyle === "automatonsx") {
    // AX: logo top-right, no rule (clean).
    const logoPath = path.join(assetsDir, T.logo);
    const kids = fs.existsSync(logoPath)
      ? [imageRun(logoPath, 0.55)]
      : [new TextRun({ text: "AutomatonsX", size: 16, color: T.accent, bold: true, font: FONT })];
    return new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { after: 0 }, children: kids })] });
  }
  return new Header({ children: [new Paragraph({
    alignment: AlignmentType.RIGHT,
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: ACCENT, space: 2 } },
    children: [new TextRun({ text: `Cloud4C | ${client} | ${spec.docType || "Proposal"}`, size: 16, color: ACCENT, bold: true, font: FONT })],
  })] });
}

function buildFooter() {
  if (T.coverStyle === "automatonsx") {
    // AX: dashed top rule, centered "Automatonsx | Confidential | <section>", page number bottom-right.
    return new Footer({ children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        border: { top: { style: BorderStyle.DASHED, size: 6, color: "000000", space: 2 } },
        spacing: { before: 40, after: 0 },
        children: [new TextRun({ text: `Automatonsx | Confidential | ${footerSection}`, size: 16, color: FOOTER_GREY, bold: true, font: FONT })],
      }),
      new Paragraph({
        alignment: AlignmentType.RIGHT, spacing: { before: 0 },
        children: [new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "000000", bold: true, font: FONT })],
      }),
    ] });
  }
  return new Footer({ children: [new Paragraph({
    border: { top: { style: BorderStyle.SINGLE, size: 6, color: ACCENT, space: 2 } },
    tabStops: [{ type: "right", position: CONTENT_W }],
    children: [
      new TextRun({ text: `Confidential \u2013 Cloud4C & ${client}`, size: 16, color: FOOTER_GREY, font: FONT }),
      new TextRun({ children: [new Tab(), "Page ", PageNumber.CURRENT], size: 16, color: ACCENT, bold: true, font: FONT }),
    ],
  })] });
}

const doc = new Document({
  creator: T.company,
  title: `${client} — ${spec.docType || "Proposal"}`,
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, color: BLUE, font: FONT },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, color: NAVY, font: FONT },
        paragraph: { spacing: { before: 220, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 23, bold: true, color: NAVY, font: FONT },
        paragraph: { spacing: { before: 160, after: 100 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: 15840 },
        margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
        borders: PAGE_BORDERS,
      },
    },
    headers: { default: buildHeader() },
    footers: { default: buildFooter() },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(outPath, buf);
  console.log("Wrote", outPath);
}).catch((e) => { console.error(e); process.exit(1); });
