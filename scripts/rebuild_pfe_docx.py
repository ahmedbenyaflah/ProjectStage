#!/usr/bin/env python3
"""
Rebuild PFE internship DOCX: simpler wording, Ch1→Ch2 lifecycle bridge,
bibliographic rows on comparison tables 2.2–2.5, extra figure/table cues.
Run from repo root: python3 scripts/rebuild_pfe_docx.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph


def iter_block_items(parent):
    parent_elm = parent.element.body
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def set_paragraph_text(paragraph: Paragraph, text: str) -> None:
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(text)
        return
    runs[0].text = text
    for r in runs[1:]:
        r.text = ""


def merge_row_cells(row):
    cell_a = row.cells[0]
    for cell in row.cells[1:]:
        cell_a = cell_a.merge(cell)
    return cell_a


def add_merged_footnote_row(table: Table, text: str) -> None:
    if table.rows:
        t0 = table.rows[-1].cells[0].text.strip()
        if t0 == text.strip():
            return
    row = table.add_row()
    merge_row_cells(row).text = text


def add_comparison_source_row_5col(table: Table) -> None:
    """Table 2.2 style: Feature | ES | Splunk | PG | Solr"""
    if table.rows:
        first0 = table.rows[-1].cells[0].text
        if "Primary documentation used for this comparison" in first0:
            return
    row = table.add_row()
    cells = row.cells
    cells[0].text = "Primary documentation used for this comparison"
    cells[1].text = "Elasticsearch [1]"
    cells[2].text = "Splunk Enterprise [22]"
    cells[3].text = "PostgreSQL [20]"
    cells[4].text = "Apache Solr [21]"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    src = root / "rapport_pfe_big_data_orange_linked_revised.docx"
    if not src.exists():
        print("Missing:", src, file=sys.stderr)
        return 1

    doc = Document(str(src))
    blocks = list(iter_block_items(doc))

    # --- Paragraph replacements (block index → new full text) ---
    idx_text: dict[int, str] = {
        88: (
            "This report describes how the Mail Journey & Log Intelligence Platform was designed and deployed at Orange Tunisia. "
            "The goal is simple: turn huge, scattered SMTP [4] mail logs into answers that support staff can read in seconds instead of digging for half an hour. "
            "Custom Python programs read the raw files, rebuild each message’s path across servers, and store the result as JSON in Elasticsearch [1]. "
            "A FastAPI [3] backend and a React [12] web app let operators search safely; Kibana [2] adds charts for managers."
        ),
        90: (
            "Work was organized with two-week Agile Scrum [18] sprints, and the runnable stack is described with Docker [9] Compose [9] so the same setup can be reproduced on another machine."
        ),
        95: (
            "Orange Tunisia’s mail servers write a very large amount of text every day—on the order of tens of gigabytes per month and hundreds of millions of lines. "
            "Ten server families (FES, VIP, GP, ML, MX, …) each keep their own files, and the same email does not use the same simple ID everywhere. "
            "That fragmentation is the core difficulty when someone asks: “What happened to my message?”"
        ),
        96: (
            "Today, fixing one ticket often means many manual searches, roughly half an hour to two hours of engineer time, and still no easy way to see patterns (for example repeated SMTP [4] errors or IP reputation problems on DNSBL [7] lists). "
            "Classic text tools were not built for this size of data, so the project needed a Big Data style pipeline: index once, search many times."
        ),
        98: (
            "Business goals first: give support teams a faster, more reliable way to explain what happened to an email, cut repeated manual steps, and reduce mistakes caused by tired eyes on huge files. "
            "Investigations should shrink from tens of minutes to seconds where possible, and managers should see trends (errors, spam, viruses, domains) without asking developers for a new report each time."
        ),
        99: (
            "To meet those goals, the internship produced the following outcomes (how they are built technically is explained in later chapters):"
        ),
        116: (
            "Chapter 1 — Project framework: where the internship took place, how mail logs are produced today, why the old manual process hurts service quality, and how the Scrum [18] plan was run."
        ),
        117: (
            "Chapter 2 — Technology comparison: how Elasticsearch [1], FastAPI [3], React [12], and Kibana [2] were chosen after comparing realistic alternatives such as Splunk [22], Django-style stacks, and Angular [24]."
        ),
        118: (
            "Chapter 3 — System design: clear requirements, security view, and UML diagrams (use cases, sequences, activities) so non-developers can still follow the intended behavior."
        ),
        119: (
            "Chapter 4 — Implementation and evaluation: parsers, APIs, screens, dashboards, and simple performance numbers that show the gain versus manual grep."
        ),
        123: (
            "What this chapter does in one sentence: it sets the scene—company, mail servers, log volumes, old workflow—before we justify any software choice.\n"
            "You will see who hosts the internship, why fragmented SMTP [4] logs slow customer support, how much data is involved, what engineers did manually, and how Scrum [18] structured the delivery."
        ),
        126: (
            "Orange S.A. is a large European telecom group serving hundreds of millions of customers worldwide. "
            "It runs mobile, fixed, and digital services; this internship sits in the Tunisian subsidiary that operates under the same Orange brand and engineering culture."
        ),
        127: (
            "Orange Tunisia is a major operator in Tunisia (mobile, Internet, and business services). "
            "The Technical Operations department is where mail platforms are run day and night, so that is where log volume and customer incidents meet."
        ),
        128: (
            "Like the wider Orange group, the local strategy stresses digital services and customer experience. "
            "Reliable mail is part of that promise; when logs are hard to read, both customers and engineers pay the price."
        ),
        129: (
            "Figure 1.1 is the organization chart for Orange Tunisia with the Technical Operations area highlighted. "
            "Non-experts can read it like a map: it shows which branch owns the servers that generate the log files used in this project."
        ),
        136: (
            "Support is tiered: first-line (N1) agents handle simple questions, while deeper incidents go to N2 engineers who already spend much of their time inside log files and dashboards."
        ),
        138: (
            "Mail logs in telecom are a textbook Big Data case for four easy-to-remember reasons:"
        ),
        139: (
            "Volume and speed: millions of lines per day—too heavy for casual desktop tools, which is why search engines such as Elasticsearch [1] exist."
        ),
        140: (
            "Variety: each server family writes lines in its own style; the platform must normalize that diversity into one coherent record per journey."
        ),
        141: (
            "Compliance: operators must keep evidence for audits; indexed storage makes controlled retention easier than ad-hoc copies of raw files."
        ),
        142: (
            "Security: spam, phishing, and blacklist [7] issues require continuous visibility, not one-off manual checks."
        ),
        145: (
            "Day-to-day trigger: a customer says an email never arrived or arrived late. "
            "Staff must then rebuild the story from many separate files, often with different IDs for the same message. "
            "That is slow, stressful, and easy to get wrong when files are gigabytes long."
        ),
        146: (
            "The platform answers that operational pain by gathering evidence in one place and linking identifiers automatically. "
            "Supervisors wanted shorter diagnosis time, fewer repeated manual steps, and histories that are suitable for audits. "
            "Later chapters explain parsers, Elasticsearch [1], FastAPI [3], and React [12] only after this business picture is clear."
        ),
        147: (
            "Suggested visual (optional): a one-page cartoon or swim-lane from “customer calls the hotline” to “engineer opens five server folders” to show fragmentation without reading acronyms first."
        ),
        149: (
            "Think of mail as water in a pipe with several meters on it: each meter (server) writes its own readings. "
            "Labels such as FES, VIP, GP, ML, and MX name those stages for outgoing and incoming traffic."
        ),
        158: (
            "One outbound email almost always touches more than one machine. "
            "The first server may tag the message with a queue id [6], while a later hop may use a delivery id taken from a “250 OK” SMTP [4] line. "
            "Humans must connect those pieces; the internship automates that linkage."
        ),
        161: (
            "On the VIP relay (identified in lab traces by the relay IP pattern used in the sample), logs add delivery details, possible antivirus rescans, and SMTP [4] responses."
        ),
        162: (
            "Without tooling, the same ticket can cost a senior engineer roughly a quarter of an hour and a junior much longer, mostly spent jumping between files."
        ),
        165: (
            "This section states the real size of the log corpus so readers understand why “just open the file” is not a serious plan."
        ),
        190: (
            "A single grep over a three-day sample (tens of millions of lines) already takes minutes; a month of data would take tens of minutes per command, which is not interactive."
        ),
        191: (
            "A real investigation chains many such commands across folders, so wall-clock time grows quickly."
        ),
        195: (
            "Large volume, fast growth, many formats, and a need for quick answers together justify a dedicated stack: Elasticsearch [1] for search, Kibana [2] for charts, and Python parsers tailored to Orange’s log shapes."
        ),
        200: (
            "The old recipe forces engineers to remember IDs across steps, pick the right folders, open huge files side by side, and mentally align timestamps."
        ),
        215: (
            "Having listed the limits of the manual process, this section now answers two simple questions: what solution is proposed, and how the internship work was organized week by week.\n\n"
            "1.6.1 High-Level Solution Overview"
        ),
        216: (
            "The proposed platform always starts from operator outcomes: less time reading raw text, fewer manual mistakes, and both a simple web UI (React [12]) and deeper charts (Kibana [2]). "
            "Three engineering habits support those outcomes:"
        ),
        217: (
            "Normalize once, query many times: convert raw lines into structured JSON in Elasticsearch [1] so every search hits the same fields."
        ),
        218: (
            "Automate correlation: encode the expert rules that tie queue ids, relays, and delivery ids so journeys appear end-to-end without hand stitching."
        ),
        219: (
            "Layer the experience: everyday searches stay in the secured web app; analysts who need ad-hoc exploration use Kibana [2] Discover/Lens on the same data."
        ),
        222: (
            "Delivery used Agile Scrum [18]: two-week sprints, a clear product owner, and reviews with the Support Data team so each increment matched operational reality."
        ),
        229: (
            "Chapter 1 explained the pain (slow, error-prone manual searches), the data scale, and the target outcomes. "
            "Chapter 2 is the next natural step in the project lifecycle: once the problem and volumes are credible, we document how Elasticsearch [1], FastAPI [3], React [12], and Kibana [2] were picked among mature alternatives—so readers see a straight line from “what hurts” to “what we installed.”"
        ),
        233: (
            "What this chapter does in one sentence: it explains, in plain terms, why each major tool was chosen.\n"
            "It builds directly on Chapter 1: after quantifying fragmented SMTP [4] logs, we compare search engines (Elasticsearch [1] vs. Splunk [22], etc.), backends (FastAPI [3] vs. others), frontends (React [12] vs. Angular [24]/Vue [25]), and dashboards (Kibana [2] vs. Grafana [23]). "
            "Short protocol notes cover SMTP [4], Postfix [6] identifiers, and DNSBL [7] monitoring."
        ),
        235: (
            '“Big data” here simply means “too big and too fast for spreadsheets.” Doug Laney’s five Vs [19]—volume, velocity, variety, veracity, value—are a common checklist; Table 2.1 shows how each applies to mail logs.'
        ),
        243: (
            "Elasticsearch [1] is a search and analytics engine built on Apache Lucene. For log-heavy work it is attractive because it shards data, indexes text for fast lookup, supports typed fields, aggregations, and daily indices—patterns used throughout this project."
        ),
        263: (
            "Picking tools matters because the wrong database or UI framework would make the internship goals impossible at this data scale."
        ),
        311: (
            "FastAPI [3] is a modern Python framework for HTTP APIs. For this project it matters because it handles concurrency well, validates payloads with Pydantic [11], documents routes automatically (OpenAPI/Swagger), and pairs naturally with the Python parsers and Elasticsearch [8] client already in use."
        ),
        392: (
            "Chapter 2 takeaways in simple words: mail logs behave like classic big data [19], so an inverted-index engine (Elasticsearch [1]) fits; FastAPI [3] with Uvicorn [10] serves many concurrent readers; React [12] with Tailwind [13] keeps the operator UI maintainable; Kibana [2] is the fastest path to trustworthy charts on the same indices. "
            "Supporting sections covered JWT [16] login, Docker [9] packaging, and safe concurrency assumptions."
        ),
        421: (
            "What this chapter does in one sentence: it turns Chapter 1 observations into numbered requirements and diagrams.\n"
            "Tables list what the system must do (functional), how well it must run (non-functional), and what we protect against (threats). UML sketches show typical user flows so Chapter 4 can be checked against the same checklist."
        ),
        485: (
            "This chapter ends with a clear checklist: actors, requirements, threats, and diagrams. Chapter 4 implements exactly that list so traceability stays obvious."
        ),
        489: (
            "What this chapter does in one sentence: it shows working software and measured speed-ups.\n"
            "Readers can follow parsers, APIs, React [12] pages, Kibana [2] boards, and benchmark tables to see each Chapter 3 requirement reflected in code or numbers."
        ),
        730: (
            "Section 4.7 wraps up the build story: Docker [9] services, parsing passes, FastAPI [3] routes, operator screens in React [12] and Kibana [2], and the throughput/latency bands observed on the lab machine."
        ),
        734: (
            "Overall, the internship delivered an operational analytics path for SMTP [4] logs inside Orange Tunisia’s Technical Operations scope: problem sizing, stack choice, design artifacts, implementation, and basic benchmarks."
        ),
        735: (
            "The centerpiece is automatic journey reconstruction: Postfix [6] queue identifiers on edge servers are tied to downstream delivery identifiers so investigators see one timeline instead of many disconnected files."
        ),
        172: (
            "In production sizing, the rolling window spans many daily indices and tens of gigabytes on disk—another reason interactive search beats repeated full-file scans."
        ),
        178: (
            "VIP and GP families dominate disk share because most corporate outbound mail passes through those relays; the table above quantifies that imbalance."
        ),
        203: (
            "Speed: even a “small” investigation touches several servers, so 15–45 minutes for experts and up to two hours for juniors was common."
        ),
        204: (
            "Scalability: when log files grow, grep time grows with them; there is no shared index, cache, or safe parallel story for occasional users."
        ),
        205: (
            "Human error: wrong folder, wrong id, or a missed line in a multi-gigabyte file is easy when everything is manual."
        ),
        206: (
            "History: trend questions (recurring errors, noisy senders) need many passes; ad-hoc grep does not remember past queries."
        ),
        207: (
            "Reputation: checking infrastructure IPs against DNSBL [7] lists was not integrated, so staff relied on separate websites or scripts."
        ),
        250: (
            "Kibana [2] is the visualization companion to Elasticsearch [1]: operators can search with KQL, build Lens charts, and pin dashboards for recurring reviews."
        ),
        251: (
            "Discover: spreadsheet-like browsing of any index with filters—useful when auditors want raw evidence without writing code."
        ),
        252: (
            "Lens: point-and-click charts (bars, lines, pies, metrics) for people who do not want to learn a query language."
        ),
        253: (
            "Dashboard: several Lens panels on one page so managers see mail health at a glance."
        ),
        254: (
            "In this internship lab, Kibana [2] ran beside Elasticsearch [1] in Docker [9]; it complements the React [12] app instead of replacing it."
        ),
        256: (
            "Elastic’s Logstash is the default ingestion tool, but this project uses hand-written Python parsers because Orange’s logs need two-pass state (queue maps, Kaspersky [17] bridging) that is awkward to express as a simple Logstash filter chain."
        ),
        257: (
            "Python fits the team skillset, handles regular expressions cleanly, and talks to Elasticsearch [1] through the official bulk API [8]."
        ),
        258: (
            "Batch parsing by date also matches how archives arrive from operations, whereas Logstash shines more on streaming taps."
        ),
        259: (
            "In short: Logstash remains a fine default for many ELK deployments; here, custom code was the pragmatic trade-off for accurate journey reconstruction."
        ),
    }

    for idx, new in idx_text.items():
        block = blocks[idx]
        if not isinstance(block, Paragraph):
            raise SystemExit(f"Block {idx} is not a paragraph")
        set_paragraph_text(block, new)

    # --- Insert bibliographic rows on comparison tables ---
    captions = {
        "Table 2.2 — Technology comparison: Elasticsearch vs. Splunk vs. PostgreSQL vs. Apache Solr": "2.2",
        "Table 2.3 — Web framework comparison: FastAPI vs. Flask vs. Django vs. Express.js": "2.3",
        "Table 2.4 — Frontend framework comparison: React vs. Angular vs. Vue.js": "2.4",
        "Table 2.5 — Visualization tool comparison: Kibana vs. Grafana vs. Custom dashboards": "2.5",
    }
    for i, block in enumerate(blocks):
        if not isinstance(block, Paragraph):
            continue
        cap = block.text.strip()
        if cap not in captions:
            continue
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        if not isinstance(nxt, Table):
            continue
        tbl = nxt
        key = captions[cap]
        if key == "2.2":
            add_comparison_source_row_5col(tbl)
        elif key == "2.3":
            add_merged_footnote_row(
                tbl,
                "Bibliographic anchors for this matrix: FastAPI [3], Uvicorn [10], Pydantic [11]. "
                "Flask, Django, and Express.js cells summarize widely documented framework traits from their official project pages (not given separate numbers in the References list).",
            )
        elif key == "2.4":
            add_merged_footnote_row(
                tbl,
                "Per-column documentation references: React [12], Angular [24], Vue [25].",
            )
        elif key == "2.5":
            add_merged_footnote_row(
                tbl,
                "Per-column documentation references: Kibana [2], Grafana [23]; custom dashboards compared to React [12] UI practice.",
            )

    out = root / "rapport_pfe_big_data_orange_linked_revised.docx"
    bak = root / "rapport_pfe_big_data_orange_linked_revised.rebuild_tmp.docx"
    doc.save(str(bak))
    shutil.move(str(bak), str(out))
    print("Wrote:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
