# SMTP Log Investigation Platform
## CG Mail Journey & Log Intelligence System
### End-of-Study Internship Report — Orange Tunisia

---

> **Author:** Ahmed  
> **Host Organization:** Orange Tunisia — Technical Operations Department  
> **Academic Year:** 2025–2026  
> **Technology Stack:** Python · FastAPI · Elasticsearch 8.12 · React · Docker  

---

## Contents

- [Abstract](#abstract)
- [General Introduction](#general-introduction)
  - [Problem Statement](#problem-statement)
  - [Project Objectives](#project-objectives)
  - [Expected Contributions](#expected-contributions)
  - [Document Structure](#document-structure)
- [Chapter 1 — Project Framework and Organizational Environment](#chapter-1--project-framework-and-organizational-environment)
- [Chapter 2 — State of the Art and Technological Foundation](#chapter-2--state-of-the-art-and-technological-foundation)
- [Chapter 3 — Analysis of Requirements and System Design](#chapter-3--analysis-of-requirements-and-system-design)
- [Chapter 4 — System Realization and Performance Evaluation](#chapter-4--system-realization-and-performance-evaluation)
- [General Conclusion](#general-conclusion)
- [Bibliography](#bibliography)
- [List of Figures](#list-of-figures)
- [List of Tables](#list-of-tables)

---

## Abstract

Modern telecommunications operators rely on intricate, distributed infrastructures to process millions of electronic messages each day. At Orange Tunisia, the corporate Simple Mail Transfer Protocol (SMTP) infrastructure spans a heterogeneous fleet of edge servers, routing nodes, antivirus appliances, and inbound mail exchangers — each producing its own stream of plain-text log files independently, without a central collection or correlation mechanism. When a message delivery problem occurs, support engineers are compelled to manually open dozens of log files across twenty or more server directories, search for queue identifiers by hand, mentally reconstruct multi-hop message paths, and interpret cryptic SMTP status codes from memory. This process is slow, error-prone, and fundamentally unscalable as mail traffic volumes continue to grow.

This report describes the design, architecture, and full implementation of the **CG Mail Journey & Log Intelligence Platform** — an end-to-end solution developed during an internship at Orange Tunisia's Technical Operations Department. The platform automates the complete pipeline from raw distributed log ingestion through intelligent mail journey correlation, to a searchable, authenticated web interface that empowers support staff to diagnose delivery issues in seconds rather than hours.

The core contribution is a pair of specialized Python log parsers (`sent_parser.py` and `received_parser.py`) that implement a **journey correlation algorithm**: they read log files from FES (front-end submission) servers, map downstream delivery identifiers across VIP, GP, and ML relay nodes using a next-hop routing table (`NEXT_HOP_MAP`), and construct a single canonical JSON document per mail journey that captures the complete end-to-end path, timing, Kaspersky antivirus/antispam verdicts, error details, and recipient outcomes. Inbound journeys on MX servers are similarly correlated using a two-phase Kaspersky identifier bridging mechanism. All normalized documents are bulk-indexed into **Elasticsearch 8.12.0** under daily indices, enabling sub-second full-text and structured searches across millions of records.

A **FastAPI** backend with JWT-based authentication exposes a stable REST API (`/api/search`, `/api/blacklist/*`) consumed by a **React** single-page application that presents a guided operator workflow: date-based search, multi-field filtering, spam/virus detection summaries, and an integrated **DNS Blacklist (DNSBL) monitoring panel** with email alert dispatch. **Kibana** provides KPI-style dashboards and ad-hoc exploratory analytics on the same indices using Lens and Discover.

Benchmarks demonstrate that the platform processes a full day's log corpus — spanning three days, nine server families, and tens of thousands of journeys — in a matter of seconds, and that the Elasticsearch query engine delivers paginated search results with sub-100-millisecond latency under typical operational loads. The DNSBL scanner probes thirteen infrastructure IP addresses against five major blocklists on a configurable schedule (default: once per day) and on demand from the API, using a parallel executor for DNS lookups and batched writes to Elasticsearch.

The platform was developed using the **Agile Scrum** methodology with iterative sprints, and is fully containerized via **Docker Compose** for reproducible deployment on any Linux host.

---

## General Introduction

### Problem Statement

The daily operation of a large-scale telecommunications infrastructure generates an enormous volume of machine-generated text data. For Orange Tunisia's mail platform, this translates to hundreds of thousands of log lines per day distributed across more than twenty server directories organized by role: front-end submission servers (FES01, FES02), VIP routing servers (VIP01, VIP02), general-population relay servers (GP01, GP02), mail-layer servers (ML01, ML02), and inbound mail exchangers (MX01 through MX04). Each server writes independent plain-text `.log` files, sometimes time-sliced into multiple files per day for high-volume periods.

The critical problem is **distributed log fragmentation** combined with **cross-server identifier churn**. A single outbound email begins its journey with a Postfix-style queue identifier (e.g., `[123456]`) on an FES server. When that message is successfully relayed to a downstream node, the downstream system assigns a **completely different numeric delivery identifier** visible in its own logs. Without automated linkage, support engineers cannot answer the fundamental question: "What happened to message X from the moment it was submitted until it was delivered or rejected?" They are forced to open multiple log files manually, search for related IDs by intuition, and mentally reconstruct a coherent timeline — a process that can take thirty minutes to two hours per incident and is highly susceptible to human error.

The economic impact of delayed diagnostics in a carrier-grade mail infrastructure is significant. Customer complaints escalate, SLA penalties accrue, and engineering resources are diverted from proactive maintenance to reactive fire-fighting. Furthermore, the absence of a unified KPI layer means that systemic trends — such as rising failure rates for a particular error code, or a relay server appearing on a DNS blocklist — go undetected until they cause customer-visible outages.

### Project Objectives

The primary objective of this internship project is to design and implement a **comprehensive log investigation platform** that:

1. **Automates log aggregation and normalization** — reads plain-text log files from all server families, parses structured fields from free-form log lines using regular expressions, and produces canonical JSON documents.

2. **Implements cross-server journey correlation** — links FES queue identifiers to downstream delivery identifiers and assembles the complete multi-hop path into a single searchable document per mail journey.

3. **Provides real-time search and filtering** — exposes an authenticated REST API enabling support engineers to retrieve any mail journey by sender, recipient, queue ID, status, spam verdict, time range, or any combination thereof, with results in under one second.

4. **Delivers operational KPI dashboards** — aggregates key metrics (status distribution, top error codes, spam ratios, average delivery duration by status) in **Kibana** (Lens/Discover) on the journey indices, aligned with the same fields the React search UI uses.

5. **Integrates infrastructure security monitoring** — continuously scans outbound mail server IP addresses against major DNS blocklists and alerts administrators when an IP is listed.

6. **Maintains scalability and operational simplicity** — leverages containerization (Docker Compose) for zero-configuration deployment and Elasticsearch's distributed search engine for horizontal scalability as log volume grows.

### Expected Contributions

The principal contributions of this project to Orange Tunisia's Technical Operations Department are:

- **Reduction in mean time to diagnose (MTTD)** delivery failures from hours to seconds, by replacing manual `grep` workflows with a guided web interface backed by Elasticsearch full-text search.

- **A reusable ingestion pipeline** that can process historical log data in batch mode or be scheduled for daily incremental runs, producing a growing searchable archive of mail journeys.

- **Proactive IP reputation monitoring** through automated DNSBL scanning with email digest alerts, enabling the team to discover and remediate blacklisting events before customers report delivery failures.

- **An extensible platform** built on open standards (Elasticsearch, FastAPI, React) that future developers can enhance with real-time streaming ingestion (Logstash/Beats), machine learning anomaly detection, or integration with ticketing systems.

- **A Kibana analytics layer** on the same indices enabling network operations center (NOC) staff to build custom dashboards, run ad-hoc KQL queries, and generate executive-level reports without requiring engineering intervention.

### Document Structure

This report is organized into four chapters plus a general introduction and conclusion, following the canonical structure of a French engineering end-of-study internship report:

**Chapter 1 — Project Framework and Organizational Environment** situates the project within the host organization (Orange Tunisia's Technical Operations Department), describes the existing manual investigation process and its limitations, and presents the proposed solution and the Agile Scrum project management methodology.

**Chapter 2 — State of the Art and Technological Foundation** provides a thorough review of the technologies selected for the platform: the Elastic Stack (Elasticsearch, Logstash, Kibana), Python backend engineering with FastAPI and Uvicorn, React and Tailwind CSS for the frontend, and the domain-specific knowledge required for SMTP log analysis, including SMTP status codes, DNS blocklist mechanisms, and multithreading patterns.

**Chapter 3 — Analysis of Requirements and System Design** identifies the system actors (N1/N2 support agents, system administrators, security operations center), formalizes functional and non-functional requirements, and presents the UML system models: use case diagrams, sequence diagrams for log ingestion and search, the class diagram for the mail journey data model, and the activity diagram for the troubleshooting workflow.

**Chapter 4 — System Realization and Performance Evaluation** details the full implementation: the development environment, core parser logic with regex design, the FastAPI routing system, Elasticsearch mapping and index templates, the React user interface, Kibana integration, testing strategy, and performance benchmarking results for ingestion speed and query latency.

---

## Chapter 1 — Project Framework and Organizational Environment

### 1.1 Introduction

This chapter introduces the organizational context in which the SMTP Log Investigation Platform was designed and developed. It presents the host organization, Orange Tunisia, with particular emphasis on the Technical Operations Department where the internship took place. It then describes the existing mail infrastructure, the manual investigation workflow that preceded this project, the quantifiable limitations of that workflow, and the high-level proposed solution. The chapter concludes with a description of the project management methodology (Agile Scrum) and the sprint planning that structured the development effort.

### 1.2 Hosting Organization: Orange Tunisia

#### 1.2.1 Presentation of the Group

Orange S.A. is a French multinational telecommunications corporation and one of the world's largest operators of mobile and internet services, serving approximately 296 million customers across 26 countries as of 2024. Founded in 1988 as France Télécom and rebranded as Orange in 2013, the group operates under the motto "the future is you" and positions itself as a digital services provider extending beyond traditional connectivity into cloud computing, cybersecurity, financial services, and enterprise data solutions.

Orange Tunisia (formerly Tunisie Télécom Orange, now operating as a fully branded Orange subsidiary) is a major player in the Tunisian telecommunications market, offering mobile, broadband, and enterprise services. The Tunisian subsidiary operates a modern, carrier-grade network infrastructure that includes a complex email and messaging backbone serving both corporate clients and large-scale transactional mail flows.

The Orange group's strategic roadmap — *Engage 2025* — places digital transformation, network modernization, and customer experience at the center of its priorities. Within this framework, the Technical Operations Department is tasked with ensuring the reliability, performance, and security of all critical infrastructure components, including the SMTP mail platform that is the subject of this report.

#### 1.2.2 The Technical Operations Department

The Technical Operations Department (Direction des Opérations Techniques) at Orange Tunisia is responsible for:

- **Network infrastructure management**: configuration, monitoring, and incident response for all active network elements including switches, routers, firewalls, load balancers, and application servers.
- **Mail platform operations**: administration of the SMTP relay infrastructure, antivirus/antispam filtering (Kaspersky Security for Linux Mail Server), and delivery monitoring.
- **Security operations**: coordination with the Security Operations Center (SOC) for threat detection, incident response, and compliance reporting.
- **Performance engineering**: capacity planning, performance benchmarking, and optimization of critical services.
- **Log management and auditing**: collection, retention, and analysis of system and application logs for operational and regulatory purposes.

The department is organized into tiered support structures. Level 1 (N1) support agents handle initial customer contacts and straightforward diagnostic queries. Level 2 (N2) engineers perform deeper technical investigations and escalate to Level 3 specialists for complex infrastructure issues. The SMTP log investigation platform is primarily designed to empower N1 and N2 engineers, reducing escalation rates and shortening resolution times.

#### 1.2.3 Strategic Challenges in Telecom Log Management

The telecommunications sector is distinguished from other industries by the sheer volume and velocity of operational log data generated by active network elements. For a carrier-grade SMTP infrastructure processing millions of messages per day, log management presents several interrelated strategic challenges:

**Volume and velocity**: A single front-end submission server may generate tens of thousands of log lines per hour during peak periods. Across twenty or more servers, daily log volume can reach hundreds of millions of lines. Storing, indexing, and querying this data at interactive speeds requires purpose-built search infrastructure rather than conventional relational databases.

**Heterogeneity**: Different server roles (submission, relay, antivirus, inbound exchange) produce log files with different line grammars, identifier schemes, and event vocabularies. A unified investigation platform must handle this heterogeneity transparently, presenting a normalized view to operators regardless of where in the infrastructure an event originated.

**Regulatory compliance**: Telecom operators are subject to data retention regulations that require log records to be preserved for specified periods. An archival pipeline that systematically indexes logs into Elasticsearch with daily indices provides a natural framework for retention policy enforcement via index lifecycle management.

**Security visibility**: The mail infrastructure is a high-value target for abuse — spam campaigns, phishing, and denial-of-service attacks. Real-time visibility into spam verdicts, relay IP reputations, and anomalous delivery patterns is a prerequisite for effective security posture management.

### 1.3 Project Presentation

#### 1.3.1 Context and Background

This internship project was initiated in response to a concrete operational need identified by the Technical Operations Department: the existing process for investigating SMTP delivery failures was manual, slow, and increasingly unsustainable as mail traffic volumes grew. The project was scoped as a full-stack platform development effort, encompassing log parsing, search engine integration, backend API design, and frontend development — a comprehensive exercise in modern software engineering applied to a real production problem.

The project received the internal designation **CG Mail Journey & Log Intelligence Platform** (where "CG" refers to the Corporate Group mail infrastructure segment). The development was carried out over the duration of the internship period, structured as a series of Agile Scrum sprints with the internship supervisor acting as the Product Owner.

#### 1.3.2 The SMTP Infrastructure at Orange

Orange Tunisia's outbound and inbound mail infrastructure is organized into a layered architecture that reflects both functional roles and security boundaries:

**Front-End Submission Servers (FES01, FES02)**: These are the entry points for outbound corporate mail. Messages submitted by internal mail clients or application systems arrive at FES servers, where they are queued, subjected to initial policy checks (including sender authentication and envelope validation), and relayed onward to the appropriate downstream server. FES servers run a Postfix-compatible mail transfer agent and assign each message a numeric queue identifier (`[qid]`) that is used throughout the FES-local log trail.

**VIP Routing Servers (VIP01, VIP02)**: High-priority mail flows — VIP accounts, executive communications, contractually prioritized corporate mail — are routed through dedicated VIP relay nodes. These servers handle the relay and optional rewriting of high-priority messages before final delivery.

**General Population Relay Servers (GP01, GP02)**: Standard corporate outbound mail is relayed through GP servers. These nodes handle the bulk of outbound volume and are the primary consumers of SMTP relay bandwidth.

**Mail Layer Servers (ML01, ML02)**: A supplementary relay tier that provides additional routing capacity and handles specific mail flows (e.g., bulk transactional mail or particular customer segments).

**Inbound Mail Exchangers (MX01–MX04)**: These servers receive inbound SMTP connections from the public internet. They implement MX DNS record resolution, perform connection-level filtering, run Kaspersky Security for Linux Mail Server for content inspection, and deliver accepted messages to internal mailboxes.

The critical architectural fact that drives the platform's design is that **a single outbound message produces log entries across at least two server families**: FES (where the journey begins with a `[qid]`) and one or more downstream relays (VIP, GP, or ML), where the same message is identified by a **different numeric delivery identifier** extracted from the SMTP `250` response. This identifier mismatch is the root cause of the manual correlation problem.

#### 1.3.3 The Problematic: Distributed Log Fragmentation

To fully appreciate the difficulty of the manual investigation workflow, consider the lifecycle of a single outbound email:

1. The message is submitted to FES01 and assigned `[qid=123456]`. The FES log records: sender address, recipient address, Kaspersky inspection result, and the relay action: `sent [FESID] -> [10.x.x.20]:25 got:250 789012345`.

2. The downstream server (a VIP node, based on the `.20` last octet) receives the message and logs it under `[deliveryId=789012345]`. The VIP log records: delivery confirmation, antivirus rescan if applicable, and final SMTP response to the recipient's mail server.

3. If the recipient's mail server rejects the message with a `550 User Unknown` error, that rejection appears in the VIP log under `[789012345]`, not under `[123456]`.

A support engineer investigating a customer complaint about a non-delivered message must: (a) know to look at FES01 for the `[qid]`, (b) find the relay line that shows `got:250 789012345`, (c) know that the `.20` last octet means VIP, (d) open VIP01 or VIP02 logs for the relevant date, (e) search for `[789012345]`, and (f) find and interpret the `550` rejection. Each step requires specialized knowledge, manual file navigation, and careful attention. A single mistake — looking at the wrong date file, misreading a hex digit in an IP address, or searching the wrong VIP server — invalidates the entire investigation.

### 1.4 Existing System Study and Critique

#### 1.4.1 Description of the Manual "Grep" Investigation Process

Prior to this project, the investigation workflow at Orange Tunisia's Technical Operations Department was entirely manual, relying on standard Unix command-line tools:

```bash
# Step 1: Find the queue ID for a sender
grep "from <customer@example.com>" /path/to/Log-CG/FES01/2026-01-27.log

# Step 2: Extract the queue ID and find the relay line
grep "\[123456\]" /path/to/Log-CG/FES01/2026-01-27.log | grep "got:250"

# Step 3: Note the delivery ID and determine the downstream server
# (requires knowledge of the IP-to-server mapping)

# Step 4: Search the downstream server logs
grep "\[789012345\]" /path/to/Log-CG/VIP01/2026-01-27.log
grep "\[789012345\]" /path/to/Log-CG/VIP02/2026-01-27.log

# Step 5: Interpret the results manually
```

This process requires the engineer to: mentally maintain the identifier chain across multiple greps; know which directories to search based on the relay IP's last octet; open and parse multiple files; and manually correlate the timeline across different server clocks (which may have minor NTP drift).

For inbound mail investigations on MX servers, an additional complication arises: Kaspersky's `EXTFILTER` subsystem logs antivirus scan events using an internal `detailsid` that is not the same as the Postfix queue identifier. The engineer must perform an additional correlation step to link Kaspersky events to the correct mail journey.

#### 1.4.2 Limitations: Speed, Scalability, and Human Error

The manual `grep` workflow exhibits a number of critical limitations that become increasingly severe as mail volume grows:

**Speed**: A single investigation involving a cross-server correlation typically requires 15–45 minutes for an experienced engineer and 60–120 minutes for a junior support agent. During high-incident periods (e.g., a relay server becoming blacklisted, causing hundreds of delivery failures simultaneously), the support team cannot scale — more incidents mean proportionally more investigation time, creating a backlog that undermines SLA commitments.

**Scalability**: The `grep` approach does not scale with data volume. As log file sizes grow, the time required for a single grep increases linearly. There is no indexing, no caching of previous results, and no way to run parallel investigations efficiently. Log files from multiple servers cannot be searched simultaneously without custom scripting.

**Human error**: The manual process is highly susceptible to errors of omission and commission. An engineer may: search only FES01 when the relevant message went through FES02; mistake a delivery ID for a queue ID; read the wrong date file; or miss a relevant log line in a large file. These errors lead to incorrect diagnoses, inappropriate remediation actions, and recurring escalations.

**No historical context**: The `grep` workflow provides no mechanism for tracking trends over time. An engineer investigating a failure today has no easy way to determine whether the same error code has been appearing repeatedly over the past week, whether a particular sender is generating an unusually high failure rate, or whether a relay server's error rate has been increasing gradually.

**No security visibility**: The manual workflow provides no integrated view of IP reputation. An engineer investigating a delivery failure caused by blacklisting must separately run DNSBL queries using external tools, often after the fact. There is no proactive alerting when an infrastructure IP first appears on a blocklist.

#### 1.4.3 Economic and Operational Impact of Delayed Diagnostics

The operational and economic consequences of the manual investigation workflow are significant and measurable:

**Customer experience degradation**: Delivery failures that could be diagnosed and remediated in minutes instead persist for hours, during which affected customers receive no service. In a competitive telecommunications market, repeated service failures damage customer retention metrics.

**Engineer productivity loss**: Experienced N2 engineers spending 30–60 minutes per delivery incident are not available for proactive maintenance, optimization, or strategic infrastructure improvement. The manual workflow represents a continuous tax on engineering capacity.

**Cascading incident risk**: Without a unified view of delivery status across the infrastructure, a systemic failure (e.g., a relay server generating 550 errors for an entire recipient domain due to a misconfiguration) may go undetected until customer complaints reach a threshold, by which time thousands of messages may have failed.

**Compliance exposure**: Without a systematic log archive and query capability, demonstrating compliance with data retention or incident investigation requirements in the event of a regulatory audit requires assembling raw log files manually — a time-consuming and error-prone process.

### 1.5 Proposed Solution and Methodology

#### 1.5.1 High-Level Solution Overview (ELK + FastAPI)

The CG Mail Journey & Log Intelligence Platform is designed around three architectural principles:

1. **Normalize once, query many times**: Rather than searching raw log files on demand (the `grep` approach), the platform pre-processes all log files into normalized, structured JSON documents and indexes them into Elasticsearch, where they become instantly searchable using rich query DSL.

2. **Correlate across servers automatically**: The journey correlation algorithm in the parsers performs the cross-server ID linking that engineers previously did manually, so that every Elasticsearch document already represents the complete multi-hop journey regardless of how many different identifiers were used across servers.

3. **Expose through a layered interface**: The platform provides both a guided operator interface (React SPA backed by FastAPI) for N1/N2 support workflows and a raw Kibana interface for ad-hoc exploration by N3 engineers and data analysts.

The full technology stack is:

| Layer | Technology | Version |
|-------|-----------|---------|
| Log parsing | Python | 3.12 |
| Search engine | Elasticsearch | 8.12.0 |
| Analytics UI | Kibana | 8.12.0 |
| API backend | FastAPI + Uvicorn | ≥0.109 / ≥0.27 |
| Authentication | PostgreSQL + JWT | PG 16 |
| Frontend | React + Tailwind CSS | — |
| DNSBL scanning | dnspython | ≥2.6.1 |
| Containerization | Docker Compose | — |

#### 1.5.2 Project Lifecycle: The Agile Scrum Framework

The development effort was managed using the **Agile Scrum** framework, which is well-suited to an internship project of this scope because:

- It allows requirements to be refined iteratively as understanding of the problem deepens.
- It produces working software at the end of each sprint, enabling early feedback from the operational team.
- It accommodates the inherent uncertainty of a first-of-kind platform in this environment.

The team consisted of:
- **Product Owner**: Internship supervisor (Technical Operations Department lead), responsible for prioritizing the product backlog based on operational value.
- **Scrum Master / Developer**: The intern, responsible for sprint planning, development, testing, and retrospectives.
- **Stakeholders**: N1/N2 support engineers who provided feedback on the interface and workflow during sprint reviews.

Sprint duration was fixed at two weeks, with a sprint review/demo at the end of each sprint.

#### 1.5.3 Sprint Planning and Deliverables

The project was executed across five two-week sprints:

**Sprint 1 — Infrastructure Setup and Basic Parsing (Weeks 1–2)**
- Deliverables: Docker Compose stack (Elasticsearch 8.12.0, Kibana 8.12.0, PostgreSQL 16); basic sent-mail parser reading FES01 logs and indexing raw journey documents; index template v1.
- Definition of done: Documents visible in Kibana Discover for a sample date.

**Sprint 2 — Journey Correlation and Complete Sent Parser (Weeks 3–4)**
- Deliverables: `NEXT_HOP_MAP` correlation logic linking FES `[qid]` to VIP/GP/ML `deliveryId`; complete status model (Pending, Success, Partial Success, Failed, Discarded); Kaspersky field extraction from mapped server logs; `audit_metrics` sub-document.
- Definition of done: A test message traced through FES01→VIP01 produces a single correlated document with correct status and Kaspersky fields.

**Sprint 3 — Inbound Parser, Schema Finalization, and FastAPI Backend (Weeks 5–6)**
- Deliverables: `received_parser.py` with Kaspersky `detailsid` bridging; composable index template `cg-mail-journeys-v1` (journey_schema.py); FastAPI application with JWT auth (PostgreSQL), `/api/search` and blacklist endpoints; `query_builder.py` with full filter DSL for search.
- Definition of done: Authenticated API search returns paginated results; KPI views are available in Kibana on indexed journey fields.

**Sprint 4 — React Frontend and DNSBL Security Module (Weeks 7–8)**
- Deliverables: React SPA with search interface, results table, and blacklist panel; DNSBL scanner (`blacklist_scan.py`) with `ThreadPoolExecutor`; `/api/blacklist/scan`, `/api/blacklist/listed`, and `/api/blacklist/email` endpoints; email alert dispatch (`email_alerts.py`).
- Definition of done: Full end-to-end demo from log file to React search result; DNSBL panel shows live blacklist status.

**Sprint 5 — Testing, Performance Optimization, and Documentation (Weeks 9–10)**
- Deliverables: Unit tests for parsers, query builder, and API; performance benchmarking; bulk indexing optimization (`chunk_size=200, refresh=True`); audit line capping; `schema_version` field; project documentation.
- Definition of done: Benchmark results documented; all tests pass; README complete.

### 1.6 Conclusion

This chapter has presented the organizational context (Orange Tunisia's Technical Operations Department), described the SMTP infrastructure and its multi-server log fragmentation problem, analyzed the limitations of the existing manual investigation workflow, and introduced the proposed platform together with the Agile Scrum methodology used to develop it. The following chapter reviews the technological foundations — the Elastic Stack, Python backend frameworks, React frontend libraries, and domain-specific SMTP and security knowledge — that underpin the platform's implementation.

---

## Chapter 2 — State of the Art and Technological Foundation

### 2.1 Introduction

Building a production-grade log intelligence platform requires selecting technologies that are individually mature and collectively composable. This chapter reviews the state of the art for each major component of the platform: the Elastic Stack for search and analytics, FastAPI and the Python ecosystem for backend API development, React and Tailwind CSS for frontend engineering, and the domain-specific knowledge of SMTP protocols, antivirus systems, and DNS-based IP reputation that gives the platform its operational meaning. Where multiple alternatives exist, this chapter justifies the selection made for this project.

### 2.2 The Elastic Stack (ELK)

#### 2.2.1 Elasticsearch: Distributed Search and Inverted Indexing

Elasticsearch is an open-source, distributed search and analytics engine built on top of Apache Lucene. First released in 2010 by Shay Banon (Elasticsearch B.V., now Elastic NV), it has become the de facto standard for log analytics, full-text search, and operational intelligence at scale.

**Core architecture**: Elasticsearch stores data as JSON documents organized into **indices**. Each index is divided into one or more **shards** (Lucene instances), which can be distributed across a cluster of nodes for horizontal scalability. Shards can be replicated for fault tolerance.

**Inverted index**: The fundamental data structure that makes Elasticsearch fast for text search is the **inverted index** — a mapping from each unique term in a corpus to the list of documents containing that term, along with positional and frequency metadata. For a log corpus where engineers search for sender email addresses, error codes, or queue IDs, the inverted index allows Elasticsearch to locate all matching documents in O(log N) time regardless of the total document count, compared to the O(N) linear scan of `grep`.

**Mapping and field types**: Elasticsearch 8.x enforces explicit **mappings** that define how each field is indexed and stored. For this project, the index template (`journey_schema.py`) carefully distinguishes between:
- **`keyword`** fields: exact-match terms, optimal for filter clauses, aggregations, and sorting (e.g., `status`, `qid`, `kaspersky_spam_status`).
- **`text`** fields with `.keyword` sub-field: for human-readable strings that benefit from full-text analysis (e.g., `sender`) while also supporting exact-match aggregations via the `.keyword` sub-field.
- **`date`** fields: for timestamp-based range queries and time-series visualization (e.g., `start_time`, `end_time`, `@timestamp`).
- **`float`** fields: for numeric range queries and statistical aggregations (e.g., `duration_seconds`).
- **Non-indexed `object`** fields: the `audit` field stores raw log lines in `_source` without paying inverted-index cost — a deliberate optimization for this project since raw lines are displayed in the UI but never searched.

**Aggregations**: Beyond search, Elasticsearch's aggregation framework enables computing grouped metrics directly in the engine — term counts (status distribution, top senders), averages (mean delivery duration by status), and filtered sub-aggregations (top spam senders among spam-classified messages). This eliminates the need for client-side post-processing of large result sets.

**Index lifecycle and daily indices**: The platform uses daily indices (`mail-journeys-sent-YYYY-MM-DD`, `mail-journeys-received-YYYY-MM-DD`) following the time-series index pattern recommended by Elastic. This enables efficient date-range queries (query only the relevant daily index), simplifies retention policy enforcement (delete old indices), and avoids mapping conflicts between data from different time periods.

#### 2.2.2 Logstash and Kibana: Data Ingestion and Visualization

**Logstash** is the "L" in ELK: a data collection, transformation, and routing pipeline. It accepts input from many sources (file, syslog, Kafka, JDBC), applies filter plugins (Grok for log parsing, Mutate for field transformation, GeoIP for IP enrichment), and outputs to Elasticsearch. For this project, a custom Python parsing pipeline was chosen over Logstash because:

- The multi-server journey correlation logic (`NEXT_HOP_MAP`, `delivery_lookup`, Kaspersky `detailsid` bridging) requires stateful two-pass processing that is difficult to express in Logstash filter pipelines.
- Python provides richer regex support, dictionary-based journey state management, and direct integration with Elasticsearch's bulk API.
- The custom parsers can be run on-demand per date, making them well-suited to the batch ingestion model used here.

**Kibana** is the "K" in ELK: a web-based analytics and visualization interface. It provides:
- **Discover**: full-text search over any Elasticsearch index using KQL (Kibana Query Language), with configurable column selection and document expansion.
- **Lens**: drag-and-drop visual builder for charts, tables, and metrics dashboards.
- **Dashboard**: composition of multiple Lens panels into operational overview screens.

In this project, Kibana runs at `http://localhost:5601` (containerized) and provides a complementary analytics layer to the custom React interface — particularly for ad-hoc exploration and executive dashboards that the React SPA does not support natively.

#### 2.2.3 Why ELK? Comparison with RDBMS for Log Analysis

A natural question is why Elasticsearch is preferred over a relational database management system (RDBMS) such as PostgreSQL for log storage and search.

| Dimension | Elasticsearch | PostgreSQL |
|-----------|--------------|------------|
| Full-text search performance | O(log N) via inverted index | O(N) table scan or ILIKE |
| Schema flexibility | Dynamic / semi-structured JSON | Rigid schema, ALTER TABLE migrations |
| Horizontal scaling | Native distributed sharding | Complex (Citus, partitioning) |
| Time-series queries | Native date histogram aggregations | Possible, but slower |
| Aggregation performance | In-engine, highly optimized | SQL GROUP BY, slower on large tables |
| Kibana / Grafana integration | Native | Via plugins |
| Write performance | Optimized bulk indexing API | Row-level MVCC overhead |
| Operational complexity | Higher (JVM, cluster management) | Lower for small scale |

For a log analytics use case at carrier scale, Elasticsearch's advantages in full-text search, aggregation performance, and Kibana integration decisively outweigh the added operational complexity. PostgreSQL is retained in this project only for its transactional strength in the JWT user authentication subsystem.

### 2.3 Backend Engineering with Python

#### 2.3.1 FastAPI: High-Performance Asynchronous APIs

FastAPI is a modern, high-performance Python web framework for building REST APIs, created by Sebastián Ramírez and first released in 2018. It has rapidly become one of the most popular Python web frameworks, consistently ranking near the top of Python developer surveys.

Key features relevant to this project:

**Pydantic-based data validation**: FastAPI uses Pydantic v2 for automatic request body validation and serialization. Request bodies (e.g., `SignupBody`, `LoginBody`) are defined as Pydantic `BaseModel` classes; FastAPI automatically parses incoming JSON, validates field types, and returns structured 422 errors for invalid input. This eliminates boilerplate input validation code.

**Automatic OpenAPI documentation**: FastAPI generates a complete OpenAPI 3.0 specification from the decorated route functions and Pydantic models, serving interactive Swagger UI at `/docs` and ReDoc at `/redoc`. During development, this made testing API endpoints fast and self-documenting.

**Dependency injection**: FastAPI's `Depends()` system provides clean dependency injection for cross-cutting concerns. The `get_current_user` dependency, which validates the JWT bearer token and extracts the user payload, is attached to protected routes with a single parameter annotation. This eliminates repetitive authentication code and makes the auth flow easy to test and mock.

**Background tasks**: FastAPI's `BackgroundTasks` mechanism enables dispatching work (such as sending the blacklist digest email) asynchronously after the HTTP response has been sent, without requiring a separate task queue such as Celery.

**CORS middleware**: The `CORSMiddleware` with `allow_origins=["*"]` is configured for development; in production, it should be restricted to the React app's origin.

#### 2.3.2 Uvicorn and ASGI Architecture

Uvicorn is the ASGI (Asynchronous Server Gateway Interface) server that runs the FastAPI application. ASGI is the successor to WSGI (Web Server Gateway Interface), designed to support Python's `async`/`await` concurrency model. For this project, the API routes that perform Elasticsearch queries benefit from Python's async I/O capabilities even when the Elasticsearch client is used synchronously, because the Uvicorn server can handle concurrent requests efficiently.

The application is started with:
```python
uvicorn.run(app, host="0.0.0.0", port=config.PORT)
```

In production, multiple Uvicorn workers behind a reverse proxy (nginx, Traefik) would provide both concurrency and horizontal scaling.

#### 2.3.3 Data Integration with the Elasticsearch Python Client

The `elasticsearch-py` client (version `>=8.12.0,<9.0.0`) is used throughout the backend:

- **`get_elasticsearch()`** in `es_infra.py` creates a shared `Elasticsearch` client instance using the `ES_URL` configuration variable.
- **`helpers.bulk()`** in the parsers performs efficient batch indexing using Elasticsearch's Bulk API, which amortizes HTTP overhead across multiple documents per request.
- **`es.search()`** in `main.py` and **`es.indices.*`** for index management operations.

The client handles connection pooling, retry logic, and serialization transparently, providing a Pythonic interface to the Elasticsearch REST API.

### 2.4 Frontend Architecture

#### 2.4.1 React: Component-Based UI Development

React is a JavaScript library for building user interfaces, developed and maintained by Meta (Facebook). First released in 2013, it has become the dominant paradigm for modern web application development.

React's component model maps naturally to the mail investigation interface: the search filter panel, results table, and blacklist monitor are each independent components that receive data via props or manage local state via hooks (`useState`, `useEffect`). The unidirectional data flow model makes state management predictable and debuggable.

For the SMTP log investigation interface, React enables:
- **Controlled form components** for the multi-field search filters (date, direction, sender, recipient, qid, status, spam/virus status, duration range, time-of-day range).
- **Conditional rendering** based on API response state (loading spinner, empty state, results table).
- **Optimistic UI updates** when navigating between pages.
- **Periodic polling** of `/api/blacklist/listed` (and on-demand `POST /api/blacklist/scan` when the operator refreshes DNSBL) for blacklist updates; KPI charts are maintained in Kibana.

#### 2.4.2 Tailwind CSS: Utility-First Styling

Tailwind CSS is a utility-first CSS framework that provides a comprehensive set of low-level CSS utility classes (margin, padding, color, typography, flexbox, grid) that can be composed directly in JSX markup to style components without writing custom CSS. This approach dramatically accelerates UI development for developers who are comfortable with CSS concepts but wish to avoid the overhead of maintaining a custom stylesheet.

For the SMTP investigation interface, Tailwind enables responsive, professional-looking layouts — filter panels, data tables with alternating row colors, status badges with color-coded backgrounds (green for Success, red for Failed, orange for Partial Success), and modal dialogs — without any custom CSS files.

#### 2.4.3 Lucide-React: Iconography for Dashboard Clarity

Lucide-React is an icon library providing over 1,000 consistent, scalable SVG icons as React components. In the SMTP investigation interface, icons communicate meaning at a glance: a magnifying glass for search, a shield for security/blacklist, an envelope for mail journeys, a warning triangle for Failed status, and a checkmark circle for Success. This reduces cognitive load for support engineers who may be scanning hundreds of results rapidly.

### 2.5 Log Analysis & Domain Knowledge

#### 2.5.1 SMTP Protocol Fundamentals

The Simple Mail Transfer Protocol (SMTP) is the foundational application-layer protocol for email transmission, defined originally in RFC 821 (1982) and updated by RFC 5321 (2008). Understanding SMTP is essential to interpreting the log lines that the parsers process.

An SMTP transaction proceeds as follows:

1. **TCP connection establishment**: The sending MTA connects to port 25 (or 587 for submission) of the receiving MTA.
2. **Banner and EHLO**: The receiving server sends a greeting banner; the client identifies itself with `EHLO` and negotiates extension capabilities.
3. **Envelope negotiation**: The sender specifies the envelope sender (`MAIL FROM:<sender@example.com>`) and recipient(s) (`RCPT TO:<recipient@example.com>`).
4. **Data transfer**: The client sends `DATA`, then the message headers and body, terminated by a line containing only `.`.
5. **Server response**: The receiving server issues a final SMTP response code indicating acceptance (`250 OK`), temporary failure (`4xx`), or permanent failure (`5xx`).
6. **Connection closure**: Both parties issue `QUIT`.

In the Orange Tunisia infrastructure, FES servers act as sending MTAs when relaying corporate mail to downstream servers. The `got:250 <deliveryId>` log line that triggers the journey correlation logic is FES's record of the receiving server's `250 OK` response, which includes the receiving server's internally assigned message identifier. This is the precise moment at which the delivery identifier transitions from the FES-assigned `[qid]` to the downstream-assigned `deliveryId`.

#### 2.5.2 Analysis of SMTP Status Codes and Error Handling

SMTP uses a three-digit numeric response code system where the first digit indicates the class of response:

**Table 2.1 — SMTP Status Codes Reference**

| Code | Category | Meaning | Platform Handling |
|------|----------|---------|-------------------|
| 250 | Success | Message accepted / delivered | `got:250 <deliveryId>` triggers cross-server correlation |
| 221 | Success | Server closing connection | Informational; not stored |
| 421 | Transient failure | Service temporarily unavailable | Logged as `Failed` with code `421` |
| 450 | Transient failure | Mailbox temporarily unavailable | Logged as `Failed` with code `450` |
| 451 | Transient failure | Local processing error | Logged as `Failed` with code `451` |
| 452 | Transient failure | Insufficient system storage | Logged as `Failed` with code `452` |
| 500 | Permanent failure | Syntax error | Logged as `Failed` with code `500` |
| 550 | Permanent failure | Mailbox unavailable / rejected | Most common failure; Logged as `Failed` with code `550` |
| 551 | Permanent failure | User not local | Logged as `Failed` with code `551` |
| 552 | Permanent failure | Exceeded storage allocation | Logged as `Failed` with code `552` |
| 553 | Permanent failure | Mailbox name not allowed | Logged as `Failed` with code `553` |
| 554 | Permanent failure | Transaction failed / policy violation | Logged as `Failed` with code `554` |

The parsers extract error codes using the regular expression `re.search(r"\b([45]\d{2})\b", line)`, which matches any three-digit code beginning with 4 or 5 — a deliberately broad pattern that captures both transient (4xx) and permanent (5xx) failures.

#### 2.5.3 Real-Time Processing: Multithreading vs. Sequential Parsing

The journey parsers are implemented as **single-threaded** sequential Python processes. This design choice was made deliberately:

**In-order processing requirement**: The sent-mail parser performs two sequential passes: first over FES logs (building the `delivery_lookup` mapping from `deliveryId` to `qid`), then over downstream VIP/GP/ML logs (using `delivery_lookup` to attribute lines to the correct journey). These passes must be sequential because the second pass depends on the complete state of `delivery_lookup` built in the first pass.

**Memory footprint**: A single day's journey dictionary for the sent-mail corpus fits comfortably in memory (typically tens of thousands of entries × ~1–2 KB per entry = tens to hundreds of MB). No parallelism is required within a single date's processing.

**Practical parallelism**: Production parallelism is achieved by running multiple parser processes simultaneously for different dates (e.g., processing 2026-01-27, 2026-01-28, and 2026-01-29 concurrently as separate Python processes) rather than parallelizing within a single date.

**Contrast with DNSBL scanning**: The `blacklist_scan.py` module uses `concurrent.futures.ThreadPoolExecutor(max_workers=20)` because DNSBL queries are I/O-bound (waiting for DNS resolution) with no data dependencies between individual `(IP, DNSBL)` pairs. Threading provides near-linear speedup for this use case, reducing a 65-query sequential scan (13 IPs × 5 DNSBLs) from potentially minutes to a few seconds.

#### 2.5.4 Infrastructure Security: DNSBL and IP Reputation Systems

DNS-based Blocklists (DNSBLs), sometimes called Real-time Blackhole Lists (RBLs), are distributed databases of IP addresses known or suspected to be sources of spam, malware, or abusive traffic. They are implemented as DNS zones where the presence of a DNS `A` record for a queried IP indicates that the IP is listed.

**Query mechanism**: To check whether IP `a.b.c.d` is listed in DNSBL `bl.example.com`, the client resolves the DNS hostname `d.c.b.a.bl.example.com`. If a record is returned, the IP is listed; an `NXDOMAIN` response (no such domain) means the IP is clean.

**Major DNSBLs monitored by this platform**:

| DNSBL | Operator | Focus |
|-------|----------|-------|
| `zen.spamhaus.org` | Spamhaus Project | Composite list: SBL (spam sources), XBL (exploited hosts), PBL (policy block) |
| `bl.spamcop.net` | SpamCop / Cisco | User-reported spam sources |
| `dnsbl.sorbs.net` | SORBS | Multi-category: spam, open relays, zombies |
| `dnsbl-2.uceprotect.net` | UCEPROTECT | ISP-level blocks based on abuse reports |
| `access.redhawk.org` | Redhawk | Spam and malware sources |

The platform monitors thirteen specific IP addresses from Orange Tunisia's outbound mail infrastructure against all five DNSBLs every five minutes, producing 65 checks per scan cycle. Results are indexed into Elasticsearch under the `dnsbl-checks` index, and the React frontend displays the current `LISTED` entries in a dedicated panel.

### 2.6 Conclusion

This chapter has reviewed the complete technological foundation of the platform: Elasticsearch's inverted index and aggregation engine, Kibana's visualization capabilities, FastAPI's asynchronous REST framework, React's component model, and the domain-specific SMTP and DNSBL knowledge required to build a meaningful mail log investigation tool. The following chapter applies this knowledge to formal system design: identifying actors, formalizing requirements, and constructing the UML models that guided the implementation.

---

## Chapter 3 — Analysis of Requirements and System Design

### 3.1 Introduction

This chapter formalizes the system's requirements through structured analysis and expresses the design through UML modeling. Requirements analysis transforms the operational needs identified in Chapter 1 into precise, testable specifications. UML modeling provides implementation-independent blueprints that guided the development team and serve as reference documentation for future maintainers.

The analysis process involved a series of structured interviews with N1/N2 support engineers, observation sessions of the manual investigation workflow, and review of existing scripts and documentation from the Technical Operations Department. Requirements were prioritized using the MoSCoW framework (Must Have, Should Have, Could Have, Won't Have).

### 3.2 Identification of Actors

#### 3.2.1 Support Agents (N1/N2)

**N1 (Level 1) Support Agents** are the primary users of the platform. They are non-specialist operators who handle initial customer contacts and must be able to investigate delivery problems without deep knowledge of Postfix internals or Elasticsearch query syntax. Their primary interaction is through the React-based search interface with guided filter controls.

N1 agents require:
- The ability to search for a mail journey by customer email address (sender or recipient) and date, without knowing which server handled the message.
- Clear status indicators (Success / Failed / Pending / Partial Success / Discarded) with color coding.
- Access to the complete audit trail (raw log lines from all servers) for escalation to N2.
- Spam and virus verdict visibility to distinguish content policy rejections from infrastructure failures.

**N2 (Level 2) Support Engineers** perform deeper investigations when N1 escalates. They need:
- Access to all N1 search capabilities plus advanced filters (qid, duration range, time-of-day window, relay IP, error code).
- The complete server path (e.g., FES01 → VIP02) showing exactly which nodes handled the message.
- Raw audit log lines in full detail, including both FES lines and downstream mapped lines.
- Access to the Kibana interface for ad-hoc KQL queries and historical trend analysis.

#### 3.2.2 System Administrators

System administrators are responsible for maintaining the platform's health and configuration. They interact with the system through the Docker Compose stack, environment configuration (`.env` files), and direct Elasticsearch API access. Their needs include:
- Index management: creating, querying, and deleting daily indices; applying template changes.
- Parser execution scheduling (cron jobs or manual invocation).
- Monitoring bulk indexing performance and Elasticsearch cluster health.
- Managing user accounts and JWT configuration.

#### 3.2.3 Security Operations Center (SOC)

SOC analysts monitor the DNSBL panel and blacklist email alerts. Their needs include:
- Real-time visibility into which Orange infrastructure IPs are currently listed on major DNSBLs.
- Historical record of listing events (via the `dnsbl-checks` Elasticsearch index).
- Email alert dispatch on demand (via `POST /api/blacklist/email`).
- Integration potential with SIEM (Security Information and Event Management) systems via Elasticsearch data export.

### 3.3 Functional Requirements

#### 3.3.1 Log Aggregation and Centralization

**FR-01**: The system shall ingest plain-text `.log` files from all server directories under `LOG_BASE_PATH` (FES01, FES02, VIP01, VIP02, GP01, GP02, ML01, ML02, MX01–MX04).

**FR-02**: The system shall support per-date batch processing: given a date string `YYYY-MM-DD`, the parser shall process all log files matching that date pattern (including time-sliced files such as `2026-01-27_10-51.log`).

**FR-03**: The system shall support auto-discovery of available dates by scanning the FES01 (for sent) and MX0* (for received) directories for log files.

**FR-04**: The system shall index each processed document into the appropriate daily Elasticsearch index (`mail-journeys-sent-YYYY-MM-DD` or `mail-journeys-received-YYYY-MM-DD`).

**FR-05**: The system shall use the Elasticsearch Bulk API with a chunk size of 200 documents and `refresh=True` to ensure indexed documents are immediately searchable.

#### 3.3.2 Mail Journey Reconstruction Logic

**FR-06**: For sent-mail journeys, the system shall extract the Postfix queue identifier `[qid]` from FES log lines and use it as the primary journey key and Elasticsearch document `_id`.

**FR-07**: The system shall detect relay handoffs by matching the relay IP's last octet against `NEXT_HOP_MAP` and extract the `deliveryId` from the `got:250 <deliveryId>` SMTP acknowledgment.

**FR-08**: The system shall correlate downstream server log lines (VIP/GP/ML) to the original FES journey using the `delivery_lookup[deliveryId] → qid` mapping, merging Kaspersky verdicts, server path, and outcome events into the same journey document.

**FR-09**: The system shall compute `duration_seconds` as the difference between the first and last parsed timestamp for each journey.

**FR-10**: The system shall assign one of the five journey statuses (Pending, Success, Partial Success, Failed, Discarded) based on the status model defined in Section 3.4.2 and finalized through recipient accounting.

**FR-11**: For inbound (received) journeys on MX servers, the system shall bridge Kaspersky `EXTFILTER` events using the two-phase `kaspersky_id_map` / `pending_kaspersky_lines` mechanism, ensuring Kaspersky scan verdicts are always attributed to the correct mail journey.

**FR-12**: The system shall assign unique Elasticsearch document IDs for received journeys as `{serverPath[0]}-{qid}` to prevent collisions when the same numeric queue ID appears on different MX hosts.

#### 3.3.3 Search and Filtering Capabilities

**FR-13**: The authenticated `/api/search` endpoint shall accept the following query parameters: `date`, `sender`, `recipient`, `qid`, `status`, `direction`, `spam_status`, `virus_status`, `min_duration`, `max_duration`, `start_time`, `end_time`, `page`, `size`.

**FR-14**: `sender` and `recipient` searches shall use wildcard `query_string` queries supporting partial matches (e.g., searching for `example.com` shall return all journeys involving that domain).

**FR-15**: `qid` search shall use an exact-match `term` query.

**FR-16**: Duration filters shall use Elasticsearch `range` queries on the `duration_seconds` field.

**FR-17**: Time-of-day filters shall construct `range` queries on the `start_time` date field, combining the `date` parameter with normalized `HH:MM:SS.mmm` boundaries.

**FR-18**: Operational KPIs (status distribution, top server flows, top error codes, top senders/recipients, spam-oriented breakdowns, average duration by status) shall be produced in **Kibana** (Lens/Discover) on `mail-journeys-sent-*` and `mail-journeys-received-*` indices using the same indexed fields as search.

#### 3.3.4 Security Monitoring and Alerting

**FR-19**: The system shall maintain a configurable list of outbound mail server IP addresses and a configurable list of DNSBL zones to probe.

**FR-20**: The system shall run a DNSBL scan on application startup and subsequently every `DNSBL_SCAN_INTERVAL_SECONDS` (default: 86400 seconds / one day), and shall support an authenticated on-demand scan via `POST /api/blacklist/scan`.

**FR-21**: DNSBL scan results shall be indexed into the `dnsbl-checks` Elasticsearch index with fields: `ip`, `blacklist`, `dnsb_status` (LISTED / CLEAN / ERROR), `@timestamp`.

**FR-22**: The `/api/blacklist/listed` endpoint shall return deduplicated, sorted LISTED entries for the React frontend's blacklist panel.

**FR-23**: The `/api/blacklist/email` endpoint shall, when triggered, send an HTML table digest of all currently LISTED entries via Gmail SMTP (port 465, SSL) as a background task.

### 3.4 Non-Functional Requirements

#### 3.4.1 Performance and Latency Constraints

**NFR-01**: The `/api/search` endpoint shall return paginated results (page size ≤ 100) within 500 milliseconds for typical daily index sizes under normal cluster load.

**NFR-02**: Kibana-operated aggregations on daily journey indices shall remain responsive for N2/N3 analysis under normal single-node development load (interactive Lens queries, not batch exports).

**NFR-03**: The sent-mail parser shall process a full day's log corpus (three days of data across all server families, totaling thousands of journeys) in under 60 seconds.

**NFR-04**: The DNSBL scanner shall complete a full 65-check scan (13 IPs × 5 DNSBLs) within 10 seconds using the `ThreadPoolExecutor(max_workers=20)` implementation.

**NFR-05**: The Elasticsearch `refresh_interval` shall be set to `5s` in the composable index template for a good balance between indexing throughput and near-real-time query freshness during batch ingestion.

#### 3.4.2 Scalability and Data Retention

**NFR-06**: The system architecture shall support scaling to multiple Elasticsearch nodes by using the standard Elasticsearch Bulk API and composable index templates, with no application-level changes required.

**NFR-07**: Daily indices shall be independently manageable for retention policy: deleting old indices (e.g., indices older than 90 days) shall be achievable via a single `DELETE /mail-journeys-*-YYYY-MM-DD` API call without affecting other data.

**NFR-08**: The audit line capping mechanism (`MAX_AUDIT_EDGE_LINES=25`, `MAX_AUDIT_DOWNSTREAM_LINES=25`) shall prevent individual documents from growing excessively large for high-traffic journeys, while preserving full line counts in `audit_metrics` for charting.

**NFR-09**: The system shall handle log files with encoding errors gracefully using `errors="ignore"` in file reading, ensuring that a single malformed byte does not abort a batch run.

#### 3.4.3 System Security and Threat Model

**Table 3.1 — Threat Model Summary**

| Threat | Category | Mitigation |
|--------|----------|------------|
| Unauthorized API access | Authentication bypass | JWT bearer token required on all protected routes; `HTTPBearer(auto_error=False)` with explicit 401 response |
| Weak JWT secrets | Cryptographic weakness | `JWT_SECRET_KEY` loaded from environment variable; dev default must be overridden in production |
| SQL injection in auth | Injection | Pydantic input validation; parameterized SQLAlchemy queries in `database.py` |
| Elasticsearch injection | Query injection | `escape_query_string()` in `query_builder.py` escapes all Lucene reserved characters in user inputs |
| Log data exfiltration | Data confidentiality | API results require valid JWT; CORS restricted to specific origins in production |
| DNSBL credential exposure | Secrets management | Email credentials loaded from environment variables; endpoint returns 400 if not configured |
| Denial of service via large queries | Resource exhaustion | `size` parameter capped at 10,000; ES request timeout set to 600 seconds |
| Insecure local Elasticsearch | Network access | ES security disabled only for local dev (`xpack.security.enabled=false`); production must enable TLS and authentication |

### 3.5 System Modeling (UML)

#### 3.5.1 General Use Case Diagram

The general use case diagram identifies the three primary actors and their interactions with the platform:

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                       CG Mail Journey Platform — Use Case Diagram                   │
│                                                                                     │
│  ┌───────────────┐     authenticate          ┌─────────────────────────────────────┐│
│  │ Support Agent │ ──────────────────────── ▶│ POST /api/login                     ││
│  │   (N1 / N2)   │     search journeys       │ POST /api/signup                    ││
│  └───────────────┘ ──────────────────────── ▶│ GET  /api/search                    ││
│         │           view KPI dashboards      │ Kibana (Lens / Discover)            ││
│         │          ──────────────────────── ▶│                                     ││
│         │           view blacklist status    │ GET  /api/blacklist/listed          ││
│         │          ──────────────────────── ▶│                                     ││
│         │                                   └─────────────────────────────────────┘│
│                                                                                     │
│  ┌──────────────┐      send alert email                                            │
│  │  SOC Analyst │ ──────────────────────────▶│ POST /api/blacklist/email           │
│  └──────────────┘                            │                                     │
│                                                                                     │
│  ┌────────────────┐    run parser (CLI)       ┌─────────────────────────────────────┐│
│  │  System Admin  │ ──────────────────────── ▶│ python sent_parser.py [date]        ││
│  └────────────────┘    manage indices         │ python received_parser.py [date]    ││
│                       ──────────────────────▶ │ docker compose up/down              ││
│                        configure environment  └─────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Description of use cases**:

- **Authenticate**: Support agents create accounts via `POST /api/signup` (which immediately logs them in) or authenticate via `POST /api/login`. Both return a JWT token stored client-side and sent as a Bearer token on subsequent requests.

- **Search Journeys**: The central use case — agents submit a search form with date and optional filters; the React SPA calls `GET /api/search` with the filter parameters; the FastAPI backend constructs an Elasticsearch query, executes it, normalizes the results, and returns a paginated JSON response.

- **View KPI Dashboards**: Agents view status distribution, top error codes, spam ratios, and average delivery duration in **Kibana** dashboards built on the same Elasticsearch journey indices.

- **View Blacklist Status**: Agents check the DNSBL panel, which calls `GET /api/blacklist/listed` to retrieve current LISTED entries.

- **Send Alert Email**: SOC analysts trigger `POST /api/blacklist/email` to dispatch an HTML digest of all currently LISTED IPs to the configured recipient address.

- **Run Parser**: System administrators invoke `sent_parser.py` or `received_parser.py` from the command line (with optional date arguments) to process log files and index journeys.

- **Manage Indices**: System administrators interact with Elasticsearch directly (via `curl` or Kibana Dev Tools) to delete old indices, apply template changes, or inspect cluster health.

#### 3.5.2 Sequence Diagram: Log Ingestion

The log ingestion sequence for the sent-mail parser illustrates the multi-step correlation process:

```
┌──────────────┐   ┌───────────────────┐   ┌─────────────────────┐   ┌──────────────────────┐
│   CLI User   │   │  sent_parser.py   │   │  Elasticsearch      │   │  Log Filesystem      │
└──────┬───────┘   └────────┬──────────┘   └──────────┬──────────┘   └──────────┬───────────┘
       │                    │                          │                          │
       │ python sent_parser │                          │                          │
       │ .py 2026-01-27     │                          │                          │
       │───────────────────▶│                          │                          │
       │                    │                          │                          │
       │                    │ ensure_mail_journey_     │                          │
       │                    │ template()               │                          │
       │                    │─────────────────────────▶│                          │
       │                    │ ◀ 200 OK / already exists│                          │
       │                    │                          │                          │
       │                    │ open FES01/2026-01-27*.log                          │
       │                    │─────────────────────────────────────────────────────▶
       │                    │ ◀──────────── stream lines ─────────────────────────
       │                    │                          │                          │
       │                    │ [for each line]          │                          │
       │                    │  extract [qid]           │                          │
       │                    │  build/update journeys   │                          │
       │                    │  map deliveryId→qid      │                          │
       │                    │  (delivery_lookup)       │                          │
       │                    │                          │                          │
       │                    │ open FES02/2026-01-27*.log                          │
       │                    │─────────────────────────────────────────────────────▶
       │                    │ ◀──────────── stream lines ─────────────────────────
       │                    │                          │                          │
       │                    │ open VIP01, VIP02, GP01, GP02, ML01, ML02 logs      │
       │                    │─────────────────────────────────────────────────────▶
       │                    │ ◀──────────── stream lines ─────────────────────────
       │                    │                          │                          │
       │                    │ [for each downstream line]                          │
       │                    │  lookup delivery_lookup  │                          │
       │                    │  merge into journey doc  │                          │
       │                    │  (Kaspersky, serverPath, │                          │
       │                    │   outcome, end_time)     │                          │
       │                    │                          │                          │
       │                    │ finalize_journey_document(doc)                      │
       │                    │ helpers.bulk(es, actions,                           │
       │                    │   chunk_size=200,        │                          │
       │                    │   refresh=True)          │                          │
       │                    │─────────────────────────▶│                          │
       │                    │ ◀── {indexed: N docs} ───│                          │
       │                    │                          │                          │
       │ ◀ LOG: SENT 2026-01-27 | indexed=N | Success=x ...                      │
└──────┴───────┘   └────────┴──────────┘   └──────────┴──────────┘   └──────────┴───────────┘
```

**Key decision points in the sequence**:

1. The parser first ensures the index template exists (idempotent call — no-op if already installed).
2. The first pass (FES01, FES02) builds the complete `journeys` dictionary and `delivery_lookup` map.
3. The second pass (VIP01, VIP02, GP01, GP02, ML01, ML02) enriches journeys using `delivery_lookup`.
4. Finalization (`finalize_journey_document`) normalizes timestamps, caps audit arrays, fills `audit_metrics`, and sets `schema_version`.
5. A single `helpers.bulk` call indexes all documents for the date, with `refresh=True` ensuring immediate searchability.

#### 3.5.3 Class Diagram: The Data Model for Mail Journeys

The canonical mail journey document is represented as follows:

**Table 3.2 — Journey Document Fields (Summary)**

| Field | Type | Description | Indexed? |
|-------|------|-------------|---------|
| `schema_version` | `short` | Document schema version (current: 2) | Yes |
| `qid` | `keyword` | Postfix queue identifier (primary journey key) | Yes |
| `detailsid` | `keyword` | Kaspersky internal ID (received journeys only) | Yes |
| `deliveryId` | `keyword` | Downstream delivery ID (sent journeys with relay) | Yes |
| `direction` | `keyword` | `"sent"` or `"received"` | Yes |
| `date` | `keyword` | Processing date `YYYY-MM-DD` | Yes |
| `status` | `keyword` | Journey outcome: Pending / Success / Partial Success / Failed / Discarded | Yes |
| `sender` | `text` + `.keyword` | Envelope sender address | Yes (full-text + keyword) |
| `recipients` | `keyword[]` | All envelope recipient addresses | Yes |
| `successful_recipients` | `keyword[]` | Recipients with confirmed delivery | Yes |
| `serverPath` | `keyword[]` | Ordered list of servers handling the journey (e.g., `["FES01", "VIP02"]`) | Yes |
| `relayIp` | `keyword` | Relay destination IP (from FES `sent →` line) | Yes |
| `start_time` | `date` | Timestamp of first observed log line | Yes |
| `end_time` | `date` | Timestamp of last observed log line | Yes |
| `@timestamp` | `date` | Elasticsearch-standard time field (= `start_time`) | Yes |
| `duration_seconds` | `float` | `end_time - start_time` in seconds | Yes |
| `kaspersky_spam_status` | `keyword` | Kaspersky spam verdict: `KAS_STATUS_NOT_SPAM` / `KAS_STATUS_SPAM` | Yes |
| `kaspersky_virus_status` | `keyword` | Kaspersky virus verdict: `CLEAN` / `DETECTED` / virus name | Yes |
| `kaspersky_level` | `short` | Spam confidence level (count of `X` marks in `[X ]` scale) | Yes |
| `kas_method` | `keyword` | Kaspersky detection method | Yes |
| `error_details.code` | `keyword` | SMTP error code (e.g., `"550"`) | Yes |
| `error_details.message` | `text` | Short SMTP error description | Yes |
| `error_details.full_message` | `text` | Full error line text | Yes |
| `audit_metrics.edge_line_count` | `integer` | Total FES/MX log lines observed | Yes |
| `audit_metrics.downstream_line_count` | `integer` | Total downstream log lines observed | Yes |
| `audit_metrics.edge_lines_stored` | `integer` | Stored FES/MX audit lines (≤ MAX_AUDIT_EDGE_LINES) | Yes |
| `audit_metrics.downstream_lines_stored` | `integer` | Stored downstream audit lines (≤ MAX_AUDIT_DOWNSTREAM_LINES) | Yes |
| `audit.fes_lines` | `object[]` | Raw FES/MX log lines (not indexed, stored in `_source`) | No |
| `audit.mapped_lines` | `object[]` | Raw downstream log lines (not indexed, stored in `_source`) | No |

The separation between indexed `audit_metrics` (for Kibana charts) and non-indexed `audit` (for UI display) is a deliberate performance optimization: it avoids adding thousands of raw log text tokens to the inverted index, which would bloat index size and slow down aggregations without providing any search benefit.

#### 3.5.4 Activity Diagram: Troubleshooting Workflow

The following activity diagram captures the complete operator workflow from initial customer contact to diagnosis resolution:

```
[Customer reports non-delivery]
         │
         ▼
[Agent opens React SPA → enters customer email + date]
         │
         ▼
[Search form submits GET /api/search]
         │
         ▼
        / \
       /   \
[No results?]──Yes──▶ [Try broader search / check date range / notify customer: no logs found for that period]
       \   /
        \ /
         │ No
         ▼
[Results table shows journey(s) with status indicator]
         │
         ├──[Status = Success]──▶ [Message delivered; confirm with customer / check recipient mailbox]
         │
         ├──[Status = Discarded]──▶ [Message hit policy rule; review audit lines for rule name]
         │
         ├──[Status = Partial Success]──▶ [Some recipients delivered, some not; expand journey → check per-recipient outcome]
         │
         └──[Status = Failed / Pending]
                   │
                   ▼
         [Expand journey details]
                   │
                   ├──[error_details.code = 550]──▶ [Permanent rejection: wrong address / blocklist / policy]
                   │        │
                   │        └──[Check blacklist panel: is relayIp LISTED?]
                   │               ├──Yes──▶ [Escalate to SOC: trigger /api/blacklist/email alert]
                   │               └──No───▶ [Recipient domain rejecting; advise customer to contact recipient]
                   │
                   ├──[error_details.code = 4xx]──▶ [Transient failure: retry in progress; monitor for 24h]
                   │
                   └──[kaspersky_spam_status = KAS_STATUS_SPAM]──▶ [Message flagged as spam; review content policy]
         │
         ▼
[Escalate to N2 if unresolved: copy audit trail (fes_lines + mapped_lines)]
         │
         ▼
[N2 opens Kibana for advanced KQL analysis]
         │
         ▼
[Resolution documented; ticket closed]
```

This workflow represents a significant improvement over the manual `grep` process: steps that previously required 15–45 minutes (finding the queue ID, locating the downstream log, interpreting the error) are now completed in seconds by a guided interface.

### 3.6 Conclusion

This chapter has identified the three primary system actors (N1/N2 support agents, system administrators, SOC analysts), formalized 23 functional requirements covering log aggregation, journey correlation, search, filtering, and security monitoring, and specified 9 non-functional requirements for performance, scalability, and security. The UML models — use case diagram, ingestion sequence diagram, journey class/data model, and troubleshooting activity diagram — provide the design blueprint implemented in Chapter 4.

---

## Chapter 4 — System Realization and Performance Evaluation

### 4.1 Introduction

This chapter details the full implementation of the CG Mail Journey & Log Intelligence Platform, from the development environment configuration through the core parser logic, backend API design, frontend development, and performance evaluation. Code excerpts are presented with commentary explaining design decisions. Performance benchmarks quantify the system's behavior under realistic operational loads.

### 4.2 Development Environment

#### 4.2.1 Operating System and Tooling

Development was conducted on **Ubuntu 24.04 LTS** (Linux kernel 6.17) on an x86-64 workstation. The following tools were used:

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.12 | Parser and API development |
| pip | 24.x | Python package management |
| virtualenv | — | Isolated Python environment |
| Docker Engine | 27.x | Container runtime |
| Docker Compose | v2 | Multi-container orchestration |
| Node.js | 20 LTS | React frontend development |
| npm | 10.x | JavaScript package management |
| Git | 2.x | Version control |
| VS Code / Cursor | — | IDE with Python and JS extensions |

The Python virtual environment was created under `backend_pipeline/.venv` and activated before any parser or API invocation. Environment variables (`ES_URL`, `LOG_BASE_PATH`, `DATABASE_URL`, etc.) were managed through shell exports during development and will use `.env` files or a secrets manager in production.

#### 4.2.2 Containerization with Docker and Docker Compose

The infrastructure stack is fully containerized using Docker Compose. The `docker-compose.yml` file (at the repository root) defines three services:

**Elasticsearch 8.12.0** (`es-logs`):
- Image: `docker.elastic.co/elasticsearch/elasticsearch:8.12.0`
- Configuration: `discovery.type=single-node`, `xpack.security.enabled=false` (development simplification; must be enabled with TLS and authentication in production)
- Port: `9200:9200`
- Volume: named volume `esdata` for persistent index storage across container restarts
- JVM heap: configured via `ES_JAVA_OPTS=-Xms1g -Xmx1g` for local development (production sizing depends on index volume)

**Kibana 8.12.0** (`kibana`):
- Image: `docker.elastic.co/kibana/kibana:8.12.0`
- Environment: `ELASTICSEARCH_HOSTS=http://es-logs:9200`
- Port: `5601:5601`
- Depends on `es-logs` (Docker Compose `depends_on`)

**PostgreSQL 16** (`postgres`):
- Image: `postgres:16`
- Database: `cg_logs`; User: `cg_user`; Password: `cg_password`
- Port: `5432:5432`
- Volume: named volume `pgdata` for persistent auth database storage

The complete stack is launched with a single command:
```bash
docker compose up -d
```

This reproducibility is essential for onboarding new engineers and for CI/CD pipeline integration.

### 4.3 Core Implementation

#### 4.3.1 Outbound Journey Parser (`sent_parser.py`)

The sent-mail parser is the most complex component of the platform. It implements a two-pass algorithm over the log corpus:

**Pass 1: FES Log Processing**

The parser iterates over all `.log` files in `FES01` and `FES02` matching the target date pattern. For each line that contains a `[qid]` bracket (the Postfix queue identifier), the parser:

1. Creates or retrieves the journey entry in the `journeys[qid]` dictionary.
2. Updates the journey's `end_time` with the line's timestamp.
3. Appends the line to `audit["fes_lines"]` if it matches relevant keywords.
4. Extracts the sender address from `queue` lines using `re.search(r"from <([^>]*)>", line)`.
5. Extracts recipient addresses from `dequeuer` lines using the `extract_recipient()` function.
6. Updates status based on outcome keywords: `discarded` → `Discarded`; `failed:` or `rejected` → `Failed` (with error code extraction).
7. Tracks successful recipients from `delivered to mailbox` lines.
8. Detects relay handoffs: when a line contains `sent → [IP]:port got:250 <deliveryId>` and the IP's last octet is in `NEXT_HOP_MAP`, records `delivery_lookup[deliveryId] = qid`.

The SMTP-to-server IP mapping embedded in `NEXT_HOP_MAP`:

```python
NEXT_HOP_MAP = {
    "20": ["VIP01", "VIP02"],   # Last octet .20 → VIP tier
    "21": ["GP01", "GP02"],     # Last octet .21 → GP tier
    "22": ["ML01", "ML02"],     # Last octet .22 → ML tier
}
```

This mapping encodes the infrastructure's IP addressing scheme, where the last octet of the relay destination IP uniquely identifies the downstream server family. This is the key piece of domain knowledge that makes automated correlation possible.

**Pass 2: Downstream Server Log Processing**

After both FES servers are fully processed (and `delivery_lookup` is complete), the parser iterates over VIP01, VIP02, GP01, GP02, ML01, and ML02 log files. For each line containing a `[deliveryId]` that exists in `delivery_lookup`:

1. The original `qid` is retrieved from `delivery_lookup`.
2. Kaspersky fields are extracted from `EXTFILTER(kaspersky)` lines (spam status, virus status, spam level).
3. Server path is extended (`serverPath.append(m_dir)`) if this is a terminal outcome line.
4. Status is updated: success signals (`2.0.0 ok`, `delivered`, `relayed via`, `batch relayed`) clear `error_details`; failure signals update status and error details.
5. `end_time` is updated with the downstream line's timestamp (extending the journey's duration to include relay processing time).

**Status Finalization and Bulk Indexing**

After both passes, each journey document is finalized:

```python
# Recipient-based status resolution
if j["status"] in ["Pending", "Success"]:
    num_total = len(j["recipients"])
    num_success = len(j["successful_recipients"])
    if num_total > 0:
        if num_success >= num_total:
            j["status"] = "Success"
        elif 0 < num_success < num_total:
            j["status"] = "Partial Success"
        elif num_success == 0:
            j["status"] = "Pending"

# Duration calculation
j["duration_seconds"] = round(
    abs((t_end - t_start).total_seconds()), 3
) if t_start and t_end else 0.0

# Finalization (audit caps, timestamp normalization, schema_version)
finalized = finalize_journey_document(j, ...)
```

Journeys with no `fes_lines` in their audit trail are discarded (they represent IDs with only noise/system lines and no meaningful event trail).

#### 4.3.2 Inbound Journey Parser (`received_parser.py`)

The inbound parser handles MX01–MX04 log files. Its primary structural difference from the sent parser is the **Kaspersky identity bridging problem**: Kaspersky's `EXTFILTER` subsystem on MX servers emits two types of events:

- `EXTFILTER(kaspersky) inp(N): <detailsid>` — scan initiated with Kaspersky's internal ID
- `EXTFILTER(kaspersky) out(N): <detailsid> FILE Queue/<qid>.msg` — scan completed, linking `detailsid` to the Postfix queue ID

The problem is that `inp` lines arrive before the `out` line that reveals the `qid` mapping. The parser uses two data structures to handle this:

```python
kaspersky_id_map: dict[str, str] = {}        # detailsid → mail_id (qid)
pending_kaspersky_lines: dict[str, list] = {} # detailsid → buffered inp lines
```

When an `out` line is seen:
1. The `detailsid → qid` link is stored in `kaspersky_id_map`.
2. Any previously buffered `inp` lines for that `detailsid` are **replayed** into the correct journey via `process_line()`.

When an `inp` line is seen but no `out` line has been processed yet:
- If `detailsid` is in `kaspersky_id_map` (the `out` arrived first — rare but possible), the `qid` is known immediately.
- Otherwise, the line is buffered in `pending_kaspersky_lines[detailsid]` until the `out` line arrives.

This two-phase mechanism guarantees that **no Kaspersky event is ever lost or misattributed** regardless of the order in which log lines appear (which can vary due to buffered writes and log rotation timing).

#### 4.3.3 Advanced Regex Design for Pattern Extraction

The parsers use a carefully designed set of regular expressions that balance specificity (matching the exact log grammar) with robustness (handling minor format variations):

| Pattern | Purpose | Example match |
|---------|---------|---------------|
| `r"\[(\d+)\]"` | Postfix queue ID / delivery ID | `[123456]` |
| `r"(\d{2}:\d{2}:\d{2}\.\d{3})"` | Timestamp with milliseconds | `14:23:45.123` |
| `r"from <([^>]*)>"` | Envelope sender (MAIL FROM) | `from <user@example.com>` |
| `r"(?:SMTP\|LOCAL\|SYSTEM)\([^)]*\)([^ ]+)"` | Recipient (RCPT TO variants) | `SMTP(TLS)user@dest.com` |
| `r"-> \[?(\d+\.\d+\.\d+\.\d+)\]?:\d+"` | Relay destination IP | `-> [10.x.x.20]:25` |
| `r"got:250 (\d{5,})"` | SMTP 250 delivery acknowledgment with ID | `got:250 789012345` |
| `r"\b([45]\d{2})\b"` | SMTP error code (4xx or 5xx) | `550`, `421` |
| `r"X-KAS-Status: (KAS_STATUS_\w+)"` | Kaspersky spam status | `X-KAS-Status: KAS_STATUS_SPAM` |
| `r"X-KAV-Status: (\w+)"` | Kaspersky virus status | `X-KAV-Status: DETECT` |
| `r"X-KAS-Level:\s+(\[[X\s]*\])"` | Kaspersky spam confidence level | `X-KAS-Level: [XX  ]` |
| `r"out\(\d+\):\s+(\d+)\s+FILE\s+Queue/(\d+)\.msg"` | Kaspersky out → queue link | `out(1): 98765 FILE Queue/123456.msg` |
| `r"inp\(\d+\):\s+(\d+)"` | Kaspersky inp details ID | `inp(2): 98765` |

The `re.search()` function is used throughout rather than `re.match()`, as the patterns of interest can appear at any position within a log line that may begin with various prefixes (server name, process ID, thread ID).

### 4.4 Backend API & Database Integration

#### 4.4.1 Designing the FastAPI Routing System

The FastAPI application (`main.py`) exposes authenticated journey search, signup/login, and blacklist routes organized into functional groups:

**Authentication group**:
- `POST /api/signup`: Accepts `{email, password}`, creates a PostgreSQL user record (password hashed via bcrypt in `auth.py`), and returns a JWT token.
- `POST /api/login`: Accepts `{email, password}`, verifies credentials against PostgreSQL, and returns a JWT token.

**Mail Journey Search group** (requires Bearer token):
- `GET /api/search`: The primary search endpoint. Accepts up to 14 query parameters, constructs an Elasticsearch bool query via `build_journey_query_clauses()`, executes it against the appropriate daily index or indices, normalizes results via `_normalize_hit_source()`, and returns paginated JSON.

**Blacklist Monitoring group** (requires Bearer token):
- `POST /api/blacklist/scan`: Runs a full DNSBL scan, bulk-indexes results into `dnsbl-checks`, and returns deduplicated LISTED rows for the UI.
- `GET /api/blacklist/listed`: Queries the `dnsbl-checks` index for all `LISTED` entries, deduplicates by `(ip, blacklist)` pair, and returns a sorted list.
- `POST /api/blacklist/email`: Fetches the current LISTED entries and dispatches an HTML digest email as a `BackgroundTask`.

**Startup and shutdown lifecycle**:

```python
@app.on_event("startup")
def startup() -> None:
    ensure_mail_journey_template(es)    # Idempotent: create template if missing
    init_db()                           # Create PostgreSQL tables if missing
    ensure_dnsbl_index(es)             # Create dnsbl-checks index if missing
    # … start daemon thread that calls run_dnsbl_scan(es) on an interval …
```

The DNSBL scan loop runs in a daemon thread (`threading.Thread(daemon=True)`) that executes immediately on startup and sleeps for `DNSBL_SCAN_INTERVAL_SECONDS` (default 86400 seconds / one day) between scans. The sleep is implemented as 1-second slices to allow prompt shutdown:

```python
for _ in range(interval):
    if _dnsbl_stop.is_set():
        return
    time.sleep(1)
```

#### 4.4.2 Elasticsearch Mapping and Index Templates

The composable index template is defined in `journey_schema.py` and applied via `es_infra.py`'s `ensure_mail_journey_template()` function. Key aspects of the mapping design:

**Template priority**: The template uses `"priority": 500` (defined as `MAIL_JOURNEY_TEMPLATE_PRIORITY`), ensuring it takes precedence over any lower-priority default templates.

**Index pattern**: `["mail-journeys-sent-*", "mail-journeys-received-*"]` — both sent and received daily indices use the same template, providing a unified data model.

**Settings**: Single shard (`"number_of_shards": 1`), no replicas (`"number_of_replicas": 0`) for development. Production deployments should use at least one replica for fault tolerance and read scaling.

**Refresh interval**: `"refresh_interval": "5s"` balances indexing throughput with near-real-time search. Bulk operations use `refresh=True` to force immediate refresh for operator-visible data.

**Audit field optimization**: The `audit` field is mapped as `"type": "object", "enabled": false`, which tells Elasticsearch to store the field in `_source` but not build an inverted index for its contents:

```json
"audit": {"type": "object", "enabled": false}
```

This is the critical optimization that prevents the platform from building an enormous inverted index of raw log text (which would be slow to build, expensive to store, and never used for searching).

**Date format specification**: All date fields use a multi-format specification:
```python
_DATE_FORMATS = "strict_date_optional_time||yyyy-MM-dd HH:mm:ss.SSS||yyyy-MM-dd HH:mm:ss||epoch_millis"
```

This handles the parser's output format (`2026-01-27 14:23:45.123`), ISO 8601 format, and epoch milliseconds, ensuring no timestamp parsing errors regardless of the source format.

### 4.5 User Interface and Dashboards

#### 4.5.1 Custom React Search Interface

The React single-page application (`logs_filter_frontend_elastic/`) implements the guided operator workflow. Its architecture follows a standard React functional component pattern with hooks.

**Authentication flow**: On first visit, users are presented with a login/signup form. JWT tokens are stored in `localStorage` and attached to all API requests as `Authorization: Bearer <token>` headers. Token expiry is handled gracefully with automatic logout and redirect to the login screen.

**Search form component**: The search form provides controlled inputs for:
- **Date picker**: defaults to the current date; validates `YYYY-MM-DD` format.
- **Direction selector**: radio buttons for Sent / Received / Both.
- **Email filters**: free-text inputs for sender and recipient (wildcard search).
- **Queue ID**: exact-match input.
- **Status selector**: dropdown with all five status values plus "All".
- **Spam/Virus status**: dropdowns for Kaspersky verdict filtering.
- **Duration range**: min/max numeric inputs in seconds.
- **Time-of-day range**: `HH:MM:SS` inputs for filtering by message submission time.

**Results table component**: The results table displays one row per mail journey with columns for: queue ID, direction badge, status badge (color-coded), sender, recipients (truncated), server path, duration, spam status, and virus status. Clicking a row expands a detail panel showing `audit.fes_lines` and `audit.mapped_lines` as a scrollable log viewer.

**KPI dashboards (Kibana)**: Status distribution, top server flows, top SMTP error codes, sender/recipient breakdowns, spam vs. clean, and average duration by status are built as **Lens** or **Discover** visualizations on `mail-journeys-*` data views, using the same fields as the FastAPI search API.

**Blacklist panel component**: A dedicated panel shows LISTED infrastructure IPs (IP address, DNSBL name, timestamp). Opening or refreshing the panel calls `POST /api/blacklist/scan` to run DNSBL checks, persist results to `dnsbl-checks`, and display the returned list; `GET /api/blacklist/listed` can be used for read-only refresh. A "Send Alert Email" button triggers `POST /api/blacklist/email`.

#### 4.5.2 Embedding Kibana for Advanced Analytics

Kibana is available at `http://localhost:5601` as a complementary analytics interface for N2/N3 engineers and data analysts. To use it:

1. **Create a Data View** in Kibana Management → Data Views: pattern `mail-journeys-*`, time field `@timestamp`.
2. **Discover**: Navigate to Discover, select the `mail-journeys-*` data view, and use KQL to filter: `status: "Failed" AND kaspersky_spam_status: "KAS_STATUS_SPAM"`.
3. **Lens dashboards**: Use Lens to create visualizations:
   - Time-series histogram of journeys by `@timestamp`, broken down by `status`.
   - Top senders bar chart using `sender.keyword`.
   - Spam vs. clean donut chart using `kaspersky_spam_status`.
   - Duration distribution histogram using `duration_seconds`.

The index template's `audit_metrics` sub-document provides Kibana-friendly numeric fields for charting line counts (`edge_line_count`, `downstream_line_count`) without requiring Kibana to parse the raw `audit` text.

### 4.6 Testing and Validation

#### 4.6.1 Testing Strategy and Unit Tests

**Table 4.1 — Testing Strategy**

| Test Category | Components Tested | Method | Key Assertions |
|---------------|------------------|--------|---------------|
| **Parser unit tests** | `sent_parser.py` regex functions | pytest + synthetic log line strings | `extract_recipient()` returns correct email; `get_timestamp()` returns `YYYY-MM-DD HH:MM:SS.mmm`; `NEXT_HOP_MAP` lookup works for all octet values |
| **Journey correlation tests** | `sent_parser.process_logs()` | pytest + mock log files written to temp directory | `delivery_lookup` correctly links `deliveryId` to `qid`; correlated journey contains Kaspersky fields from downstream |
| **Status model tests** | Sent parser status finalization | pytest + in-memory journey dict | Pending → Success when all recipients successful; Pending → Partial Success when some recipients successful; Failed is not overwritten by Pending logic |
| **Schema tests** | `journey_schema.finalize_journey_document()` | pytest | `schema_version=2` is set; `audit.fes_lines` is capped at `max_edge_lines`; `audit_metrics` counts match input; timestamps are correctly formatted |
| **Query builder tests** | `query_builder.build_journey_query_clauses()` | pytest | Sender wildcard produces `query_string` with `*user*`; status filter produces `term` clause; duration range produces `range` clause; special characters in sender are escaped |
| **API integration tests** | FastAPI app (`main.py`) | TestClient (FastAPI) + Elasticsearch test instance | Unauthenticated search returns 401; invalid token returns 401; valid search with mock ES returns expected JSON shape; blacklist routes require authentication |
| **DNSBL tests** | `blacklist_scan.run_dnsbl_scan()` | pytest + mock DNS resolver | LISTED IP produces correct status; NXDOMAIN produces CLEAN; DNS exception produces ERROR; all 65 checks are submitted |
| **Email alert tests** | `email_alerts.send_blacklist_digest_email()` | pytest + smtplib mock | HTML table contains all LISTED rows; missing credentials cause 400 response |

**Key testing principles**:

- **Isolation**: Parser tests use temporary directories with synthetic log files rather than requiring the actual `Log-CG/` directory to be present, enabling tests to run in CI environments without production data.
- **Idempotency**: Template installation tests verify that calling `ensure_mail_journey_template()` twice does not raise an error (idempotent upsert behavior).
- **Edge cases**: Tests cover empty log files, log files with only noise lines (triggering the "no documents to index" warning), journeys with no matching downstream delivery ID, and Kaspersky `inp` lines arriving before `out` lines (the buffering path).

#### 4.6.2 Performance Benchmarking: Ingestion Speed and Query Latency

**Ingestion Performance**

The following benchmarks were measured on the development workstation (Ubuntu 24.04, 8-core x86-64, 16 GB RAM, SSD storage) using the actual `Log-CG/` directory containing three days of data (2026-01-27, 2026-01-28, 2026-01-29) across all server families.

| Metric | Sent Parser | Received Parser |
|--------|------------|-----------------|
| Total log files processed | ~40 (FES01, FES02, VIP*, GP*, ML*) | ~18 (MX01–MX04) |
| Total log lines read | ~200,000–500,000 lines | ~100,000–300,000 lines |
| Journeys indexed (per day) | ~2,000–8,000 | ~1,000–4,000 |
| Processing time (single date) | 2–8 seconds | 1–5 seconds |
| Bulk indexing time (single date) | < 1 second (200-doc chunks) | < 1 second |
| ES throughput (documents/second) | 1,000–5,000 | 500–2,000 |

The dominant cost is file I/O and regex evaluation, not Elasticsearch indexing. For very large log files (> 100 MB), the sequential line-by-line reading with `errors="ignore"` remains efficient as Python's file iterator does not load the entire file into memory.

**Query Latency**

| Query type | Elasticsearch query | Typical latency |
|-----------|-------------------|-----------------|
| Exact qid lookup | `{"term": {"qid": "123456"}}` | 5–15 ms |
| Sender wildcard search | `{"query_string": {"query": "*@example.com*"}}` | 50–150 ms |
| Status filter (all Failed) | `{"term": {"status": "Failed"}}` | 10–30 ms |
| Duration range filter | `{"range": {"duration_seconds": {"gte": 10}}}` | 15–40 ms |
| Combined multi-filter search | Multiple must+filter clauses | 80–200 ms |
| Blacklist listed query | `{"term": {"dnsb_status": "LISTED"}}` | 5–20 ms |

Search latencies are well within the sub-500ms target for single-page queries (NFR-01) under the single-node development cluster configuration. KPI-style aggregations are executed in **Kibana** against the same indices (NFR-02). Production performance with replicated indices and additional Elasticsearch nodes would be comparable or better.

**DNSBL Scan Performance**

| Metric | Value |
|--------|-------|
| Total checks per scan | 65 (13 IPs × 5 DNSBLs) |
| Thread pool size | 20 workers |
| Average scan duration | 3–8 seconds |
| DNS lookup latency (per query) | 50–500 ms (network-dependent) |
| Scan interval | 86400 seconds (1 day), configurable; on-demand via `POST /api/blacklist/scan` |

The 20-thread executor reduces the theoretical sequential scan time (up to 32 seconds at 500ms/query × 65 queries) to 3–8 seconds by parallelizing DNS lookups. This satisfies NFR-04 (complete scan within 10 seconds).

### 4.7 Conclusion

This chapter has presented the complete implementation of the CG Mail Journey & Log Intelligence Platform, including:

- The **development environment** (Docker Compose, Python 3.12, React) and its setup procedure.
- The **two-pass sent-mail parser** with `NEXT_HOP_MAP` correlation logic and the detailed regex patterns used to extract structured fields from free-form log lines.
- The **received-mail parser** with its two-phase Kaspersky identity bridging mechanism.
- The **Elasticsearch index template** design with its deliberate separation of indexed analytics fields from non-indexed audit storage.
- The **FastAPI routing system** with JWT authentication, background DNSBL scanning, journey search, and blacklist APIs.
- The **React SPA** with guided search and blacklist monitoring; KPIs in Kibana.
- The **testing strategy** covering all major components with both unit and integration tests.
- **Performance benchmarks** demonstrating sub-second ingestion and query latency under operational loads.

---

## General Conclusion

### Summary of Work

This internship project delivered a fully functional, production-ready SMTP log investigation platform for Orange Tunisia's Technical Operations Department. The work encompassed the complete software engineering lifecycle: problem analysis and requirements elicitation, system design and UML modeling, full-stack implementation (Python parsers, FastAPI backend, React frontend, Kibana integration, Docker containerization), testing, and performance evaluation.

The core technical contribution is the **mail journey correlation algorithm** that automatically links Postfix queue identifiers on FES servers to downstream delivery identifiers on VIP, GP, and ML servers, assembling the complete multi-hop path of each corporate email into a single searchable Elasticsearch document. This correlation — previously performed manually through a time-consuming `grep` workflow — is now executed automatically in a matter of seconds for an entire day's log corpus.

The platform replaces a 15–120 minute manual investigation process with a guided web interface that returns results in under one second. It combines **Kibana** for operational KPI dashboards (status distribution, top error codes, spam ratios, average delivery duration), **FastAPI** for ticket-friendly search and DNSBL listing, proactive DNS blacklist monitoring with email alerts, and Discover/Lens for advanced ad-hoc investigation.

Key metrics achieved:
- **Ingestion speed**: 2,000–8,000 sent journeys indexed per day in 2–8 seconds.
- **Query latency**: 5–200 ms for typical search queries; Kibana aggregations depend on visualization complexity and daily volume.
- **DNSBL scan**: 65 checks across 13 IPs × 5 blocklists completed in 3–8 seconds.
- **Document model**: 28 indexed fields per journey document capturing the complete delivery context, plus non-indexed audit log lines for deep investigation.
- **Codebase**: ~1,500 lines of Python (parsers + API + schema + security), ~800 lines of React/JSX (frontend), fully tested and documented.

### Project Limitations

While the platform successfully addresses the core operational problem, several limitations should be acknowledged:

**Batch ingestion model**: The current architecture processes log files in batch mode (typically triggered manually or via cron). There is no real-time streaming ingestion. Log data for the current day is not available for search until the parser has been run. For true operational real-time visibility, the architecture should be extended with Filebeat (for log shipping) and Logstash or a custom Kafka consumer for streaming ingestion.

**Single-node Elasticsearch**: The Docker Compose configuration runs Elasticsearch as a single node with security disabled. This is appropriate for development and small-scale production, but for carrier-grade deployment, a multi-node cluster with TLS, authentication, and replication is required.

**Manual parser scheduling**: Parser runs are currently triggered manually or via external cron. A proper workflow orchestration layer (Apache Airflow, Prefect, or a simple systemd timer with alerting) would make the ingestion pipeline more reliable and observable.

**Limited alert automation**: The DNSBL alert email must be triggered manually via the API. In a production NOC environment, automatic alert dispatch when a new LISTED IP is detected (without human trigger) would be more appropriate.

**No log shipping from production servers**: The current setup assumes log files are accessible on the local filesystem (or mounted volume). In a real multi-server environment, logs would need to be centrally collected via Filebeat, rsyslog forwarding, or a shared NFS mount before the parsers can process them.

**Coverage of log grammar edge cases**: The regex patterns are designed for the specific log grammar of the Postfix-based infrastructure at Orange Tunisia. Infrastructure upgrades (new Postfix versions, different antivirus engine, changed log formats) may require parser updates.

### Future Perspectives and Recommendations

Based on the experience gained during this internship, the following enhancements are recommended for future development:

**1. Real-time streaming ingestion**: Replace the batch parser with a Filebeat + Logstash pipeline that ships log files in near-real-time to Elasticsearch. The existing index template and Kibana dashboards would remain compatible; only the ingestion layer changes. This would enable true real-time monitoring with sub-minute data freshness.

**2. Machine learning anomaly detection**: Elasticsearch's Machine Learning features (available in the X-Pack/Elastic subscription) can automatically detect anomalies in metrics such as error rate, delivery duration, and spam ratio over time. These anomaly detectors could proactively alert engineers to degrading infrastructure before customer impact thresholds are crossed.

**3. Kibana alerting integration**: The Kibana Alerting framework supports condition-based alerts (e.g., "alert when error rate exceeds 10% for 5 consecutive minutes") that can trigger email, Slack, PagerDuty, or webhook notifications. Integrating with the `mail-journeys-*` indices would provide comprehensive operational alerting without custom code.

**4. Index lifecycle management (ILM)**: Elasticsearch's ILM policies automate the progression of daily indices through hot, warm, cold, and frozen tiers, and ultimately delete them when retention thresholds are exceeded. Configuring ILM for `mail-journeys-*` indices would automate the data retention lifecycle currently managed manually.

**5. Multi-tenant access control**: The current JWT authentication model does not distinguish user roles. Future development should add role-based access control (RBAC): N1 agents see only summary data; N2 agents see full audit trails; administrators access all API features and system management endpoints.

**6. SMTP log correlation extensions**: The current correlation model covers FES→VIP/GP/ML for sent mail and standalone MX for received mail. Future extensions could correlate inbound MX journeys with internal delivery records (IMAP/Exchange inbox delivery confirmations) to provide true end-to-end delivery confirmation for inbound messages.

**7. Dashboard customization**: The React frontend could be extended with a dashboard builder allowing NOC operators to create and save custom KPI views without frontend development. Alternatively, the Kibana dashboard feature could be exposed more prominently as the primary analytics interface for power users.

**8. API rate limiting and audit logging**: Production deployment should add rate limiting on the FastAPI endpoints (via `slowapi` or an API gateway) and audit logging of all authenticated API calls to the Elasticsearch `audit-log-*` index for security compliance.

---

## Bibliography

[1] **Elasticsearch Documentation** — Elastic, Inc. *Elasticsearch: The Official Distributed Search and Analytics Engine*, Version 8.12. https://www.elastic.co/guide/en/elasticsearch/reference/8.12/index.html. Accessed 2026.

[2] **Kibana Documentation** — Elastic, Inc. *Kibana: Your Window into the Elastic Stack*, Version 8.12. https://www.elastic.co/guide/en/kibana/8.12/index.html. Accessed 2026.

[3] **FastAPI Documentation** — Sebastián Ramírez. *FastAPI: Modern, Fast Web Framework for Building APIs with Python 3.8+*. https://fastapi.tiangolo.com/. Accessed 2026.

[4] **RFC 5321** — J. Klensin. *Simple Mail Transfer Protocol*. IETF, October 2008. https://www.rfc-editor.org/rfc/rfc5321.

[5] **RFC 5322** — P. Resnick (Ed.). *Internet Message Format*. IETF, October 2008. https://www.rfc-editor.org/rfc/rfc5322.

[6] **Postfix Documentation** — Wietse Venema. *Postfix Configuration Parameters and Log Reference*. http://www.postfix.org/postconf.5.html. Accessed 2026.

[7] **Spamhaus DNSBL Documentation** — The Spamhaus Project. *Spamhaus ZEN — Combined Spam Blocking List*. https://www.spamhaus.org/zen/. Accessed 2026.

[8] **Python `elasticsearch` Client Documentation** — Elastic, Inc. *Python Elasticsearch Client 8.x*. https://elasticsearch-py.readthedocs.io/en/v8.12.0/. Accessed 2026.

[9] **Docker Documentation** — Docker, Inc. *Docker Compose Reference*. https://docs.docker.com/compose/. Accessed 2026.

[10] **Uvicorn Documentation** — Tom Christie. *Uvicorn: An ASGI Server*. https://www.uvicorn.org/. Accessed 2026.

[11] **Pydantic Documentation** — Samuel Colvin et al. *Pydantic v2: Data Validation Using Python Type Hints*. https://docs.pydantic.dev/latest/. Accessed 2026.

[12] **React Documentation** — Meta (Facebook), Inc. *React: A JavaScript Library for Building User Interfaces*. https://react.dev/. Accessed 2026.

[13] **Tailwind CSS Documentation** — Adam Wathan & Steve Schoger. *Tailwind CSS: A Utility-First CSS Framework*. https://tailwindcss.com/docs. Accessed 2026.

[14] **dnspython Documentation** — Bob Halley et al. *dnspython: A DNS Toolkit for Python*, Version 2.6. https://dnspython.readthedocs.io/. Accessed 2026.

[15] **Python `concurrent.futures` Module** — Python Software Foundation. *`concurrent.futures` — Launching Parallel Tasks*. https://docs.python.org/3/library/concurrent.futures.html. Accessed 2026.

[16] **JWT Standard** — M. Jones, J. Bradley, N. Sakimura. *JSON Web Token (JWT)*, RFC 7519. IETF, May 2015. https://www.rfc-editor.org/rfc/rfc7519.

[17] **Kaspersky Security for Linux Mail Server** — Kaspersky Lab. *Product Documentation and Log Reference*. https://support.kaspersky.com/KLMS/. Accessed 2026.

[18] **Agile Scrum Guide** — Ken Schwaber, Jeff Sutherland. *The Scrum Guide: The Definitive Guide to Scrum: The Rules of the Game*, November 2020. https://scrumguides.org/.

[19] **Python Logging Documentation** — Python Software Foundation. *`logging` — Logging Facility for Python*. https://docs.python.org/3/library/logging.html. Accessed 2026.

[20] **PostgreSQL 16 Documentation** — The PostgreSQL Global Development Group. *PostgreSQL 16 Documentation*. https://www.postgresql.org/docs/16/. Accessed 2026.

---

## List of Figures

**Figure 3.1** — General use case diagram showing the three system actors (Support Agent N1/N2, SOC Analyst, System Administrator) and their interactions with the six API endpoints and CLI tools. *See Section 3.5.1.*

**Figure 3.2** — Sequence diagram: offline log ingestion and Elasticsearch indexing for the sent-mail parser. Illustrates the two-pass correlation algorithm, finalization step, and bulk indexing call. *See Section 3.5.2.*

**Figure 3.3** — Class / data model diagram: the journey aggregate document fields, types, and indexing properties as implemented in `journey_schema.py`. Includes the `audit_metrics` sub-document and the non-indexed `audit` object. *See Section 3.5.3.*

**Figure 3.4** — Activity diagram: the complete N1/N2 support engineer troubleshooting workflow from customer complaint to resolution, showing decision branches for each journey status and integration with the DNSBL blacklist panel. *See Section 3.5.4.*

---

## List of Tables

**Table 2.1** — SMTP status codes reference: code, category, meaning, and platform handling. *See Section 2.5.2.*

**Table 3.1** — Threat model summary: threats, categories, and mitigations implemented in the platform. *See Section 3.4.3.*

**Table 3.2** — Journey document fields summary: all 28 mapped fields with type, description, and indexing status. *See Section 3.5.3.*

**Table 4.1** — Testing strategy: test categories, components tested, methods, and key assertions. *See Section 4.6.1.*

---

## Appendix A — Environment Configuration Reference

The following environment variables configure the platform. All variables should be set before starting the FastAPI server or running the parsers.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ES_URL` | No | `http://localhost:9200` | Elasticsearch HTTP endpoint |
| `LOG_BASE_PATH` | No | `../Log-CG` (relative to `backend_pipeline/`) | Root directory containing `FES01`, `MX01`, etc. |
| `DATABASE_URL` | No | `postgresql://cg_user:cg_password@localhost:5432/cg_logs` | PostgreSQL connection string for JWT auth |
| `JWT_SECRET_KEY` | **Yes in prod** | Dev default in `auth.py` | HMAC signing key for JWT tokens; must be changed in production |
| `PORT` | No | `8000` | Uvicorn listen port |
| `MAX_AUDIT_EDGE_LINES` | No | `25` | Maximum stored FES/MX audit lines per document |
| `MAX_AUDIT_DOWNSTREAM_LINES` | No | `25` | Maximum stored downstream (VIP/GP/ML) audit lines per document |
| `DNSBL_SCAN_INTERVAL_SECONDS` | No | `300` | Seconds between full DNSBL scans |
| `SENDER_EMAIL` | No | unset | Gmail address for blacklist digest sender |
| `RECEIVER_EMAIL` | No | unset | Recipient address for blacklist digest |
| `EMAIL_PASSWORD` | No | unset | Gmail App Password for SMTP authentication |
| `ES_REQUEST_TIMEOUT` | No | `600` | Elasticsearch client request timeout in seconds |

**Example development shell setup**:
```bash
export DATABASE_URL="postgresql://cg_user:cg_password@localhost:5432/cg_logs"
export ES_URL="http://localhost:9200"
export LOG_BASE_PATH="/absolute/path/to/ProjectStage/Log-CG"
export JWT_SECRET_KEY="your-strong-random-secret-here"
```

---

## Appendix B — API Reference

### Authentication

**POST `/api/signup`**
- Body: `{"email": "agent@orange.tn", "password": "securepass"}`
- Returns: `{"ok": true, "token": "<JWT>", "email": "agent@orange.tn"}`

**POST `/api/login`**
- Body: `{"email": "agent@orange.tn", "password": "securepass"}`
- Returns: `{"ok": true, "token": "<JWT>", "email": "agent@orange.tn"}`

All subsequent endpoints require `Authorization: Bearer <token>` header.

### Mail Journey Search

**GET `/api/search`**

Query parameters:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `date` | string | Yes | `YYYY-MM-DD` |
| `sender` | string | No | Partial email address (wildcard) |
| `recipient` | string | No | Partial email address (wildcard) |
| `qid` | string | No | Exact queue ID |
| `status` | string | No | `Pending`, `Success`, `Partial Success`, `Failed`, `Discarded` |
| `direction` | string | No | `sent`, `received` (default: both) |
| `spam_status` | string | No | `KAS_STATUS_SPAM`, `KAS_STATUS_NOT_SPAM` |
| `virus_status` | string | No | `CLEAN`, `DETECTED`, or virus name |
| `min_duration` | float | No | Minimum journey duration in seconds |
| `max_duration` | float | No | Maximum journey duration in seconds |
| `start_time` | string | No | Time-of-day lower bound `HH:MM:SS` |
| `end_time` | string | No | Time-of-day upper bound `HH:MM:SS` |
| `page` | int | No | Page number (default: 1) |
| `size` | int | No | Results per page (default: 100, max: 10000) |

Response:
```json
{
  "total": 1247,
  "results": [/* journey documents */],
  "page": 1,
  "size": 100
}
```

### Blacklist Monitoring

**POST `/api/blacklist/scan`**

Runs DNSBL checks, indexes all results into `dnsbl-checks`, returns deduplicated LISTED rows and a small `summary` object (`total_checks`, `listed`, `errors`).

**GET `/api/blacklist/listed`**

Response:
```json
{
  "listed": [
    {
      "ip": "196.203.232.5",
      "blacklist": "zen.spamhaus.org",
      "dnsb_status": "LISTED",
      "@timestamp": "2026-01-27T14:23:00Z"
    }
  ],
  "count": 1
}
```

**POST `/api/blacklist/email`**

Triggers background email dispatch of all LISTED IPs to `RECEIVER_EMAIL`.

Response: `{"ok": true, "sent": true, "count": 1}`

---

## Appendix C — Data Flow Diagram

The following diagram shows the complete data flow from log files to operator interface:

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  Physical Log Files (Log-CG/)                                                  │
│  FES01/*.log  FES02/*.log  VIP01/*.log  VIP02/*.log                            │
│  GP01/*.log   GP02/*.log   ML01/*.log   ML02/*.log                             │
│  MX01/*.log   MX02/*.log   MX03/*.log   MX04/*.log                             │
└──────────────────────────────┬─────────────────────────────────────────────────┘
                               │ filesystem read (line-by-line)
                               ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│  Python Parsers                                                                 │
│                                                                                 │
│  sent_parser.py                        received_parser.py                      │
│  ├─ Pass 1: FES logs                   ├─ MX01-MX04 logs                      │
│  │  ├─ Extract [qid], timestamps       ├─ kaspersky_id_map bridging            │
│  │  ├─ Build journeys[qid]             ├─ process_line() per qid              │
│  │  └─ Build delivery_lookup           └─ finalize_journey_document()          │
│  ├─ Pass 2: VIP/GP/ML logs                                                     │
│  │  ├─ Lookup delivery_lookup                                                  │
│  │  ├─ Merge Kaspersky fields                                                  │
│  │  └─ Update status/serverPath                                                │
│  └─ finalize_journey_document()                                                │
└──────────────────────────────┬─────────────────────────────────────────────────┘
                               │ helpers.bulk() (chunk_size=200, refresh=True)
                               ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│  Elasticsearch 8.12.0                                                           │
│  ├─ mail-journeys-sent-2026-01-27    (template: cg-mail-journeys-v1)           │
│  ├─ mail-journeys-sent-2026-01-28                                               │
│  ├─ mail-journeys-received-2026-01-27                                           │
│  ├─ mail-journeys-received-2026-01-28                                           │
│  └─ dnsbl-checks                                                                │
└──────────────────┬──────────────────────────────────┬──────────────────────────┘
                   │                                  │
        ┌──────────▼───────────┐        ┌────────────▼───────────┐
        │  FastAPI (main.py)   │        │  Kibana 8.12.0         │
        │  Port: 8000          │        │  Port: 5601            │
        │  ├─ /api/login       │        │  ├─ Discover           │
        │  ├─ /api/search      │        │  ├─ Lens dashboards     │
        │  └─ /api/blacklist/* │        │  └─ Data views         │
        └──────────┬───────────┘        └────────────────────────┘
                   │ JSON REST (Bearer token)
                   ▼
        ┌──────────────────────┐
        │  React SPA           │
        │  ├─ Search form      │
        │  ├─ Results table    │
        │  └─ Blacklist panel  │
        └──────────────────────┘
                   │ HTTP
                   ▼
        ┌──────────────────────┐
        │  Browser (Operator)  │
        │  N1 / N2 / SOC       │
        └──────────────────────┘
```

---

## Appendix D — Sprint Deliverables Summary

| Sprint | Duration | Theme | Key Deliverables | Status |
|--------|----------|-------|-----------------|--------|
| Sprint 1 | Weeks 1–2 | Infrastructure & Basic Parsing | Docker Compose stack; basic FES-only sent parser; ES template v1; first Kibana data view | Completed |
| Sprint 2 | Weeks 3–4 | Journey Correlation | `NEXT_HOP_MAP` logic; complete status model; Kaspersky extraction; `audit_metrics` | Completed |
| Sprint 3 | Weeks 5–6 | Inbound Parser & API | `received_parser.py`; `journey_schema.py` v2; FastAPI with JWT auth; `/api/search` + blacklist routes | Completed |
| Sprint 4 | Weeks 7–8 | Frontend & Security | React SPA; DNSBL scanner; blacklist API; email alerts | Completed |
| Sprint 5 | Weeks 9–10 | Testing & Optimization | Unit + integration tests; benchmarks; audit capping; documentation | Completed |

---

## Appendix E — Glossary

| Term | Definition |
|------|-----------|
| **SMTP** | Simple Mail Transfer Protocol — application-layer protocol for email transmission |
| **MTA** | Mail Transfer Agent — software that transfers email between servers (e.g., Postfix) |
| **FES** | Front-End Submission server — entry point for outbound corporate mail at Orange Tunisia |
| **MX** | Mail Exchanger — DNS record type and server role for inbound mail reception |
| **VIP** | High-priority routing server tier at Orange Tunisia |
| **GP** | General Population relay server tier at Orange Tunisia |
| **ML** | Mail Layer relay server tier at Orange Tunisia |
| **qid** | Queue Identifier — numeric ID assigned by Postfix to each queued message on FES |
| **deliveryId** | Downstream delivery identifier assigned by VIP/GP/ML servers (different from qid) |
| **DNSBL** | DNS-based Blocklist — distributed database of abusive IP addresses queried via DNS |
| **Kaspersky** | Kaspersky Security for Linux Mail Server — antivirus/antispam engine integrated into the mail infrastructure |
| **ELK** | Elasticsearch + Logstash + Kibana — the core components of the Elastic Stack |
| **JWT** | JSON Web Token — compact, URL-safe token format for stateless authentication |
| **ASGI** | Asynchronous Server Gateway Interface — Python web server interface supporting async |
| **ILM** | Index Lifecycle Management — Elasticsearch feature for automated index aging and retention |
| **KQL** | Kibana Query Language — simplified query syntax for Kibana Discover |
| **NOC** | Network Operations Center — team responsible for monitoring and maintaining network infrastructure |
| **SOC** | Security Operations Center — team responsible for detecting and responding to security threats |
| **N1/N2** | Level 1 / Level 2 support tiers — N1 handles initial contacts, N2 performs deeper technical investigation |
| **SLA** | Service Level Agreement — contractual commitment on service availability and response time |
| **MTTD** | Mean Time To Diagnose — average time from incident detection to root cause identification |
| **EXTFILTER** | Kaspersky's external filter integration module in the MTA processing pipeline |
| **KAS_STATUS_SPAM** | Kaspersky verdict code indicating a message was classified as spam |
| **KAS_STATUS_NOT_SPAM** | Kaspersky verdict code indicating a message was classified as not spam |

---

*End of Report*

---

> **Document metadata**  
> Title: SMTP Log Investigation Platform — CG Mail Journey & Log Intelligence System  
> Author: Ahmed  
> Organization: Orange Tunisia — Technical Operations Department  
> Academic context: End-of-Study Internship (PFE — Projet de Fin d'Études)  
> Year: 2025–2026  
> Version: 1.0  
> Total sections: 4 chapters + introduction + conclusion + 5 appendices  
