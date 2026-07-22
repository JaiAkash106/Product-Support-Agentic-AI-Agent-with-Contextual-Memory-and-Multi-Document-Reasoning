const fs = require("fs");
const path = require("path");

const WORKSPACE = "D:\\hcl";
const OUTPUT_FILE = path.join(
  WORKSPACE,
  "Product_Support_Agentic_AI_Enterprise_Documentation.docx"
);

const SOURCE_FILES = [
  "Product_Support_Agentic_AI_SRS.md",
  "Product_Support_Agentic_AI_HLD.md",
  "Product_Support_Agentic_AI_LLD.md",
  "Product_Support_Agentic_AI_UID.md",
];

const HCL_BLUE = "0057B8";
const HCL_LIGHT_BLUE = "D9E8F5";
const LIGHT_GRAY = "EDEDED";
const BORDER_GRAY = "A6A6A6";

function xmlEscape(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function cleanText(value) {
  return String(value).replace(/\u0000/g, "");
}

function formatIsoDate(dateString) {
  return `${dateString}T00:00:00Z`;
}

function dedupe(values) {
  return [...new Set(values.filter(Boolean))];
}

function parseTableRow(line) {
  let text = line.trim();
  if (!text.startsWith("|") || !text.endsWith("|")) {
    return null;
  }
  text = text.slice(1, -1);
  return text.split("|").map((cell) => cell.trim());
}

function isTableDivider(cells) {
  return cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function readMarkdown(fileName) {
  const fullPath = path.join(WORKSPACE, fileName);
  return fs.readFileSync(fullPath, "utf8").replace(/\r\n/g, "\n");
}

function extractMetadata(fileName, text) {
  const lines = text.split("\n");
  const headings = lines
    .filter((line) => /^#{1,6}\s+/.test(line))
    .map((line) => ({
      level: line.match(/^#+/)[0].length,
      text: line.replace(/^#{1,6}\s+/, "").trim(),
    }));

  const projectTitle = headings.find((h) => h.level === 1)?.text || fileName;
  const documentTitle = headings.find((h) => h.level === 2)?.text || fileName;

  const revisionHeadingIndex = lines.findIndex(
    (line) => line.trim() === "## Revision History"
  );

  let revisionRows = [];
  if (revisionHeadingIndex >= 0) {
    for (let i = revisionHeadingIndex + 1; i < lines.length; i += 1) {
      if (!lines[i].trim()) {
        continue;
      }
      if (lines[i].trim().startsWith("|")) {
        const row1 = parseTableRow(lines[i]);
        const row2 = parseTableRow(lines[i + 1] || "");
        const row3 = parseTableRow(lines[i + 2] || "");
        if (row1 && row2 && row3 && isTableDivider(row2)) {
          revisionRows.push({
            version: row3[0] || "",
            date: row3[1] || "",
            author: row3[2] || "",
            changes: row3[3] || "",
            document: documentTitle,
          });
          break;
        }
      }
      if (/^#{1,6}\s+/.test(lines[i])) {
        break;
      }
    }
  }

  return {
    fileName,
    projectTitle,
    documentTitle,
    revisionRows,
  };
}

function parseMarkdownDocument(fileName, text) {
  const metadata = extractMetadata(fileName, text);
  const lines = text.split("\n");
  const blocks = [];
  let i = 0;
  let orderedGroupCounter = 2;
  let currentOrderedNumId = null;
  let inListBlock = false;

  function isBlockStarter(line) {
    return (
      /^#{1,6}\s+/.test(line) ||
      /^```/.test(line) ||
      (/^\|.*\|\s*$/.test(line.trim()) && line.trim().startsWith("|")) ||
      /^(\s*)([-*]|\d+\.)\s+/.test(line) ||
      /^---+$/.test(line.trim())
    );
  }

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      inListBlock = false;
      currentOrderedNumId = null;
      i += 1;
      continue;
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      inListBlock = false;
      currentOrderedNumId = null;
      blocks.push({
        type: "heading",
        level: headingMatch[1].length,
        text: headingMatch[2].trim(),
      });
      i += 1;
      continue;
    }

    if (/^---+$/.test(line.trim())) {
      inListBlock = false;
      currentOrderedNumId = null;
      blocks.push({ type: "rule" });
      i += 1;
      continue;
    }

    const fenceMatch = line.match(/^```(.*)$/);
    if (fenceMatch) {
      inListBlock = false;
      currentOrderedNumId = null;
      const language = fenceMatch[1].trim().toLowerCase();
      i += 1;
      const codeLines = [];
      while (i < lines.length && !/^```/.test(lines[i])) {
        codeLines.push(lines[i]);
        i += 1;
      }
      if (i < lines.length) {
        i += 1;
      }
      blocks.push({
        type: "code",
        language,
        text: codeLines.join("\n"),
      });
      continue;
    }

    if (/^\|.*\|\s*$/.test(line.trim()) && line.trim().startsWith("|")) {
      inListBlock = false;
      currentOrderedNumId = null;
      const tableLines = [];
      while (
        i < lines.length &&
        /^\|.*\|\s*$/.test(lines[i].trim()) &&
        lines[i].trim().startsWith("|")
      ) {
        tableLines.push(lines[i]);
        i += 1;
      }
      const rows = tableLines
        .map(parseTableRow)
        .filter(Boolean)
        .filter((cells) => !isTableDivider(cells));
      if (rows.length > 0) {
        blocks.push({ type: "table", rows });
      }
      continue;
    }

    const listMatch = line.match(/^(\s*)([-*]|\d+\.)\s+(.*)$/);
    if (listMatch) {
      const indent = listMatch[1].replace(/\t/g, "    ").length;
      const level = Math.max(0, Math.floor(indent / 2));
      const marker = listMatch[2];
      const ordered = /\d+\./.test(marker);
      const textLines = [listMatch[3]];
      i += 1;

      while (i < lines.length) {
        const nextLine = lines[i];
        if (!nextLine.trim()) {
          break;
        }
        if (isBlockStarter(nextLine)) {
          break;
        }
        textLines.push(nextLine.trim());
        i += 1;
      }

      if (ordered) {
        if (!inListBlock || currentOrderedNumId === null) {
          currentOrderedNumId = orderedGroupCounter;
          orderedGroupCounter += 1;
        }
      }

      blocks.push({
        type: "listItem",
        ordered,
        level,
        numId: ordered ? currentOrderedNumId : 1,
        textLines,
      });

      inListBlock = true;
      continue;
    }

    inListBlock = false;
    currentOrderedNumId = null;
    const paragraphLines = [line];
    i += 1;
    while (i < lines.length) {
      const nextLine = lines[i];
      if (!nextLine.trim()) {
        break;
      }
      if (isBlockStarter(nextLine)) {
        break;
      }
      paragraphLines.push(nextLine);
      i += 1;
    }
    blocks.push({
      type: "paragraph",
      lines: paragraphLines,
    });
  }

  metadata.blocks = blocks;
  metadata.maxOrderedNumId = orderedGroupCounter - 1;
  return metadata;
}

function createInlineSegments(text) {
  const segments = [];
  let i = 0;
  let buffer = "";

  function flushBuffer() {
    if (buffer) {
      segments.push({ type: "text", text: buffer });
      buffer = "";
    }
  }

  while (i < text.length) {
    if (text.startsWith("**", i)) {
      const end = text.indexOf("**", i + 2);
      if (end !== -1) {
        flushBuffer();
        segments.push({
          type: "bold",
          children: createInlineSegments(text.slice(i + 2, end)),
        });
        i = end + 2;
        continue;
      }
    }

    if (text[i] === "`") {
      const end = text.indexOf("`", i + 1);
      if (end !== -1) {
        flushBuffer();
        segments.push({
          type: "code",
          text: text.slice(i + 1, end),
        });
        i = end + 1;
        continue;
      }
    }

    if (text[i] === "[") {
      const textEnd = text.indexOf("]", i + 1);
      if (textEnd !== -1 && text[textEnd + 1] === "(") {
        const urlEnd = text.indexOf(")", textEnd + 2);
        if (urlEnd !== -1) {
          flushBuffer();
          segments.push({
            type: "link",
            url: text.slice(textEnd + 2, urlEnd),
            children: createInlineSegments(text.slice(i + 1, textEnd)),
          });
          i = urlEnd + 1;
          continue;
        }
      }
    }

    if (text[i] === "*") {
      const end = text.indexOf("*", i + 1);
      if (end !== -1) {
        flushBuffer();
        segments.push({
          type: "italic",
          children: createInlineSegments(text.slice(i + 1, end)),
        });
        i = end + 1;
        continue;
      }
    }

    buffer += text[i];
    i += 1;
  }

  flushBuffer();
  return segments;
}

function rPrXml(options = {}) {
  const props = [];
  if (options.bold) props.push("<w:b/>");
  if (options.italic) props.push("<w:i/>");
  if (options.underline) props.push('<w:u w:val="single"/>');
  if (options.color) props.push(`<w:color w:val="${options.color}"/>`);
  if (options.font) {
    props.push(
      `<w:rFonts w:ascii="${xmlEscape(options.font)}" w:hAnsi="${xmlEscape(
        options.font
      )}" w:cs="${xmlEscape(options.font)}"/>`
    );
  }
  if (options.size) {
    props.push(`<w:sz w:val="${options.size}"/><w:szCs w:val="${options.size}"/>`);
  }
  if (options.noProof) props.push("<w:noProof/>");
  return props.length ? `<w:rPr>${props.join("")}</w:rPr>` : "";
}

function createRelationshipManager() {
  let counter = 3;
  const relationships = [
    {
      id: "rId1",
      type: "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header",
      target: "header1.xml",
    },
    {
      id: "rId2",
      type: "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer",
      target: "footer1.xml",
    },
  ];

  return {
    createHyperlink(url) {
      const id = `rId${counter}`;
      counter += 1;
      relationships.push({
        id,
        type: "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        target: url,
        targetMode: "External",
      });
      return id;
    },
    xml() {
      return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
${relationships
  .map((rel) => {
    const targetMode = rel.targetMode ? ` TargetMode="${rel.targetMode}"` : "";
    return `<Relationship Id="${rel.id}" Type="${rel.type}" Target="${xmlEscape(
      rel.target
    )}"${targetMode}/>`;
  })
  .join("\n")}
</Relationships>`;
    },
  };
}

function renderInlineSegments(segments, relationships, inherited = {}) {
  const xml = [];
  for (const segment of segments) {
    if (segment.type === "text") {
      if (!segment.text) continue;
      xml.push(
        `<w:r>${rPrXml(inherited)}<w:t xml:space="preserve">${xmlEscape(
          cleanText(segment.text)
        )}</w:t></w:r>`
      );
      continue;
    }

    if (segment.type === "bold") {
      xml.push(
        renderInlineSegments(segment.children, relationships, {
          ...inherited,
          bold: true,
        })
      );
      continue;
    }

    if (segment.type === "italic") {
      xml.push(
        renderInlineSegments(segment.children, relationships, {
          ...inherited,
          italic: true,
        })
      );
      continue;
    }

    if (segment.type === "code") {
      xml.push(
        `<w:r>${rPrXml({
          ...inherited,
          font: "Consolas",
          noProof: true,
        })}<w:t xml:space="preserve">${xmlEscape(cleanText(segment.text))}</w:t></w:r>`
      );
      continue;
    }

    if (segment.type === "link") {
      const relId = relationships.createHyperlink(segment.url);
      const inner = renderInlineSegments(segment.children, relationships, {
        ...inherited,
        color: HCL_BLUE,
        underline: true,
      });
      xml.push(`<w:hyperlink r:id="${relId}" w:history="1">${inner}</w:hyperlink>`);
    }
  }
  return xml.join("");
}

function renderParagraph(lines, relationships, options = {}) {
  const pPr = [];
  if (options.style) pPr.push(`<w:pStyle w:val="${options.style}"/>`);
  if (options.pageBreakBefore !== undefined) {
    pPr.push(`<w:pageBreakBefore w:val="${options.pageBreakBefore ? 1 : 0}"/>`);
  }
  if (options.align) pPr.push(`<w:jc w:val="${options.align}"/>`);
  if (options.spacingBefore || options.spacingAfter || options.line) {
    const before = options.spacingBefore || 0;
    const after = options.spacingAfter || 0;
    const line = options.line || 276;
    pPr.push(
      `<w:spacing w:before="${before}" w:after="${after}" w:line="${line}" w:lineRule="auto"/>`
    );
  }
  if (options.keepNext) pPr.push("<w:keepNext/>");
  if (options.keepLines) pPr.push("<w:keepLines/>");
  if (options.shading) {
    pPr.push(`<w:shd w:fill="${options.shading}" w:val="clear"/>`);
  }
  if (options.numId) {
    pPr.push(
      `<w:numPr><w:ilvl w:val="${options.ilvl || 0}"/><w:numId w:val="${
        options.numId
      }"/></w:numPr>`
    );
  }
  if (options.leftIndent || options.hangingIndent) {
    pPr.push(
      `<w:ind${
        options.leftIndent ? ` w:left="${options.leftIndent}"` : ""
      }${options.hangingIndent ? ` w:hanging="${options.hangingIndent}"` : ""}/>`
    );
  }
  if (options.borderBottom) {
    pPr.push(
      `<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="4" w:color="${options.borderBottom}"/></w:pBdr>`
    );
  }

  const runs = [];
  const textLines = Array.isArray(lines) ? lines : [lines];
  textLines.forEach((line, index) => {
    if (index > 0) {
      runs.push("<w:r><w:br/></w:r>");
    }
    runs.push(
      renderInlineSegments(createInlineSegments(cleanText(line)), relationships)
    );
  });

  return `<w:p>${pPr.length ? `<w:pPr>${pPr.join("")}</w:pPr>` : ""}${runs.join(
    ""
  )}</w:p>`;
}

function renderRawParagraph(text, options = {}) {
  const pPr = [];
  if (options.style) pPr.push(`<w:pStyle w:val="${options.style}"/>`);
  if (options.align) pPr.push(`<w:jc w:val="${options.align}"/>`);
  if (options.spacingBefore || options.spacingAfter || options.line) {
    pPr.push(
      `<w:spacing w:before="${options.spacingBefore || 0}" w:after="${
        options.spacingAfter || 0
      }" w:line="${options.line || 276}" w:lineRule="auto"/>`
    );
  }
  return `<w:p>${pPr.length ? `<w:pPr>${pPr.join("")}</w:pPr>` : ""}<w:r><w:t xml:space="preserve">${xmlEscape(
    cleanText(text)
  )}</w:t></w:r></w:p>`;
}

function renderPageBreak() {
  return "<w:p><w:r><w:br w:type=\"page\"/></w:r></w:p>";
}

function renderTable(rows, relationships, options = {}) {
  const colCount = rows.reduce((max, row) => Math.max(max, row.length), 0);
  const pageWidth = 9026;
  const defaultWidth = Math.floor(pageWidth / Math.max(1, colCount));
  const gridCols = new Array(colCount)
    .fill(0)
    .map(() => `<w:gridCol w:w="${defaultWidth}"/>`)
    .join("");

  const tblRows = rows
    .map((row, rowIndex) => {
      const cells = [];
      for (let i = 0; i < colCount; i += 1) {
        const text = row[i] || "";
        const cellShade =
          rowIndex === 0
            ? options.headerShade || HCL_LIGHT_BLUE
            : options.bodyShade || "";
        const paragraphs = renderParagraph([text], relationships, {
          align: "left",
          spacingAfter: 40,
          spacingBefore: 20,
          style: "Normal",
        });
        const tcPr = [
          `<w:tcW w:w="${defaultWidth}" w:type="dxa"/>`,
          "<w:vAlign w:val=\"top\"/>",
        ];
        if (cellShade) {
          tcPr.push(`<w:shd w:fill="${cellShade}" w:val="clear"/>`);
        }
        cells.push(`<w:tc><w:tcPr>${tcPr.join("")}</w:tcPr>${paragraphs}</w:tc>`);
      }
      return `<w:tr>${cells.join("")}</w:tr>`;
    })
    .join("");

  return `<w:tbl>
<w:tblPr>
  <w:tblW w:w="0" w:type="auto"/>
  <w:tblLayout w:type="fixed"/>
  <w:tblBorders>
    <w:top w:val="single" w:sz="8" w:space="0" w:color="${BORDER_GRAY}"/>
    <w:left w:val="single" w:sz="8" w:space="0" w:color="${BORDER_GRAY}"/>
    <w:bottom w:val="single" w:sz="8" w:space="0" w:color="${BORDER_GRAY}"/>
    <w:right w:val="single" w:sz="8" w:space="0" w:color="${BORDER_GRAY}"/>
    <w:insideH w:val="single" w:sz="6" w:space="0" w:color="${BORDER_GRAY}"/>
    <w:insideV w:val="single" w:sz="6" w:space="0" w:color="${BORDER_GRAY}"/>
  </w:tblBorders>
</w:tblPr>
<w:tblGrid>${gridCols}</w:tblGrid>
${tblRows}
</w:tbl>`;
}

function renderCodeBlock(codeText) {
  const escapedLines = codeText.split("\n");
  const runs = escapedLines
    .map((line, index) => {
      const prefix = index > 0 ? "<w:r><w:br/></w:r>" : "";
      return `${prefix}<w:r>${rPrXml({
        font: "Consolas",
        size: 19,
        noProof: true,
      })}<w:t xml:space="preserve">${xmlEscape(cleanText(line))}</w:t></w:r>`;
    })
    .join("");

  return `<w:p><w:pPr><w:pStyle w:val="CodeBlock"/><w:spacing w:before="60" w:after="120" w:line="240" w:lineRule="auto"/><w:ind w:left="360" w:right="360"/></w:pPr>${runs}</w:p>`;
}

function mermaidPlaceholder(codeText, headingContext) {
  const code = codeText.toLowerCase();
  const heading = String(headingContext || "").toLowerCase();
  if (code.includes("sequencediagram") || heading.includes("sequence")) {
    return "[Insert Sequence Diagram]";
  }
  if (heading.includes("deployment")) {
    return "[Insert Deployment Diagram]";
  }
  if (
    heading.includes("process") ||
    heading.includes("flow") ||
    heading.includes("conversation")
  ) {
    return "[Insert Sequence Diagram]";
  }
  if (
    heading.includes("architecture") ||
    heading.includes("architectural") ||
    heading.includes("logical view") ||
    heading.includes("component") ||
    heading.includes("use case")
  ) {
    return "[Insert Architecture Diagram]";
  }
  return "[Insert Architecture Diagram]";
}

function renderMermaidPlaceholder(label, relationships) {
  return renderParagraph([label], relationships, {
    style: "DiagramPlaceholder",
    align: "center",
    spacingBefore: 120,
    spacingAfter: 180,
  });
}

function createTocField() {
  return `<w:p>
  <w:pPr><w:pStyle w:val="Heading1"/><w:pageBreakBefore w:val="0"/></w:pPr>
  <w:r><w:fldChar w:fldCharType="begin"/></w:r>
  <w:r><w:instrText xml:space="preserve"> TOC \\o "1-3" \\h \\z \\u </w:instrText></w:r>
  <w:r><w:fldChar w:fldCharType="separate"/></w:r>
  <w:r><w:t> </w:t></w:r>
  <w:r><w:fldChar w:fldCharType="end"/></w:r>
</w:p>`;
}

function createStylesXml() {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>
        <w:sz w:val="22"/>
        <w:szCs w:val="22"/>
        <w:lang w:val="en-US"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:after="120" w:line="276" w:lineRule="auto"/>
        <w:jc w:val="both"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>

  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:after="120" w:line="276" w:lineRule="auto"/>
      <w:jc w:val="both"/>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>
      <w:sz w:val="22"/>
      <w:szCs w:val="22"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:before="0" w:after="180" w:line="300" w:lineRule="auto"/>
      <w:jc w:val="center"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:color w:val="${HCL_BLUE}"/>
      <w:sz w:val="36"/>
      <w:szCs w:val="36"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="SubTitle">
    <w:name w:val="SubTitle"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:after="120" w:line="276" w:lineRule="auto"/>
      <w:jc w:val="center"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:color w:val="${HCL_BLUE}"/>
      <w:sz w:val="26"/>
      <w:szCs w:val="26"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="DocHeading">
    <w:name w:val="Document Heading"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:outlineLvl w:val="0"/>
      <w:spacing w:before="120" w:after="120" w:line="276" w:lineRule="auto"/>
      <w:keepNext/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:color w:val="${HCL_BLUE}"/>
      <w:sz w:val="30"/>
      <w:szCs w:val="30"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="FrontMatterHeading">
    <w:name w:val="Front Matter Heading"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:before="120" w:after="80" w:line="276" w:lineRule="auto"/>
      <w:keepNext/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:color w:val="${HCL_BLUE}"/>
      <w:sz w:val="24"/>
      <w:szCs w:val="24"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:uiPriority w:val="9"/>
    <w:qFormat/>
    <w:pPr>
      <w:outlineLvl w:val="0"/>
      <w:pageBreakBefore/>
      <w:keepNext/>
      <w:spacing w:before="240" w:after="120" w:line="300" w:lineRule="auto"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:color w:val="${HCL_BLUE}"/>
      <w:sz w:val="30"/>
      <w:szCs w:val="30"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:uiPriority w:val="9"/>
    <w:qFormat/>
    <w:pPr>
      <w:outlineLvl w:val="1"/>
      <w:keepNext/>
      <w:spacing w:before="180" w:after="80" w:line="276" w:lineRule="auto"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:color w:val="${HCL_BLUE}"/>
      <w:sz w:val="26"/>
      <w:szCs w:val="26"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:uiPriority w:val="9"/>
    <w:qFormat/>
    <w:pPr>
      <w:outlineLvl w:val="2"/>
      <w:keepNext/>
      <w:spacing w:before="120" w:after="60" w:line="276" w:lineRule="auto"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:color w:val="${HCL_BLUE}"/>
      <w:sz w:val="22"/>
      <w:szCs w:val="22"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="CodeBlock">
    <w:name w:val="Code Block"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:spacing w:before="60" w:after="120" w:line="240" w:lineRule="auto"/>
      <w:jc w:val="left"/>
      <w:shd w:fill="${LIGHT_GRAY}" w:val="clear"/>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/>
      <w:sz w:val="19"/>
      <w:szCs w:val="19"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="DiagramPlaceholder">
    <w:name w:val="Diagram Placeholder"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:spacing w:before="120" w:after="180" w:line="276" w:lineRule="auto"/>
      <w:jc w:val="center"/>
      <w:shd w:fill="${LIGHT_GRAY}" w:val="clear"/>
      <w:pBdr>
        <w:top w:val="single" w:sz="6" w:space="4" w:color="${BORDER_GRAY}"/>
        <w:left w:val="single" w:sz="6" w:space="4" w:color="${BORDER_GRAY}"/>
        <w:bottom w:val="single" w:sz="6" w:space="4" w:color="${BORDER_GRAY}"/>
        <w:right w:val="single" w:sz="6" w:space="4" w:color="${BORDER_GRAY}"/>
      </w:pBdr>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:i/>
      <w:color w:val="${HCL_BLUE}"/>
      <w:sz w:val="22"/>
      <w:szCs w:val="22"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Header">
    <w:name w:val="Header"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:jc w:val="left"/>
      <w:spacing w:after="40" w:line="240" w:lineRule="auto"/>
    </w:pPr>
    <w:rPr>
      <w:color w:val="${HCL_BLUE}"/>
      <w:sz w:val="18"/>
      <w:szCs w:val="18"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Footer">
    <w:name w:val="Footer"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:jc w:val="right"/>
      <w:spacing w:before="40" w:after="0" w:line="240" w:lineRule="auto"/>
    </w:pPr>
    <w:rPr>
      <w:sz w:val="18"/>
      <w:szCs w:val="18"/>
    </w:rPr>
  </w:style>
</w:styles>`;
}

function createNumberingXml(maxNumId) {
  const nums = ['<w:num w:numId="1"><w:abstractNumId w:val="1"/></w:num>'];
  for (let i = 2; i <= maxNumId; i += 1) {
    nums.push(`<w:num w:numId="${i}"><w:abstractNumId w:val="2"/></w:num>`);
  }

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="1">
    <w:multiLevelType w:val="hybridMultilevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="bullet"/>
      <w:lvlText w:val="•"/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>
      <w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/></w:rPr>
    </w:lvl>
    <w:lvl w:ilvl="1">
      <w:start w:val="1"/>
      <w:numFmt w:val="bullet"/>
      <w:lvlText w:val="o"/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="1080" w:hanging="360"/></w:pPr>
    </w:lvl>
    <w:lvl w:ilvl="2">
      <w:start w:val="1"/>
      <w:numFmt w:val="bullet"/>
      <w:lvlText w:val="▪"/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="1440" w:hanging="360"/></w:pPr>
    </w:lvl>
  </w:abstractNum>

  <w:abstractNum w:abstractNumId="2">
    <w:multiLevelType w:val="multilevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="decimal"/>
      <w:lvlText w:val="%1."/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>
    </w:lvl>
    <w:lvl w:ilvl="1">
      <w:start w:val="1"/>
      <w:numFmt w:val="decimal"/>
      <w:lvlText w:val="%1.%2."/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="1080" w:hanging="360"/></w:pPr>
    </w:lvl>
    <w:lvl w:ilvl="2">
      <w:start w:val="1"/>
      <w:numFmt w:val="decimal"/>
      <w:lvlText w:val="%1.%2.%3."/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="1440" w:hanging="360"/></w:pPr>
    </w:lvl>
  </w:abstractNum>

  ${nums.join("\n  ")}
</w:numbering>`;
}

function createSettingsXml() {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:zoom w:percent="100"/>
  <w:updateFields w:val="true"/>
</w:settings>`;
}

function createHeaderXml(projectTitle) {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p>
    <w:pPr>
      <w:pStyle w:val="Header"/>
      <w:spacing w:after="40" w:line="240" w:lineRule="auto"/>
      <w:pBdr><w:bottom w:val="single" w:sz="8" w:space="4" w:color="${HCL_BLUE}"/></w:pBdr>
    </w:pPr>
    <w:r>${rPrXml({ bold: true, color: HCL_BLUE, size: 18 })}<w:t xml:space="preserve">HCL  |  ${xmlEscape(
      cleanText(projectTitle)
    )}</w:t></w:r>
  </w:p>
</w:hdr>`;
}

function createFooterXml(version) {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p>
    <w:pPr>
      <w:pStyle w:val="Footer"/>
      <w:jc w:val="right"/>
      <w:pBdr><w:top w:val="single" w:sz="6" w:space="4" w:color="${BORDER_GRAY}"/></w:pBdr>
    </w:pPr>
    <w:r>${rPrXml({ size: 18 })}<w:t xml:space="preserve">Version ${xmlEscape(
      version
    )}  |  Page </w:t></w:r>
    <w:fldSimple w:instr=" PAGE "/>
  </w:p>
</w:ftr>`;
}

function createCoreXml(title, authors, dateValue) {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>${xmlEscape(cleanText(title))}</dc:title>
  <dc:creator>${xmlEscape(cleanText(authors.join("; ")))}</dc:creator>
  <cp:lastModifiedBy>${xmlEscape(cleanText(authors.join("; ")))}</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">${xmlEscape(dateValue)}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">${xmlEscape(dateValue)}</dcterms:modified>
</cp:coreProperties>`;
}

function createAppXml() {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex Enterprise Document Formatter</Application>
  <DocSecurity>0</DocSecurity>
  <ScaleCrop>false</ScaleCrop>
  <HeadingPairs>
    <vt:vector size="2" baseType="variant">
      <vt:variant><vt:lpstr>Title</vt:lpstr></vt:variant>
      <vt:variant><vt:i4>1</vt:i4></vt:variant>
    </vt:vector>
  </HeadingPairs>
  <TitlesOfParts>
    <vt:vector size="1" baseType="lpstr">
      <vt:lpstr>Document</vt:lpstr>
    </vt:vector>
  </TitlesOfParts>
  <Company>HCL</Company>
  <LinksUpToDate>false</LinksUpToDate>
  <SharedDoc>false</SharedDoc>
  <HyperlinksChanged>false</HyperlinksChanged>
  <AppVersion>16.0000</AppVersion>
</Properties>`;
}

function createRootRelsXml() {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>`;
}

function createContentTypesXml() {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
  <Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
  <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>`;
}

function createDocumentXml(parsedDocs, masterMeta, relationships) {
  const body = [];

  body.push(
    renderParagraph(["HCL"], relationships, {
      style: "Title",
      align: "center",
      spacingAfter: 80,
    })
  );
  body.push(
    renderParagraph([masterMeta.projectTitle], relationships, {
      style: "Title",
      align: "center",
      spacingAfter: 120,
    })
  );
  body.push(
    renderParagraph(
      [masterMeta.documentTitles.join(" | ")],
      relationships,
      {
        style: "SubTitle",
        align: "center",
        spacingAfter: 240,
      }
    )
  );

  const titleTableRows = [
    ["Document Title", masterMeta.projectTitle],
    ["Project Name", masterMeta.projectTitle],
    ["Version", masterMeta.version],
    ["Author", masterMeta.authors.join("; ")],
    ["Date", masterMeta.date],
    ["Company", "HCL"],
  ];
  body.push(
    renderTable(titleTableRows, relationships, {
      headerShade: HCL_LIGHT_BLUE,
      bodyShade: "",
    })
  );

  body.push(renderPageBreak());

  body.push(
    renderParagraph(["Revision History"], relationships, {
      style: "Heading1",
      pageBreakBefore: false,
    })
  );
  body.push(
    renderTable(
      [
        [
          "Document",
          "Version No",
          "Date",
          "Prepared by / Modified by",
          "Significant Changes",
        ],
        ...masterMeta.revisionRows.map((row) => [
          row.document,
          row.version,
          row.date,
          row.author,
          row.changes,
        ]),
      ],
      relationships,
      { headerShade: HCL_LIGHT_BLUE }
    )
  );

  body.push(renderPageBreak());

  body.push(
    renderParagraph(["Table of Contents"], relationships, {
      style: "Heading1",
      pageBreakBefore: false,
    })
  );
  body.push(createTocField());

  parsedDocs.forEach((doc, docIndex) => {
    body.push(renderPageBreak());

    let currentHeadingContext = doc.documentTitle;
    let seenNumberedSection = false;
    let sawProjectTitle = false;
    let sawDocumentTitle = false;

    for (const block of doc.blocks) {
      if (block.type === "heading") {
        const text = block.text;
        if (/^\d+(\.\d+)*\s+/.test(text)) {
          seenNumberedSection = true;
        }

        let style = "Normal";
        let pageBreakBefore = undefined;

        if (block.level === 1 && !sawProjectTitle) {
          style = "Title";
          sawProjectTitle = true;
        } else if (block.level === 2 && !sawDocumentTitle) {
          style = "DocHeading";
          sawDocumentTitle = true;
        } else if (
          block.level === 2 &&
          !seenNumberedSection &&
          (text === "Revision History" || text === "Table of Contents")
        ) {
          style = "FrontMatterHeading";
        } else if (block.level === 2) {
          style = "Heading1";
        } else if (block.level === 3) {
          style = "Heading2";
        } else if (block.level >= 4) {
          style = "Heading3";
        }

        if (style !== "Heading1") {
          pageBreakBefore = false;
        }

        body.push(
          renderParagraph([text], relationships, {
            style,
            pageBreakBefore,
          })
        );
        currentHeadingContext = text;
        continue;
      }

      if (block.type === "rule") {
        body.push(renderRawParagraph("", { spacingAfter: 40 }));
        continue;
      }

      if (block.type === "paragraph") {
        body.push(
          renderParagraph(block.lines, relationships, {
            style: "Normal",
          })
        );
        continue;
      }

      if (block.type === "listItem") {
        body.push(
          renderParagraph(block.textLines, relationships, {
            style: "Normal",
            numId: block.numId,
            ilvl: Math.min(block.level, 2),
            leftIndent: 720 + Math.min(block.level, 2) * 360,
            hangingIndent: 360,
            spacingAfter: 60,
          })
        );
        continue;
      }

      if (block.type === "table") {
        body.push(renderTable(block.rows, relationships, { headerShade: HCL_LIGHT_BLUE }));
        continue;
      }

      if (block.type === "code") {
        if (block.language === "mermaid") {
          body.push(
            renderMermaidPlaceholder(
              mermaidPlaceholder(block.text, currentHeadingContext),
              relationships
            )
          );
        } else {
          body.push(renderCodeBlock(block.text));
        }
      }
    }
  });

  body.push(`<w:sectPr>
    <w:headerReference w:type="default" r:id="rId1"/>
    <w:footerReference w:type="default" r:id="rId2"/>
    <w:pgSz w:w="11906" w:h="16838"/>
    <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
    <w:cols w:space="720"/>
    <w:docGrid w:linePitch="360"/>
  </w:sectPr>`);

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:w10="urn:schemas-microsoft-com:office:word" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" mc:Ignorable="w14 wp14">
  <w:body>
    ${body.join("\n")}
  </w:body>
</w:document>`;
}

function makeDosDateTime(date = new Date()) {
  let year = date.getFullYear();
  if (year < 1980) year = 1980;
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const hours = date.getHours();
  const minutes = date.getMinutes();
  const seconds = Math.floor(date.getSeconds() / 2);
  const dosTime = (hours << 11) | (minutes << 5) | seconds;
  const dosDate = ((year - 1980) << 9) | (month << 5) | day;
  return { dosTime, dosDate };
}

function createCrc32Table() {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i += 1) {
    let c = i;
    for (let j = 0; j < 8; j += 1) {
      c = (c & 1) ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    table[i] = c >>> 0;
  }
  return table;
}

const CRC32_TABLE = createCrc32Table();

function crc32(buffer) {
  let crc = 0xffffffff;
  for (let i = 0; i < buffer.length; i += 1) {
    crc = CRC32_TABLE[(crc ^ buffer[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function writeUInt64LEUnsupported() {
  throw new Error("Zip64 is not supported for this generator.");
}

function createZip(entries) {
  const localParts = [];
  const centralParts = [];
  let offset = 0;
  const now = makeDosDateTime(new Date());

  for (const entry of entries) {
    const nameBuffer = Buffer.from(entry.name.replace(/\\/g, "/"), "utf8");
    const dataBuffer = Buffer.isBuffer(entry.data)
      ? entry.data
      : Buffer.from(entry.data, "utf8");
    const checksum = crc32(dataBuffer);

    if (
      nameBuffer.length > 0xffff ||
      dataBuffer.length > 0xffffffff ||
      offset > 0xffffffff
    ) {
      writeUInt64LEUnsupported();
    }

    const localHeader = Buffer.alloc(30);
    localHeader.writeUInt32LE(0x04034b50, 0);
    localHeader.writeUInt16LE(20, 4);
    localHeader.writeUInt16LE(0x0800, 6);
    localHeader.writeUInt16LE(0, 8);
    localHeader.writeUInt16LE(now.dosTime, 10);
    localHeader.writeUInt16LE(now.dosDate, 12);
    localHeader.writeUInt32LE(checksum, 14);
    localHeader.writeUInt32LE(dataBuffer.length, 18);
    localHeader.writeUInt32LE(dataBuffer.length, 22);
    localHeader.writeUInt16LE(nameBuffer.length, 26);
    localHeader.writeUInt16LE(0, 28);

    localParts.push(localHeader, nameBuffer, dataBuffer);

    const centralHeader = Buffer.alloc(46);
    centralHeader.writeUInt32LE(0x02014b50, 0);
    centralHeader.writeUInt16LE(20, 4);
    centralHeader.writeUInt16LE(20, 6);
    centralHeader.writeUInt16LE(0x0800, 8);
    centralHeader.writeUInt16LE(0, 10);
    centralHeader.writeUInt16LE(now.dosTime, 12);
    centralHeader.writeUInt16LE(now.dosDate, 14);
    centralHeader.writeUInt32LE(checksum, 16);
    centralHeader.writeUInt32LE(dataBuffer.length, 20);
    centralHeader.writeUInt32LE(dataBuffer.length, 24);
    centralHeader.writeUInt16LE(nameBuffer.length, 28);
    centralHeader.writeUInt16LE(0, 30);
    centralHeader.writeUInt16LE(0, 32);
    centralHeader.writeUInt16LE(0, 34);
    centralHeader.writeUInt16LE(0, 36);
    centralHeader.writeUInt32LE(0, 38);
    centralHeader.writeUInt32LE(offset, 42);

    centralParts.push(centralHeader, nameBuffer);
    offset += localHeader.length + nameBuffer.length + dataBuffer.length;
  }

  const centralDirectory = Buffer.concat(centralParts);
  const localDirectory = Buffer.concat(localParts);
  const endRecord = Buffer.alloc(22);
  endRecord.writeUInt32LE(0x06054b50, 0);
  endRecord.writeUInt16LE(0, 4);
  endRecord.writeUInt16LE(0, 6);
  endRecord.writeUInt16LE(entries.length, 8);
  endRecord.writeUInt16LE(entries.length, 10);
  endRecord.writeUInt32LE(centralDirectory.length, 12);
  endRecord.writeUInt32LE(localDirectory.length, 16);
  endRecord.writeUInt16LE(0, 20);

  return Buffer.concat([localDirectory, centralDirectory, endRecord]);
}

function buildMasterMetadata(parsedDocs) {
  const projectTitle = parsedDocs[0]?.projectTitle || "Enterprise Document";
  const documentTitles = parsedDocs.map((doc) => doc.documentTitle);
  const revisionRows = parsedDocs.flatMap((doc) => doc.revisionRows);
  const authors = dedupe(revisionRows.map((row) => row.author));
  const version = dedupe(revisionRows.map((row) => row.version))[0] || "1.0";
  const date = dedupe(revisionRows.map((row) => row.date))[0] || "2026-06-13";
  return {
    projectTitle,
    documentTitles,
    revisionRows,
    authors,
    version,
    date,
  };
}

function main() {
  const parsedDocs = SOURCE_FILES.map((fileName) =>
    parseMarkdownDocument(fileName, readMarkdown(fileName))
  );
  const masterMeta = buildMasterMetadata(parsedDocs);
  const relationships = createRelationshipManager();
  const documentXml = createDocumentXml(parsedDocs, masterMeta, relationships);
  const maxNumId = Math.max(
    2,
    ...parsedDocs.map((doc) => doc.maxOrderedNumId || 2)
  );

  const entries = [
    { name: "[Content_Types].xml", data: createContentTypesXml() },
    { name: "_rels/.rels", data: createRootRelsXml() },
    {
      name: "docProps/core.xml",
      data: createCoreXml(
        masterMeta.projectTitle,
        masterMeta.authors,
        formatIsoDate(masterMeta.date)
      ),
    },
    { name: "docProps/app.xml", data: createAppXml() },
    { name: "word/document.xml", data: documentXml },
    { name: "word/styles.xml", data: createStylesXml() },
    { name: "word/numbering.xml", data: createNumberingXml(maxNumId) },
    { name: "word/settings.xml", data: createSettingsXml() },
    { name: "word/header1.xml", data: createHeaderXml(masterMeta.projectTitle) },
    { name: "word/footer1.xml", data: createFooterXml(masterMeta.version) },
    { name: "word/_rels/document.xml.rels", data: relationships.xml() },
  ];

  const zipBuffer = createZip(entries);
  fs.writeFileSync(OUTPUT_FILE, zipBuffer);
  console.log(OUTPUT_FILE);
}

main();
