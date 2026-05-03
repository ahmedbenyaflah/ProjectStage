# CG Mail Journey & Log Intelligence Platform — Academic Report Master Document

**Purpose of this file:** This Markdown is the **single source of narrative structure, figure/table inventory, citation map, and overhaul instructions** for producing a final Word/PDF report aligned with *rapport_pfe_big_data_orange_linked (1).docx* (ISAMM / Orange Tunisia Technical Operations, formal academic tone, comparable professional standard to the Firas Khemir reference report).

**Author:** Ahmed Ben Yaflah  
**Host organization:** Orange Tunisia — Technical Operations Department  
**Academic year:** 2025–2026  
**Project title:** Big Data Analytics Platform for SMTP Log Investigation — Mail Journey & Log Intelligence System  

---

## How to use this document (for a follow-up LLM pass)

Copy everything from **Section A** onward into your assistant and ask it to:

1. Expand prose into full chapters while keeping **subsection Objectives**, **Table/Figure protocol**, and **citation obligations**.
2. Replace every `[INSERT …]` placeholder with the real asset or run the command and paste terminal output.
3. Integrate **in-text citations** from the bibliography (Section L) into Chapters 1–3 so that **SMTP** and **Elastic Stack** claims are referenced.
4. Add **documentation-backed justification sentences** wherever technologies are compared (Section K).

---

## A. Document metadata & theme

| Field | Value |
|--------|--------|
| **Tone** | Formal academic English hybrid acceptable if institution requires; default **English** matching the linked DOCX. |
| **Branding** | Orange Tunisia context; Technical Operations (Direction des Réseaux & Services); Engage 2025 strategic framing where relevant. |
| **Structure** | Four main chapters + General Conclusion + Bibliography + Appendices (mirror linked DOCX). |
| **“Narrative glue”** | Every chapter opens with **why this chapter exists**; every subsection states **Objective** (one sentence); transitions explain **how the previous section leads to the next**. |

---

## B. Logical progression of the project (use this to rewrite “Task Organization” / methodology)

Present the work as a **pipeline of decisions and artifacts**, not as a tool list.

1. **Problem framing** — Fragmented SMTP logs across FES/VIP/GP/ML/MX; manual grep workflow; MTTD and operational cost.  
2. **Data understanding** — Volume, velocity, variety; sample log lines; identifier correlation (queue ID vs. downstream delivery ID).  
3. **Architecture choice** — Search-indexed store + batch parsers vs. purely relational or purely stream ingestion; justification via 5 Vs and NFRs.  
4. **Canonical model** — Mail “journey” JSON document; schema (`journey_schema`); Elasticsearch mapping/template.  
5. **Ingestion implementation** — Two-pass sent pipeline; MX/Kaspersky bridging for received; bulk indexing.  
6. **API & security** — FastAPI search and auth; JWT; PostgreSQL users.  
7. **Operator UX** — React investigation UI + embedded Kibana for KPIs and trends.  
8. **Security operations** — DNSBL scanning, alerting, scheduled journeys.  
9. **Validation** — Benchmarks (ingestion, query, DNSBL); dashboard screenshots as evidence.  
10. **Governance & evolution** — ILM, streaming roadmap, RBAC, ML anomaly detection (future work).

When rewriting any “Sprint / tasks” section, **anchor each sprint to one step above** (e.g., Sprint 1: requirements + schema; Sprint 2: sent parser; …).

---

## C. Table & figure protocol (mandatory for final manuscript)

**Numbering:** Continue chapter-based numbering: **Figure X.Y**, **Table X.Y** (as in the linked DOCX List of Figures/Tables).

**Before each visual — mandatory lead-in (adapt tense as needed):**

> The following **[Table/Figure] X.Y** demonstrates **[specific goal: e.g., global mail traffic KPIs, error-code distribution, DNSBL monitoring over time]** …

**After each visual — mandatory explanation:**

- **Tables:** Define **each column** in **SMTP log / journey** terms (what operational question it answers).  
- **Figures (screenshots / diagrams):** Explain **what the reader should infer** (workflow, trend, comparison, or troubleshooting path).

---

## D. Inventory — KPI screenshots (`kpis screenshots/`)

**Root path for publication:** `kpis screenshots/<filename>` (keep paths stable when exporting to Word).

| File | Suggested figure ID | Title (draft) |
|------|---------------------|----------------|
| `dashboard overview.png` | Figure 4.3 | Dashboard overview (Kibana) — mail telemetry KPIs |
| `sent vs recieved mails .png` | Figure 4.4 | Sent vs. received mail volume distribution |
| `most common error codes .png` | Figure 4.5 | Most common SMTP error codes (aggregated) |
| `top senders and recipents.png` | Figure 4.6 | Top sender and recipient addresses/domains |
| `spam mails overtime.png` | Figure 4.7 | Spam detections over time |
| `virus mails overtime.png` | Figure 4.8 | Virus detections over time |
| `dnsbl check .png` | Figure 4.9 | DNSBL check results (listing status) |
| `DNSBL checks overti,e.png` | Figure 4.10 | DNSBL checks over time *(note: fix filename typo in annex if desired)* |
| `dnsbl kpis.png` | Figure 4.11 | DNSBL KPI panel |
| `some kpis.png` | Figure 4.12 | Supplementary KPI overview |
| `some more kpis.png` | Figure 4.13 | Additional KPI panels |
| `top domain names.png` | Figure 4.14 | Top domain names distribution |
| `audit.png` | Figure 4.15 | Audit / trail-oriented visualization |
| `example of error code 564.png` | Figure 4.16 | Example log context for SMTP error **564** |
| `example of error code 572.png` | Figure 4.17 | Example log context for SMTP error **572** |
| `log men bara .png` | Figure 4.18 | Detailed log view (line-level investigation) |
| `unkown transmission error log men bara .png` | Figure 4.19 | Unknown transmission error — detailed log view |

### D.1 Fully worked examples (paste/adapt into Chapter 4)

**Figure 4.3 — Dashboard overview (Kibana)**

The following **Figure 4.3** demonstrates **operational visibility over consolidated SMTP-derived KPIs in a single executive-grade dashboard**.

![Dashboard overview](kpis%20screenshots/dashboard%20overview.png)

**Explanation:** The dashboard aggregates time-filtered metrics drawn from indexed journey documents (and related indices). Panels typically encode **throughput** (mail volume), **quality** (errors, spam/virus signals), and **reputation** (DNSBL-related signals). Readers should interpret relative panel heights and time-axis alignment as indicators of **incident windows** versus steady-state traffic.

---

**Figure 4.4 — Sent vs. received mail**

The following **Figure 4.4** demonstrates **directional load imbalance between outbound and inbound mail paths**, supporting capacity and routing narratives.

![Sent vs received](kpis%20screenshots/sent%20vs%20recieved%20mails%20.png)

**Explanation:** In SMTP operations, “sent” versus “received” volumes expose whether incidents cluster on **customer-originated** traffic (outbound) vs. **Internet-sourced** traffic (inbound/MX). Spikes here typically precede investigation of **specific queues**, **content filters**, or **external reputation** issues.

---

**Figure 4.5 — Most common error codes**

The following **Figure 4.5** demonstrates **which SMTP response classes dominate failures**, guiding prioritization of remediations.

![Error codes](kpis%20screenshots/most%20common%20error%20codes%20.png)

**Explanation:** SMTP status codes follow RFC conventions: **4xx** transient failures (retry), **5xx** permanent failures (policy, reputation, user unknown). Each bar maps to a **machine-readable condition** observed in logs; operational teams use this to differentiate **mailboxfull/user unknown** scenarios from **policy/reputation** scenarios.

---

*(Repeat the same Before / Image / After pattern for Figures 4.6–4.19 using the table in Section D.)*

---

## E. Code & shell evidence — placeholders and captions

**Repository note:** Legacy `parser.py` was removed; implementation lives in `backend_pipeline/sent_parser.py`, `backend_pipeline/received_parser.py`, `backend_pipeline/journey_schema.py`, `backend_pipeline/query_builder.py`, `backend_pipeline/main.py`. Adjust captions accordingly in the final PDF.

| Location in report | Placeholder | Caption (draft) |
|--------------------|-------------|-----------------|
| §4.3 Parsers | `[INSERT SCREENSHOT OF sent_parser.py — PASS 1 / PASS 2 HERE]` | Two-pass correlation: FES queue ID discovery and downstream delivery-ID linkage via `NEXT_HOP_MAP`. |
| §4.3 Received / MX | `[INSERT SCREENSHOT OF received_parser.py — Kaspersky bridging HERE]` | Identity bridging: Kaspersky `detailsid` to queue `.msg` path before merging buffered scan lines into the journey. |
| §4.3 Schema | `[INSERT SCREENSHOT OF journey_schema.py — finalize / coercion HERE]` | Canonical document shaping: field coercion, audit caps, metrics for stored vs. total lines. |
| §4.4 FastAPI | `[INSERT SCREENSHOT OF main.py — search endpoint + Depends(auth) HERE]` | Request handling: JWT-gated search, Elasticsearch query execution, response models. |
| §4.4 Query DSL | `[INSERT SCREENSHOT OF query_builder.py — bool clauses HERE]` | Query construction: filters mapped from UI parameters to Elasticsearch clauses. |
| §4.2 Infra | `[INSERT TERMINAL OUTPUT HERE: docker compose ps]` | Evidence that Elasticsearch, Kibana, and PostgreSQL services are healthy in the dev/proof stack. |
| §4.2 Infra | `[INSERT TERMINAL OUTPUT HERE: curl -s localhost:9200]` | Cluster metadata response proving Elasticsearch HTTP availability (version, cluster name). |
| §4.6 Benchmarks | `[INSERT TERMINAL OUTPUT HERE: parser run with timestamps]` | Wall-clock ingestion evidence for a bounded date range (start/end times echoed in shell). |

---

## F. Chapters — skeleton with subsection Objectives (for non-experts)

### Chapter 1 — Project framework and organizational environment

**Chapter objective:** Situate the internship, the mail infrastructure, and the business case for Big Data log analytics at Orange Tunisia.

#### 1.1 Introduction  
**Objective:** Frame the internship scope and preview Chapter 1’s role in the thesis arc.

#### 1.2 Hosting organization: Orange Tunisia  
**Objective:** Provide corporate context and locate Technical Operations within Orange’s mission.

##### 1.2.1 Presentation of the group  
**Objective:** Establish Orange S.A. / Orange Tunisia positioning for international readers.

##### 1.2.2 Technical Operations Department  
**Objective:** Enumerate responsibilities touching SMTP, security, and logs—why this internship matters.

##### 1.2.3 Strategic challenges in telecom Big Data  
**Objective:** Relate industry pressures (volume, heterogeneity, compliance, security) to log analytics needs.

#### 1.3 Project presentation  
**Objective:** Transition from organizational context to the specific Mail Journey initiative.

##### 1.3.1 Context and background  
**Objective:** Explain the historical troubleshooting pain and the genesis of the platform.

##### 1.3.2 SMTP infrastructure at Orange Tunisia  
**Objective:** Describe FES/VIP/GP/ML/MX roles so non-experts understand **where** logs originate.

**Figure 1.2** — topology (existing diagram from DOCX). *Lead-in + explanation required.*

##### 1.3.3 Problematic: distributed log fragmentation  
**Objective:** Explain identifier handoff (queue ID vs. downstream IDs) as the **core correlation problem**.

#### 1.4 Raw log data: structure, volume, Big Data challenges  
**Objective:** Quantify logs and justify why file-oriented tools fail at this scale.

##### 1.4.1 Data volume overview  
**Table 1.1** — *Lead-in + column glossary + narrative.*

##### 1.4.2 Data volume by server family  
**Table 1.2** — *Lead-in + column glossary + narrative.*

##### 1.4.3 Log file format and structure  
**Objective:** Teach the log line grammar enough for readers to follow Chapter 4 parsers.

##### 1.4.4 Why this is a Big Data problem  
**Objective:** Link observations to Volume/Velocity/Variety and to interactive latency requirements.

#### 1.5 Existing system study and critique  
**Objective:** Document the legacy grep-based workflow as baseline for benchmarks.

##### 1.5.1 Manual investigation process  
**Objective:** Show reproducible shell steps that illustrate cost (time, cognitive load).

`[INSERT TERMINAL OUTPUT HERE: illustrative grep sequence on sample path]`  
**Caption:** Representative multi-step grep workflow showing manual correlation across files.

##### 1.5.2 Limitations  
**Objective:** Summarize speed, scale, error, and observability gaps.

##### 1.5.3 Economic and operational impact  
**Objective:** Translate technical limits into customer and workforce effects.

#### 1.6 Proposed solution and methodology  
**Objective:** Present the high-level architecture and Agile/Scrum framing.

##### 1.6.1 High-level solution overview  
**Table** (solution principles) — *Lead-in + per-column meaning.*

##### 1.6.2 Agile Scrum framework  
**Objective:** Justify iterative delivery; cite Scrum Guide **[18]**.

##### 1.6.3 Sprint planning and deliverables  
**Objective:** Map sprints to the **logical progression** in Section B (not a bare tool list).

#### 1.7 Conclusion  
**Objective:** Summarize Chapter 1 and foreshadow technology choices in Chapter 2.

---

### Chapter 2 — State of the art and technology comparison

**Chapter objective:** Defend technology choices with comparisons and domain knowledge (SMTP, DNSBL, stack components).

#### 2.1 Introduction  
**Objective:** Explain why comparative analysis precedes detailed design (Chapter 3).

#### 2.2 Big Data fundamentals and the 5 V’s  
**Objective:** Ground Elasticsearch + parsers in Laney’s model; cite **[19]**.

**Table 2.1** — 5 V’s applied to SMTP analytics — *Lead-in + column glossary + narrative.*

#### 2.3 Elastic Stack (ELK): architecture and strengths  
**Objective:** Describe Elasticsearch and Kibana roles at a conceptual level; cite **[1]**, **[2]**.

##### 2.3.1 Elasticsearch  
**Objective:** Explain inverted indexing and aggregations as they relate to log investigation.

**Mandatory comparison glue:** When stating performance advantages over relational scans, add a sentence such as:  
*According to Elastic’s reference documentation, Elasticsearch is built on Apache Lucene inverted indices, which are optimized for full-text search and analytics at scale [1].*  
*(Optional: add a second sentence referencing a published benchmark only if you actually use a specific source—avoid fabricated numbers.)*

##### 2.3.2 Kibana  
**Objective:** Position dashboards vs. the React UI (exploration vs. guided investigation).

##### 2.3.3 Custom Python parsers vs. Logstash  
**Objective:** Justify **stateful** multi-pass parsing and batch replay vs. stream-only pipelines; cite Logstash docs via Elastic **[1]** / ingest architecture pages as appropriate.

#### 2.4 Technology comparison matrices  
**Objective:** Consolidate decisions with explicit criteria rows.

**Table 2.2** Elasticsearch vs. Splunk vs. PostgreSQL vs. Solr — **add cited justification** for Elasticsearch (e.g., inverted index + ecosystem **[1]**; Splunk cost **[22]**; Solr ops **[21]**; PostgreSQL strengths **[20]** where OLTP is compared).

**Table 2.3** FastAPI vs. Flask vs. Django vs. Express — cite **[3]**, **[10]**, **[11]** as applicable.

**Table 2.4** React vs. Angular vs. Vue — cite **[12]**, **[24]**, **[25]**.

**Table 2.5** Kibana vs. Grafana vs. custom — cite **[2]**, **[23]**.

#### 2.5–2.11 *(Domain + engineering sections as in DOCX: FastAPI, Uvicorn, React/Tailwind, SMTP codes, DNSBL, concurrency, Docker, JSON model, JWT)*  
For **§2.7 SMTP**:

- Cite **RFC 5321 [4]** for session semantics and response codes.  
- Cite **RFC 5322 [5]** only where message format matters.  
- Cite **Postfix references [6]** when describing log-like behaviors if aligned with your deployment.

**Table 2.6** — SMTP status codes — *each row tied to operational meaning.*  
**Table 2.7** — DNSBLs — cite operator docs (e.g. Spamhaus **[7]**).

#### 2.12 Conclusion  
**Objective:** Close the technology narrative and hand off to requirements/UML (Chapter 3).

---

### Chapter 3 — Requirements and system design

**Chapter objective:** Formalize requirements, threat model, and UML specifications.

#### 3.1 Introduction  
**Objective:** Bridge operational stories (Ch.1–2) to testable requirements.

#### 3.2 Actors  
**Objective:** Map N1/N2/SD/Admin personas to permissions and information needs.

#### 3.3 Functional requirements  
**Tables 3.1** (summary) — *each requirement traceable to Chapter 4 sections.*

#### 3.4 Non-functional requirements  
**Tables 3.2–3.3** — performance, scale, security.

#### 3.5 UML models  
**Objective:** Provide implementation-independent structure.

- **Figure 3.1** Use case — *Lead-in + actor narrative.*  
- **Figures 3.2–3.4** Sequence diagrams — *Lead-in + message-flow explanation.*  
- **Table 3.4** Journey schema — **column glossary mandatory** (each field: SMTP meaning + indexing rationale).  
- **Figure 3.5** Activity diagram — troubleshooting glue from ticket to root cause.

#### 3.6 Conclusion  
**Objective:** Lock requirements traceability for Chapter 4 acceptance.

---

### Chapter 4 — System realization and performance evaluation

**Chapter objective:** Prove implementation with code paths, UI evidence, dashboards, and benchmarks.

#### 4.1 Introduction  
**Objective:** Explain evaluation strategy (correctness of correlation + latency + operability).

#### 4.2 Development environment  
**Tables 4.1–4.2** — tooling versions and Docker services — cross-check against `docker-compose.yml`.

`[INSERT TERMINAL OUTPUT HERE: docker compose ps]`  

#### 4.3 Core implementation — parsers and correlation  
**Objective:** Show how raw logs become canonical journeys.

- Placeholders for **sent_parser.py**, **received_parser.py**, **journey_schema.py** (Section E).  
- **Table 4.3** Regex patterns — *each pattern tied to a field in journeys.*

#### 4.4 Backend API  
**Objective:** Describe REST surface, auth, and Elasticsearch integration; cite FastAPI **[3]**, elasticsearch-py **[8]**.

`[INSERT SCREENSHOT OF main.py HERE]`  

#### 4.5 Frontend  
**Objective:** Link UI components to workflows (search, details, Kibana embed).

**Figures 4.1–4.2** (React) — from implementation screenshots if separate from KPI folder.

#### 4.6 KPI dashboards and operational analytics (Kibana screenshots)

For **each** figure in Section D, apply the **mandatory Before / After** sentences. Suggested column-wise readings:

| Typical Kibana panel | SMTP/journey reading |
|----------------------|----------------------|
| Time histogram | Incident windows; workload cycles; campaign spikes |
| Top-N sender/recipient | Abuse investigations; compromised accounts; noisy peers |
| Error code breakdown | Policy vs. mailbox vs. reputation failures |
| Spam/virus trends | Content-filter effectiveness; outbreak detection |
| DNSBL panels | External reputation; proactive delisting workflows |

#### 4.7 Performance evaluation  
**Tables 4.4–4.7** — ingestion, query, DNSBL scan, sprint/benchmark summary.

`[INSERT TERMINAL OUTPUT HERE: scripted benchmark or logged timings]`  

#### 4.8 Conclusion  
**Objective:** Summarize evidence and limitations (single-node ES, dev security flags, batch ingestion).

---

## G. General conclusion + future work

Reuse the DOCX themes: **operational MTTD reduction**, **correlation algorithm**, **rolling retention**, **Elastic + FastAPI + React + Docker**. Future work: **Filebeat/Logstash/Kafka streaming**, **Elastic ML**, **Kibana alerting**, **ILM**, **RBAC**, **horizontal ES cluster**, **ticketing/SIEM integrations**.

---

## H. Accessibility checklist (non-expert readers)

- [ ] Every § starts with **Objective** (one sentence).  
- [ ] First mention of **FES/VIP/GP/ML/MX** includes a **plain-language role**.  
- [ ] Every acronym expanded once (SMTP, DNSBL, JWT, KPI, MTTD, ILM, RBAC, …).  
- [ ] Figures never appear **without** Before-sentence and After-explanation.  
- [ ] Tables never appear **without** column glossary in SMTP terms.

---

## I. Bibliography — in-text citation map (mandatory coverage)

Use **numbered references** as in the DOCX bibliography. The follow-up pass must **scatter citations** in Ch.1–3:

| IDs | Use when discussing… |
|-----|------------------------|
| **[1]** | Elasticsearch architecture, indices, search relevance |
| **[2]** | Kibana dashboards, Lens, Discover |
| **[3]** | FastAPI features, OpenAPI, validation |
| **[4]** | SMTP protocol behavior, reply codes |
| **[5]** | Internet message format (if citing headers/body) |
| **[6]** | MTA/log semantics where Postfix-compatible behavior appears |
| **[7]** | Spamhaus / DNSBL listing context |
| **[8]** | Python Elasticsearch client, Bulk API |
| **[9]** | Docker Compose orchestration |
| **[10]** | Uvicorn / ASGI |
| **[11]** | Pydantic models |
| **[12]** | React UI layer |
| **[13]** | Tailwind CSS |
| **[14]** | dnspython DNSBL lookups |
| **[15]** | Thread pools / concurrent futures for scans |
| **[16]** | JWT (RFC 7519) |
| **[17]** | Kaspersky Security for Linux Mail Server |
| **[18]** | Scrum methodology |
| **[19]** | Laney 5Vs / Big Data definition |
| **[20]** | PostgreSQL (comparison baseline) |
| **[21]** | Apache Solr (comparison) |
| **[22]** | Splunk (comparison) |
| **[23]** | Grafana (comparison) |
| **[24]** | Angular (comparison) |
| **[25]** | Vue.js (comparison) |

---

## J. Justified comparisons — template sentences (do not fabricate metrics)

Use variants of:

- *According to Elastic’s Elasticsearch Reference [1], indices store JSON documents and rely on Lucene inverted indices for fast search and aggregations—characteristics that motivated choosing Elasticsearch over row-oriented OLTP stores for log-scale interactive queries.*  
- *PostgreSQL documentation [20] positions the engine as a general-purpose ACID database; for full-text scan-heavy workloads at log scale, a dedicated search index [1] reduces sequential table scans.*  
- *Splunk’s documentation [22] describes a commercial data platform; cost and licensing constraints motivated an open Elastic stack for this internship scope.*  
- *As defined in RFC 5321 [4], SMTP reply codes classify transient vs. permanent failures—directly informing how journey status is derived from log lines.*

If citing **benchmark numbers**, only attach numbers tied to a **named publication** (Elastic blog, peer-reviewed paper, your own measured table). Otherwise stay qualitative.

---

## K. Quality gate before submission

1. **List of Figures / Tables** matches numbering in text.  
2. Every figure/table has **Before** + **After** text.  
3. Chapters 1–3 cite **[4]** and **[1]** (minimum) wherever SMTP or Elastic claims appear.  
4. Technology matrices include **at least one** authoritative citation per alternative.  
5. Code screenshots updated to **actual filenames** in repo (`sent_parser.py`, not obsolete `parser.py`).  
6. KPI filenames with typos (`overti,e`, `unkown`) either **renamed** or **acknowledged in footnote**.

---

## L. Full bibliography (copy from linked DOCX)

[1] Elastic, Inc. *Elasticsearch: The Official Distributed Search and Analytics Engine*, Version 8.12. https://www.elastic.co/guide/en/elasticsearch/reference/8.12/

[2] Elastic, Inc. *Kibana: Your Window into the Elastic Stack*, Version 8.12. https://www.elastic.co/guide/en/kibana/8.12/

[3] Sebastián Ramírez. *FastAPI: Modern, Fast Web Framework for Building APIs with Python 3.8+.* https://fastapi.tiangolo.com/

[4] J. Klensin. *Simple Mail Transfer Protocol*, RFC 5321. IETF, October 2008.

[5] P. Resnick (Ed.). *Internet Message Format*, RFC 5322. IETF, October 2008.

[6] Wietse Venema. *Postfix Configuration Parameters and Log Reference.* http://www.postfix.org/postconf.5.html

[7] The Spamhaus Project. *Spamhaus ZEN — Combined Spam Blocking List.* https://www.spamhaus.org/zen/

[8] Elastic, Inc. *Python Elasticsearch Client 8.x.* https://elasticsearch-py.readthedocs.io/

[9] Docker, Inc. *Docker Compose Reference.* https://docs.docker.com/compose/

[10] Tom Christie. *Uvicorn: An ASGI Server.* https://www.uvicorn.org/

[11] Samuel Colvin et al. *Pydantic v2: Data Validation Using Python Type Hints.* https://docs.pydantic.dev/

[12] Meta (Facebook), Inc. *React: A JavaScript Library for Building User Interfaces.* https://react.dev/

[13] Adam Wathan & Steve Schoger. *Tailwind CSS: A Utility-First CSS Framework.* https://tailwindcss.com/docs

[14] Bob Halley et al. *dnspython: A DNS Toolkit for Python*, Version 2.6. https://dnspython.readthedocs.io/

[15] Python Software Foundation. *concurrent.futures — Launching Parallel Tasks.* https://docs.python.org/3/library/concurrent.futures.html

[16] M. Jones, J. Bradley, N. Sakimura. *JSON Web Token (JWT)*, RFC 7519. IETF, May 2015.

[17] Kaspersky Lab. *Kaspersky Security for Linux Mail Server Documentation.* https://support.kaspersky.com/KLMS/

[18] Ken Schwaber, Jeff Sutherland. *The Scrum Guide*, November 2020. https://scrumguides.org/

[19] Doug Laney. *3D Data Management: Controlling Data Volume, Velocity, and Variety.* META Group, 2001.

[20] The PostgreSQL Global Development Group. *PostgreSQL 16 Documentation.* https://www.postgresql.org/docs/16/

[21] Apache Software Foundation. *Apache Solr Reference Guide.* https://solr.apache.org/guide/

[22] Splunk, Inc. *Splunk Enterprise Documentation.* https://docs.splunk.com/Documentation/Splunk

[23] Grafana Labs. *Grafana Documentation.* https://grafana.com/docs/grafana/latest/

[24] Google. *Angular Framework Documentation.* https://angular.dev/

[25] Evan You. *Vue.js Documentation.* https://vuejs.org/guide/introduction.html

---

## M. Appendix pointers (environment & API)

- **Appendix A:** Environment variables and ports (`config.py`, `.env` examples).  
- **Appendix B:** REST endpoints (`/api/login`, `/api/signup`, `/api/search`, DNSBL routes) — mirror `main.py` routes exactly in the final PDF.  
- **Appendix C (optional):** Sample journey JSON (redacted) with field annotations.

---

**End of `report.md` master document.**
