#!/usr/bin/env python3
"""
Build ~50-page Orange-themed PFE DOCX from the linked backup:
- Keeps narrative content from rapport_pfe_big_data_orange_linked_revised.backup-2026-05-02.docx
- Replaces every inline figure with a bordered reserved area + caption
- Replaces five dense paragraphs with diagram reservation blocks
- Patches theme accents to Orange and inserts annex text before General Conclusion

Run from repo root:
  python3 scripts/build_pfe_50page_orange_placeholders.py
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from docx.oxml import parse_xml
from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
NSMAP = {"w": W_NS, "w14": W14_NS}


def qn(tag: str) -> str:
    prefix, local = tag.split(":")
    uri = NSMAP.get(prefix)
    if uri is None:
        raise ValueError(tag)
    return f"{{{uri}}}{local}"


def _p(text: str, *, bold: bool = False, color: str | None = "FF7900", size: int | None = 24, after_twips: int | None = None) -> etree._Element:
    """Minimal paragraph with optional spacing after (twips)."""
    esc = xml_escape(text)
    sa = f'<w:spacing w:after="{after_twips}"/>' if after_twips else ""
    b = "<w:b/>" if bold else ""
    clr = f'<w:color w:val="{color}"/>' if color else ""
    sz = f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>' if size else ""
    xml = (
        f'<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        f'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml">'
        f"<w:pPr><w:pStyle w:val=\"Normal\"/>{sa}</w:pPr>"
        f"<w:r><w:rPr>{b}{clr}{sz}</w:rPr><w:t xml:space=\"preserve\">{esc}</w:t></w:r>"
        f"</w:p>"
    )
    return parse_xml(xml)


def _diagram_block(title: str, guidance: str) -> list[etree._Element]:
    """Orange-bordered style via spacing + bold title + body (theme-aligned)."""
    border_note = (
        "Reserved diagram area (recommended export: landscape or 16:9 PNG, min. width 1400 px). "
        "Paste the finished figure here and delete this note."
    )
    return [
        _p(title, bold=True, color="FF7900", size=28, after_twips=120),
        _p(guidance, bold=False, color="000000", size=22, after_twips=360),
        _p(border_note, bold=False, color="666666", size=20, after_twips=7200),
        _p("", color=None, size=8, after_twips=400),
    ]


DIAGRAM_SWAPS: dict[int, tuple[str, str]] = {
    88: (
        "Diagram reservation — end-to-end platform overview",
        "Replace the introductory abstract block with a single architecture diagram: data sources (FES/VIP/GP/…), "
        "parsers, Elasticsearch indices, FastAPI services, React UI, and Kibana dashboards. Keep captions bilingual if required.",
    ),
    123: (
        "Diagram reservation — Chapter 1 context (company + mail flow)",
        "Use an organization + mail-path swim-lane: customer incident → N1/N2 → fragmented logs across server families → desired unified journey view.",
    ),
    233: (
        "Diagram reservation — Chapter 2 technology rationale",
        "Provide a decision tree or comparison matrix figure summarizing Elasticsearch vs Splunk/Solr, FastAPI vs Django/Flask, React vs Angular/Vue, Kibana vs Grafana.",
    ),
    421: (
        "Diagram reservation — Chapter 3 requirements & threats",
        "UML is optional; a threat-model sketch (assets, attackers, mitigations) plus a simplified deployment view is enough for readers who skip long prose.",
    ),
    682: (
        "Diagram reservation — DNSBL monitoring path",
        "Show how infrastructure IPs are checked against DNSBL lists, where alerts are emitted, and how operators reconcile blacklist hits with mail logs.",
    ),
}


ANNEX_PARAGRAPHS: list[str] = [
    (
        "Annex A — How to read this document and use placeholders. "
        "Every former screenshot is now an orange-titled reserved block followed by vertical space so pagination stays stable when you paste images. "
        "Keep figure numbering consistent with the main text captions; if Word renumbers automatically, update the List of Figures last."
    ),
    (
        "Annex B — Operational context for Orange Tunisia mail platforms. "
        "Corporate mail volume is split across several server families; identifiers differ between hops (queue id, delivery id, relay markers). "
        "This annex restates, in plain language, why correlation must be automated: humans cannot reliably stitch multi-gigabyte files under incident pressure."
    ),
    (
        "Annex C — Data handling, retention, and access control reminders. "
        "Production logs may contain personal metadata; restrict exports, prefer role-based access, and document who can run bulk searches. "
        "JWT-protected APIs and indexed storage do not remove the need for governance: define indices, ILM policies, and audit trails before scaling ingestion."
    ),
    (
        "Annex D — Ingestion workflow (batch vs near-real-time). "
        "The internship stack is oriented around batch parsing by day because archives arrive as files; near-real-time tailing is possible but changes failure modes "
        "(partial files, back-pressure, duplicate detection). If you extend the system, add idempotent writes and explicit watermarks per source host."
    ),
    (
        "Annex E — Elasticsearch index hygiene for log analytics. "
        "Prefer daily indices for mail logs, map important fields explicitly, and avoid unbounded keyword fields on noisy lines. "
        "Use index templates, ILM to roll warm→cold tiers, and snapshot policies that match your compliance window."
    ),
    (
        "Annex F — Operator UX checklist for the React application. "
        "Saved filters, readable timestamps, copy-to-clipboard for IDs, and clear empty states reduce support load. "
        "Pair the simple UI with Kibana for exploratory analysis; do not duplicate advanced charting in React unless product owners require it."
    ),
    (
        "Annex G — Benchmarking notes (repeatable measurements). "
        "When you replace placeholders with final screenshots, also capture machine specs, index size, shard count, query text, and cache state. "
        "Publish median and p95 latencies rather than single best-case numbers."
    ),
    (
        "Annex H — Failure modes during parsing. "
        "Clock skew across hosts, truncated files, antivirus re-scan lines, and non-standard relay formats can break correlation heuristics. "
        "Keep a quarantine index for malformed documents and surface parser version in each stored record for traceability."
    ),
    (
        "Annex I — Security testing backlog. "
        "Beyond functional tests, validate JWT expiry/refresh, rate limits on expensive queries, and SSRF risks if Kibana embedding URLs are configurable. "
        "Document dependency upgrades (FastAPI, Uvicorn, Elastic client) with smoke tests against a cloned index."
    ),
    (
        "Annex J — Glossary expansion for non-specialist readers. "
        "SMTP governs mail transfer; Postfix identifiers name different stages; DNSBL lists score IP reputation; Elasticsearch stores inverted indexes for fast search; "
        "Kibana visualizes the same indices. This annex exists so Chapter 2 can stay comparative while newcomers still find definitions."
    ),
    (
        "Annex K — Scrum delivery notes aligned with the internship cadence. "
        "Two-week sprints with a product owner from operations reduce the risk of building the wrong dashboards. "
        "Definition of done should include sample queries, documentation screenshots (to be pasted in reserved areas), and a rollback plan for index mapping changes."
    ),
    (
        "Annex L — Future work roadmap. "
        "Streaming ingestion, anomaly detection on rejection rates, richer Kaspersky bridge diagnostics, and automated customer-facing summaries are natural extensions. "
        "Prioritize items that reduce mean time to resolution before purely cosmetic chart polish."
    ),
    (
        "Annex M — Docker Compose layout and reproducibility. "
        "The lab stack typically bundles Elasticsearch, Kibana, FastAPI, and the React build behind a compose file so reviewers can boot the same ports and volumes. "
        "Document environment variables for Elastic security, bind mounts for log samples, and memory limits: Elasticsearch is sensitive to heap sizing; under-provisioning causes merge throttling that skews benchmarks."
    ),
    (
        "Annex N — Observability for the parsers themselves. "
        "Emit structured logs from ingestion jobs (start/end timestamps, file counts, failure reasons) to a separate index or file sink. "
        "When operators only watch the mail-data index, silent parser regressions go unnoticed until documents are missing from searches."
    ),
    (
        "Annex O — Change management for mapping updates. "
        "Reindexing is expensive at telecom log volumes; prefer additive fields and multi-fields over destructive type changes. "
        "Version every mapping change in git, run a shadow index with a 1% sample, and compare query results before cutover."
    ),
    (
        "Annex P — UI accessibility and language policy. "
        "If the product serves mixed French/English teams, keep labels consistent and avoid hard-coded strings in screenshots you will paste later. "
        "High-contrast Orange on white is readable, but never rely on color alone to encode status; pair with icons or text."
    ),
    (
        "Annex Q — Handover checklist for the next maintainer. "
        "Repository URL, Elastic cluster addresses (lab vs prod), credential rotation owners, backup locations for raw archives, and on-call escalation paths should live in one internal page linked from the README. "
        "This report’s placeholders are intentionally generous so final visuals can be dropped in without reflowing captions."
    ),
    (
        "Annex R — Suggested diagram tooling. "
        "Draw.io or Visio for architecture, Mermaid for sequence sketches exported to SVG, and Elastic screenshots for Discover/Lens panels keep a coherent visual language. "
        "Export at 144–192 dpi for print clarity; crop whitespace to avoid shrinking readable text."
    ),
    (
        "Annex S — Ethics and customer data minimization. "
        "When demonstrating the platform, redact domains, mailbox names, and message bodies in screenshots unless legal approval exists. "
        "Synthetic fixtures that preserve log line grammar are preferable for public annexes."
    ),
    (
        "Annex T — Incident post-mortem template tied to the platform. "
        "For each major ticket, record query IDs, time range, indices touched, root cause class (network, reputation, user error, infrastructure), and whether automation could have shortened detection. "
        "Feeding those fields back into dashboards closes the loop between operations and engineering priorities."
    ),
]


def _replace_paragraph_with_diagram_siblings(body: etree._Element, target_wp: etree._Element, title: str, guidance: str) -> None:
    """Remove target paragraph and insert diagram block paragraphs before its position."""
    idx = body.index(target_wp)
    body.remove(target_wp)
    new_ps = _diagram_block(title, guidance)
    for j, np in enumerate(new_ps):
        body.insert(idx + j, np)


def _remove_drawings_and_placeholder(root: etree._Element) -> int:
    """Remove all w:drawing nodes; insert orange placeholder text into their runs. Returns figure count."""
    fig = 0
    for drawing in root.xpath(".//w:drawing", namespaces=NSMAP):
        fig += 1
        parent = drawing.getparent()
        if parent is None:
            continue
        parent.remove(drawing)
        # parent is usually w:r
        if etree.QName(parent).localname != "r":
            continue
        # add text run if no w:t remains with content
        has_text = False
        for t in parent.xpath("./w:t", namespaces=NSMAP):
            if (t.text or "").strip():
                has_text = True
                break
        if not has_text:
            t_el = etree.SubElement(parent, qn("w:t"))
            t_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            t_el.text = (
                f"[Figure {fig} — reserved screenshot area] "
                f"Insert the final capture here (UI, Kibana board, UML export, or server diagram)."
            )
        wp = parent.getparent()
        while wp is not None and etree.QName(wp).localname != "p":
            wp = wp.getparent()
        if wp is not None:
            p_pr = wp.find(qn("w:pPr"))
            if p_pr is None:
                p_pr = etree.SubElement(wp, qn("w:pPr"))
            spacing = p_pr.find(qn("w:spacing"))
            if spacing is None:
                spacing = etree.SubElement(p_pr, qn("w:spacing"))
            spacing.set(qn("w:after"), "6480")  # ~11.4 cm reserved vertical space after each figure caption line
    return fig


def _patch_orange_theme(theme_xml: bytes) -> bytes:
    s = theme_xml.decode("utf-8")
    # Office accent slots → Orange palette
    s = s.replace('<a:accent1><a:srgbClr val="4F81BD"/></a:accent1>', '<a:accent1><a:srgbClr val="FF7900"/></a:accent1>')
    s = s.replace('<a:accent2><a:srgbClr val="C0504D"/></a:accent2>', '<a:accent2><a:srgbClr val="E56A00"/></a:accent2>')
    s = s.replace('<a:accent3><a:srgbClr val="9BBB59"/></a:accent3>', '<a:accent3><a:srgbClr val="F5A623"/></a:accent3>')
    s = s.replace('<a:accent4><a:srgbClr val="8064A2"/></a:accent4>', '<a:accent4><a:srgbClr val="FFB84D"/></a:accent4>')
    s = s.replace('<a:accent5><a:srgbClr val="4BACC6"/></a:accent5>', '<a:accent5><a:srgbClr val="CC5C00"/></a:accent5>')
    s = s.replace('<a:accent6><a:srgbClr val="F79646"/></a:accent6>', '<a:accent6><a:srgbClr val="A34700"/></a:accent6>')
    s = s.replace('<a:hlink><a:srgbClr val="0000FF"/></a:hlink>', '<a:hlink><a:srgbClr val="CC5C00"/></a:hlink>')
    return s.encode("utf-8")


def _find_block_paragraphs(body: etree._Element) -> list[etree._Element]:
    ps: list[etree._Element] = []
    for child in body:
        tag = etree.QName(child).localname
        if tag == "p":
            ps.append(child)
        elif tag == "tbl":
            ps.append(child)
    return ps


def _paragraph_plain_text(wp: etree._Element) -> str:
    parts: list[str] = []
    for t in wp.xpath(".//w:t", namespaces=NSMAP):
        parts.append(t.text or "")
    return "".join(parts)


def build(src: Path, dst: Path) -> None:
    buf = io.BytesIO(src.read_bytes())
    zin = zipfile.ZipFile(buf, "r")
    zout_buf = io.BytesIO()
    zout = zipfile.ZipFile(zout_buf, "w", compression=zipfile.ZIP_DEFLATED)

    doc_xml = zin.read("word/document.xml")
    root = etree.fromstring(doc_xml)
    body = root.find(qn("w:body"))
    if body is None:
        raise SystemExit("word/document.xml missing w:body")

    blocks = _find_block_paragraphs(body)

    # Replace five complex paragraphs with multi-paragraph diagram reservations (reverse index to keep positions stable)
    for idx in sorted(DIAGRAM_SWAPS.keys(), reverse=True):
        title, guidance = DIAGRAM_SWAPS[idx]
        if idx >= len(blocks):
            raise SystemExit(f"diagram index {idx} out of range ({len(blocks)})")
        target = blocks[idx]
        if etree.QName(target).localname != "p":
            raise SystemExit(f"block {idx} is not a paragraph")
        _replace_paragraph_with_diagram_siblings(body, target, title, guidance)
        blocks = _find_block_paragraphs(body)

    # Figures → text placeholders + spacing
    fig_count = _remove_drawings_and_placeholder(root)

    # Re-scan blocks to insert annex before General Conclusion
    blocks = _find_block_paragraphs(body)
    insert_at = None
    for i, el in enumerate(blocks):
        if etree.QName(el).localname != "p":
            continue
        txt = _paragraph_plain_text(el).strip()
        if txt.startswith("General Conclusion"):
            insert_at = body.index(el)
            break
    if insert_at is None:
        raise SystemExit("Could not find 'General Conclusion' anchor paragraph")

    annex_elems: list[etree._Element] = [
        _p("Annexes — supplementary material", bold=True, color="FF7900", size=32, after_twips=240),
        _p(
            "The following annexes add reading guidance, governance, and engineering notes while keeping the main chapters "
            "aligned with the backup report. They also help reach the target page length without removing technical depth.",
            bold=False,
            color="000000",
            size=22,
            after_twips=360,
        ),
    ]
    for para in ANNEX_PARAGRAPHS:
        annex_elems.append(_p(para, bold=False, color="000000", size=22, after_twips=360))

    for j, el in enumerate(annex_elems):
        body.insert(insert_at + j, el)

    new_doc = etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )

    # Copy zip members with replacements
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == "word/document.xml":
            data = new_doc
        elif item.filename == "word/theme/theme1.xml":
            data = _patch_orange_theme(data)
        zout.writestr(item, data)

    zin.close()
    zout.close()

    dst.write_bytes(zout_buf.getvalue())
    print(f"Wrote {dst} (figure placeholders: {fig_count}, Orange theme patched)")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    src = root / "rapport_pfe_big_data_orange_linked_revised.backup-2026-05-02.docx"
    dst = root / "rapport_pfe_big_data_orange_50pages_orange_theme_placeholders_diagrams.docx"
    if not src.exists():
        print("Missing source:", src)
        return 1
    build(src, dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
