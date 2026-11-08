# Event quality & crawl optimisations

Design doc for accuracy and crawl-cost improvements in `listgen` / `poc/backend`.  
**Status:** agreed slice implemented (presence, domain memory, hopeless prefilter, keyword gate, skip log). Listing-domain expansion still deferred.

---

## Goals

1. Keep fewer non-events in exports (Švica-class noise).
2. Spend less crawl time on hopeless / duplicate hosts.
3. Make every drop/skip auditable so we can tune without guessing.

Non-goals (deferred): growing `LISTING_DOMAINS` and expanding listing pages into official URLs; full lead-cleanup Claude skill.

---

## Pipeline stages (where gates apply)

```
Discovery (DDG)
  → soft filters / url_score / geo bonus
  → listing expand (known LISTING_DOMAINS only)
  → links CSV + deduped crawl queue
       [A] queue prefilter (don’t crawl)
  → crawl site (multi-page, same domain)
       [B] keyword gate (first page OR root) — don’t crawl deeper / don’t export
       [C] event presence (date + city allowlist) — don’t export
       [D] domain memory (one crawl per host / denylist)
  → extract contacts → confidence → lead rank
       [E] lead-level drops (future: email↔host, roles) — drop lead, crawl already done
  → export + skip log
```

### Drop lead vs don’t crawl

| Decision | Meaning | When |
|----------|---------|------|
| **Don’t crawl** | Never fetch (or stop before deep crawl). URL marked done / skipped. | Hopeless URL, denylisted host, domain already crawled this run, mill pattern, keyword gate fail with no JSON-LD Event |
| **Drop lead** | Pages may have been fetched; nothing (or no lead row) goes to Conferences/Leads export. | Presence fail (no date/city); later contact-quality rules |
| **Keep** | Export conference (+ leads if emails found). | Passed keyword (or JSON-LD Event) **and** presence |

Keyword miss with JSON-LD `@type=Event` → **keep going** (treat as pass for keyword gate).

---

## Already implemented

### 1. Event presence hard gate
- **Module:** `poc/backend/event_presence.py`
- **Rule:** day-level event date **and** city from country `city_allowlist` (expanded ~50+, aliases) on **any** crawled page of the site.
- **Hour:** optional; `+15` confidence if a clock time appears anywhere (`TIME_PRESENCE_BONUS`).
- **Wired in:** `pipeline.run_crawl_phase`, `listgen/runner.py` (skip export + fill `event_date` / `venue_city`).
- **Data:** `listgen/countries/europe.json` → `city_allowlist`; search still uses short `cities` list.
- **API:** `listgen/country_data.get_city_allowlist(country)`.

### 2. Same-run domain memory + persistent denylist
- **Module:** `listgen/domain_memory.py`
- **Same run:** at most **one crawl URL per host** (best `url_score`); after a host is crawled, other URLs on that host are skipped (first crawl already follows same-domain pages).
- **Future runs:** mill/listing **path/host patterns** → `listgen/output/domain_denylist.json`.
- **Presence fail:** same-run skip only; permanent deny only if mill/listing pattern.
- **Settings:** `crawl.one_url_per_domain`, `crawl.domain_denylist_file`.

### 3. Listing gateways (existing, limited list)
- **Config:** `LISTING_DOMAINS` / tickets in `poc/backend/config.py`
- **Behaviour:** resolve official outbound links; do not treat listing page as organizer site.
- **Not expanded in this workstream:** growing that list from Švica aggregators (deferred).

### 4. Queue prefilter: hopeless URLs (**don’t crawl**) — **SHIPPED**
- **Module:** `poc/backend/url_prefilter.py`
- Host / path / file / scheme denylists; applied in `build_crawl_queue` and runner.
- Reasons: `hopeless_host`, `hopeless_path`, `hopeless_file`, `hopeless_scheme`.

### 5. Keyword gate (first **or** root; JSON-LD Event exception) — **SHIPPED**
- **Modules:** `poc/backend/event_keyword_gate.py`, `poc/backend/event_keywords.py`
- Probe start URL + site root before deep crawl; pass on synonym hit or JSON-LD `@type=Event`.
- Language pack = region `event_synonyms` + EN + `CONFERENCE_KEYWORDS` + settings `extra_event_synonyms`.

### 6. Skip / drop reason log — **SHIPPED**
- **Module:** `listgen/skip_log.py`
- JSONL at `output.skip_log_file` (stamped per run); end-of-run counts by `stage/reason`.

---

## Deferred

| Item | Why |
|------|-----|
| Expand `LISTING_DOMAINS` + listing→official for Švica aggregators | Test current gates first |
| Abort-only-on-first-page without root check | Replaced by first **or** root keyword rule |
| Email domain ↔ conference host match | Lead-quality; after event gates |
| Synonym/field tightening in settings | Product tuning; separate change |
| Claude lead-cleanup skill | Separate track |

---

## Config sketch (planned)

```json
"crawl": {
  "one_url_per_domain": true,
  "domain_denylist_file": "listgen/output/domain_denylist.json",
  "require_event_keyword": true,
  "keyword_check_root": true
},
"filters": {
  "hopeless_hosts": ["..."],
  "hopeless_path_markers": ["..."],
  "hopeless_extensions": ["..."]
},
"output": {
  "skip_log_file": "listgen/output/skip_log.jsonl"
}
```

Prefer code defaults in `poc/backend/config.py` (or `listgen/filters.py`) with optional settings overrides.

---

## Implementation order (when coding starts)

1. **Skip log** infrastructure (helper + wire existing domain_memory / presence skips).
2. **Hopeless URL prefilter** (host / path / file) → queue + log `dont_crawl`.
3. **Language pack helper** shared with query synonyms.
4. **Keyword gate** (start ∪ root text, JSON-LD Event exception) → log; separate from presence.
5. Tests: hopeless URLs; keyword EN/DE; JSON-LD bypass; log line shape.
6. Manual: small country/`--test` run; inspect skip_log reason histogram.

---

## Acceptance checks

- [ ] WhatsApp / Google Calendar / `.pdf` never enter deep crawl; appear in skip log.
- [ ] Company homepage with no event synonym and no JSON-LD Event is dropped; reason `keyword_gate`.
- [ ] Page with JSON-LD `Event` but weak wording still proceeds to presence gate.
- [ ] Real event: keyword on `/` only, date on `/agenda` → still exported.
- [ ] Second URL same host skipped; log `domain_already_crawled`.
- [ ] Run summary prints skip counts by reason.

---

## File touch list (expected)

| Area | Files |
|------|--------|
| Hopeless filters | new `poc/backend/url_denylist.py` or `listgen/url_prefilter.py`; `links_export.build_crawl_queue`; `runner` |
| Keyword + language | `event_presence.py` or new `event_keyword_gate.py`; `country_data` / `regions` synonym helper |
| Skip log | new `listgen/skip_log.py`; `runner` (+ optional pipeline) |
| Settings | `listgen/settings.json`, `settings_loader.py` |
| Tests | `scripts/test_url_prefilter.py`, `scripts/test_keyword_gate.py`, extend presence tests |

---

## Decision log

| Date | Decision |
|------|----------|
| 2026-07-29 | Hard gate: date + allowlisted city; hour = confidence bonus only |
| 2026-07-29 | One crawl per domain per run; mill patterns → persistent denylist |
| 2026-07-29 | Defer listing-domain expansion until after test |
| 2026-07-29 | Keyword on **first or root**; JSON-LD Event exempts keyword miss |
| 2026-07-29 | Separate don’t-crawl vs drop-lead; log all skips |
| 2026-07-29 | Document before implementing queue denylist + keyword gate + skip log |
