# Conference Organizer Contact Finder App — Full Blueprint

## 1. Product Goal

Build a web app that finds conferences in specific fields and month ranges, extracts organizer/contact information from official sources, stores the data, assigns confidence scores, and allows export to CSV/Excel.

The app should focus on **reliable conference organizer intelligence**, not just scraping random event lists.

The app should answer questions like:

> “Find conferences in AI in healthcare happening in Europe between May and September 2027, and give me the organizer, sponsorship contacts, CFP contacts, program chairs, official website, source evidence, and confidence score.”

---

## 2. Core Use Case

The user enters:

```text
Field / topic: AI in healthcare
Region: Europe / worldwide / Slovenia / Germany / etc.
Start month: 2027-05
End month: 2027-09
Contact type: organizer / sponsorship / CFP / program chair / exhibitors
Max results: 20 / 50 / 100
```

The app returns a structured contact list:

| Conference | Date | Location | Organizer | Contact | Source | Confidence |
|---|---:|---|---|---|---:|
| Example Health AI Summit | May 2027 | Berlin | XYZ Events GmbH | sponsors@example.com | official site | 95% |
| Example Medical Informatics Conf | June 2027 | Vienna | University dept. / society | Program chair + email | CFP page | 80% |

The user can then review, edit, and export the results.

---

## 3. Important Product Positioning

Do **not** build this as a simple scraper.

Build it as a:

```text
conference discovery + organizer extraction + validation + CRM/export tool
```

The valuable part is not merely finding conferences. The valuable part is finding useful, source-backed contacts connected to business actions:

```text
- sponsorship contacts
- exhibitor contacts
- CFP contacts
- program chairs
- organizing societies
- organizing companies
- recurring conference series
- conference websites that have newly announced future dates
```

Best target users:

```text
- companies looking for sponsorship opportunities
- agencies doing conference outreach
- researchers looking for CFP deadlines
- sales teams looking for industry events
- consultants/speakers looking for event organizers
- marketing teams planning event calendars
```

---

## 4. Recommended MVP Stack

Recommended local-first MVP:

```text
Frontend: Next.js + Tailwind CSS
Backend: Python FastAPI
Database: PostgreSQL
Crawler: Playwright + BeautifulSoup
Background jobs: Celery + Redis, or local async jobs first
LLM extraction: local LLM or configurable OpenAI-compatible endpoint
Export: CSV/XLSX
```

Simplified first version:

```text
Frontend: Next.js
Backend: FastAPI
Database: SQLite first, PostgreSQL later
No login for MVP
Manual search trigger
CSV export
```

Suggested practical order:

```text
1. Backend + database + manual CRUD
2. CSV/XLSX export
3. Search provider integration
4. Official website detection
5. Website crawling
6. LLM extraction
7. Confidence scoring
8. Review/edit UI
9. Scheduled searches later
```

---

## 5. Main App Features

### 5.1 Search Form

The app should provide a form where the user can input:

```text
Field / topic
Region
Start month
End month
Contact type
Max results
```

Example:

```json
{
  "field": "AI in healthcare",
  "region": "Europe",
  "start_month": "2027-05",
  "end_month": "2027-09",
  "contact_type": "sponsorship",
  "max_results": 50
}
```

---

### 5.2 Query Generation

The app should generate multiple search queries from user input.

Example generated queries:

```text
"AI in healthcare conference Europe 2027"
"AI in healthcare summit Europe May 2027 sponsorship contact"
"AI in healthcare conference program committee 2027"
"AI in healthcare call for papers 2027"
"AI in healthcare congress exhibitors 2027"
"AI in healthcare conference sponsors 2027"
"AI in healthcare medical AI symposium 2027"
```

For month-specific searches, generate queries for each month in the selected range.

Example:

```text
"AI in healthcare conference May 2027 Europe"
"AI in healthcare conference June 2027 Europe"
"AI in healthcare conference July 2027 Europe"
```

---

### 5.3 Conference Discovery

Use a pluggable web search provider.

Create an interface like:

```python
class SearchProvider:
    def search(self, query: str, max_results: int) -> list[SearchResult]:
        ...
```

Possible providers:

```text
- Bing Search API
- SerpAPI
- Google Programmable Search
- Eventbrite API where applicable
- Manual mock provider for development
```

Each search result should include:

```text
title
url
snippet
source_query
rank
```

---

### 5.4 Official Website Detection

For each search result, identify likely official conference websites.

Prefer URLs that contain:

```text
- conference name or acronym
- event year
- official event domain
- society domain
- university domain
- known organizer domain
```

Avoid or deprioritize:

```text
- generic listing sites
- SEO spam pages
- duplicate event aggregators
- old conference editions unless useful
- pages with no official contact or organizer context
```

Generic listing sites can still be useful as discovery sources, but they should not receive the same confidence as official sources.

---

### 5.5 Official Website Crawling

For each official conference URL, crawl only a small set of relevant pages.

Allowed/relevant page types:

```text
home
about
contact
organizers
committee
program committee
sponsors
sponsorship
exhibitors
call for papers
cfp
registration
venue
```

Crawler rules:

```text
- stay on the same domain
- limit depth to 2
- limit pages per conference to 15
- prefer contact/sponsor/committee/organizer/CFP pages
- extract readable text
- store source URL, page title, and extracted text
- respect robots.txt where possible
- avoid aggressive crawling
```

Suggested tools:

```text
- Playwright for JavaScript-rendered pages
- BeautifulSoup for parsing HTML
- trafilatura or readability-lxml for readable text extraction
```

---

### 5.6 Organizer and Contact Extraction

The app should extract:

```text
conference name
date/month/year
field/topic
location
country
official website
organizing company/society
contact emails
committee names
program chair names
sponsorship contact
exhibitor contact
CFP contact
phone numbers
LinkedIn/company URLs where available
source URL
source text snippet
```

Use LLM extraction only on text that has already been collected from source pages.

The LLM must not invent contacts.

Every extracted contact must be traceable to a source URL and evidence snippet.

---

## 6. Data Sources

Possible discovery sources:

```text
- Search engines via API
- conference listing databases
- CFP databases
- industry association calendars
- university event calendars
- society websites
- Eventbrite
- Meetup where applicable
- OpenAlex / Wikidata for academic conference context
- official conference websites
```

Source quality hierarchy:

```text
1. Official conference website
2. Official society/university/organizer page
3. Official event platform page
4. CFP page from recognized source
5. Conference listing database
6. Generic aggregator
7. Inferred from previous year
```

---

## 7. Database Model

Use PostgreSQL for the main version.

For a fast local MVP, SQLite is acceptable, but design the models so migration to PostgreSQL is easy.

---

### 7.1 `conference`

```sql
CREATE TABLE conference (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    field TEXT,
    start_date DATE,
    end_date DATE,
    month_year TEXT,
    location TEXT,
    country TEXT,
    official_url TEXT,
    description TEXT,
    status TEXT DEFAULT 'discovered',
    confidence_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Suggested statuses:

```text
discovered
official_site_found
crawled
extracted
needs_review
verified
rejected
```

---

### 7.2 `organizer`

```sql
CREATE TABLE organizer (
    id SERIAL PRIMARY KEY,
    conference_id INTEGER REFERENCES conference(id) ON DELETE CASCADE,
    name TEXT,
    organization TEXT,
    role TEXT,
    email TEXT,
    phone TEXT,
    website TEXT,
    linkedin_url TEXT,
    contact_type TEXT,
    confidence_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Role examples:

```text
main organizer
program chair
general chair
sponsorship contact
exhibitor contact
CFP contact
media contact
event agency
scientific committee
local organizing committee
technical program committee
```

Contact type examples:

```text
generic
personal
sponsorship
CFP
exhibitor
registration
press
speaker
partnership
```

---

### 7.3 `source_evidence`

```sql
CREATE TABLE source_evidence (
    id SERIAL PRIMARY KEY,
    conference_id INTEGER REFERENCES conference(id) ON DELETE CASCADE,
    organizer_id INTEGER REFERENCES organizer(id) ON DELETE SET NULL,
    source_url TEXT NOT NULL,
    source_title TEXT,
    extracted_text_snippet TEXT,
    evidence_type TEXT,
    extraction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Evidence type examples:

```text
official_website
contact_page
committee_page
sponsorship_page
cfp_page
listing_page
inferred_from_previous_year
```

The `source_evidence` table is critical because every extracted record should be explainable.

---

### 7.4 `search_run`

```sql
CREATE TABLE search_run (
    id SERIAL PRIMARY KEY,
    field TEXT,
    region TEXT,
    start_month TEXT,
    end_month TEXT,
    contact_type TEXT,
    max_results INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP
);
```

Suggested statuses:

```text
pending
running
completed
failed
cancelled
```

---

### 7.5 `search_result`

```sql
CREATE TABLE search_result (
    id SERIAL PRIMARY KEY,
    search_run_id INTEGER REFERENCES search_run(id) ON DELETE CASCADE,
    title TEXT,
    url TEXT,
    snippet TEXT,
    source_query TEXT,
    rank INTEGER,
    is_selected BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### 7.6 Optional Future Tables

#### `crawled_page`

```sql
CREATE TABLE crawled_page (
    id SERIAL PRIMARY KEY,
    conference_id INTEGER REFERENCES conference(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    title TEXT,
    page_type TEXT,
    raw_html TEXT,
    extracted_text TEXT,
    crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `conference_series`

```sql
CREATE TABLE conference_series (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    acronym TEXT,
    field TEXT,
    website TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

This can later connect recurring conferences across years.

---

## 8. Backend API

Use FastAPI.

---

### 8.1 Search Runs

#### Create search run

```http
POST /api/search-runs
```

Request body:

```json
{
  "field": "AI in healthcare",
  "region": "Europe",
  "start_month": "2027-05",
  "end_month": "2027-09",
  "contact_type": "sponsorship",
  "max_results": 50
}
```

Response:

```json
{
  "id": 1,
  "status": "pending"
}
```

---

#### List search runs

```http
GET /api/search-runs
```

---

#### Get one search run

```http
GET /api/search-runs/{id}
```

Should return:

```text
- search run details
- status
- generated queries
- number of search results
- number of selected official websites
- number of conferences extracted
- number of organizers extracted
- errors if any
```

---

### 8.2 Conferences

#### List conferences

```http
GET /api/conferences
```

Query params:

```text
field
country
start_date
end_date
min_confidence
has_email
contact_type
```

---

#### Get conference detail

```http
GET /api/conferences/{id}
```

Should return:

```text
conference details
organizers
source evidence
confidence explanation
```

---

#### Update conference

```http
PATCH /api/conferences/{id}
```

Used for manual corrections.

---

### 8.3 Organizers

#### Update organizer

```http
PATCH /api/organizers/{id}
```

Used for manual corrections.

---

### 8.4 Export

```http
GET /api/export/conferences.csv
GET /api/export/conferences.xlsx
```

Export columns:

```text
conference_name
field
start_date
end_date
location
country
official_url
organizer_name
organization
role
email
phone
website
linkedin_url
contact_type
confidence_score
source_url
source_snippet
```

---

## 9. LLM Extraction

The app should use the LLM only to extract structured data from already-collected website text.

The LLM must:

```text
- return JSON only
- not invent names, dates, emails, organizations, or roles
- include evidence text for extracted data
- leave missing values as null
```

---

### 9.1 Extraction Prompt

Use this prompt in the backend:

```text
You are extracting structured conference information from official conference website text.

Rules:
- Only extract information that appears in the provided text.
- Do not invent names, dates, emails, organizations, or roles.
- If a value is not present, return null.
- Prefer official organizer, sponsorship, exhibitor, CFP, program chair, and committee contact information.
- For every extracted person or organization, include the text evidence.
- Return valid JSON only.

Input:
SOURCE_URL:
{source_url}

PAGE_TEXT:
{page_text}

Return JSON in this structure:

{
  "conference": {
    "name": null,
    "start_date": null,
    "end_date": null,
    "location": null,
    "country": null,
    "description": null
  },
  "organizers": [
    {
      "name": null,
      "organization": null,
      "role": null,
      "email": null,
      "phone": null,
      "website": null,
      "linkedin_url": null,
      "contact_type": null,
      "evidence_text": null
    }
  ]
}
```

---

### 9.2 Extraction Validation

After receiving LLM output, backend must validate:

```text
- JSON is valid
- extracted emails actually appear in the source text
- evidence_text appears in the source text or is close enough
- dates are parseable
- URLs are valid
- empty organizer objects are removed
- duplicate contacts are merged
```

Do not store contacts that have no evidence.

---

## 10. Confidence Scoring

Implement deterministic confidence scoring.

---

### 10.1 Conference Confidence

```text
+40 if official website found
+20 if conference name found on official page
+20 if date found
+10 if location found
+10 if field/topic clearly matches
```

Maximum: 100.

---

### 10.2 Organizer Confidence

```text
+40 if email appears on official website
+20 if role appears near email or name
+20 if organization appears on official website
+10 if source page is contact/sponsor/organizer/committee page
+10 if email domain matches official website or organizer domain
```

Maximum: 100.

---

### 10.3 Special Confidence Rules

```text
Generic email like info@ or contact@: okay, but label as generic.
Sponsorship email like sponsors@ or partnerships@: valuable for business outreach.
Personal email: store only if publicly listed on an official conference-related page.
Inferred organizer from previous year: max confidence 60.
Listing-site-only result: max confidence 50.
No evidence URL: confidence must be 0 and record should not be considered verified.
```

---

## 11. Frontend Pages

Use Next.js + Tailwind CSS.

---

### 11.1 `/`

Dashboard.

Show:

```text
New search button
Recent search runs
Total conferences found
Total verified organizers
Average confidence score
Export button
```

---

### 11.2 `/search/new`

Search form.

Fields:

```text
Field/topic
Region
Start month
End month
Contact type
Max results
Submit button
```

---

### 11.3 `/search-runs/[id]`

Search job progress page.

Show:

```text
status
queries generated
results found
official websites detected
pages crawled
conferences extracted
organizers extracted
errors
```

---

### 11.4 `/conferences`

Table view.

Columns:

```text
Conference
Date
Location
Field
Organizer count
Best contact
Confidence
Official URL
```

Filters:

```text
field
country
date range
contact type
minimum confidence
has email
```

---

### 11.5 `/conferences/[id]`

Detailed conference page.

Sections:

```text
Conference details
Official website
Dates/location
Organizers/contact people
Source evidence
Manual edit form
Confidence explanation
```

Organizer table columns:

```text
Name
Organization
Role
Email
Contact type
Confidence
Source
```

---

## 12. Suggested Folder Structure

---

### 12.1 Backend

```text
backend/
  app/
    main.py
    config.py
    database.py

    models/
      conference.py
      organizer.py
      source_evidence.py
      search_run.py
      search_result.py

    schemas/
      conference.py
      organizer.py
      search_run.py

    api/
      search_runs.py
      conferences.py
      organizers.py
      export.py

    services/
      query_builder.py
      search_provider.py
      crawler.py
      official_site_detector.py
      extractor.py
      confidence.py
      exporter.py

    jobs/
      run_search.py

  requirements.txt
  alembic/
  Dockerfile
```

---

### 12.2 Frontend

```text
frontend/
  app/
    page.tsx
    search/
      new/
        page.tsx
    search-runs/
      [id]/
        page.tsx
    conferences/
      page.tsx
      [id]/
        page.tsx

  components/
    SearchForm.tsx
    ConferenceTable.tsx
    OrganizerTable.tsx
    ConfidenceBadge.tsx
    SourceEvidenceCard.tsx

  lib/
    api.ts
    types.ts

  package.json
```

---

## 13. Backend Service Responsibilities

---

### 13.1 `query_builder.py`

Input:

```python
field
region
start_month
end_month
contact_type
```

Output:

```python
list[str]
```

Example output:

```text
AI in healthcare conference Europe 2027
AI in healthcare summit Europe May 2027 sponsorship contact
AI in healthcare conference program committee 2027
AI in healthcare call for papers 2027
AI in healthcare congress exhibitors 2027
```

---

### 13.2 `search_provider.py`

Responsible for web search.

Return normalized results:

```python
from dataclasses import dataclass

@dataclass
class SearchResultDTO:
    title: str
    url: str
    snippet: str
    source_query: str
    rank: int
```

---

### 13.3 `official_site_detector.py`

Given search results, rank likely official URLs.

Signals:

```text
URL contains conference acronym/name
URL has event year
URL is not obviously a listing site
Title contains conference name
Snippet mentions official conference
Domain is organization/society/university/event domain
```

Return selected URLs.

---

### 13.4 `crawler.py`

Given official URL, fetch relevant pages.

Rules:

```text
same domain only
max depth 2
max 15 pages
prefer contact/sponsor/committee/organizer/cfp pages
extract readable text
store URL + title + text
```

---

### 13.5 `extractor.py`

Given page text, call LLM extraction prompt.

Must validate:

```text
JSON is valid
emails extracted actually appear in source text
evidence_text appears in source text or is close enough
dates are parseable
URLs are valid
```

---

### 13.6 `confidence.py`

Calculate confidence scores for conference and organizer.

---

### 13.7 `exporter.py`

Generate CSV and XLSX.

---

## 14. Development Milestones

---

### Milestone 1: Manual Conference Entry

Build:

```text
Database
FastAPI CRUD
Frontend conference table
Conference detail page
Manual organizer entry
CSV export
```

No scraping yet.

This verifies the data model.

---

### Milestone 2: Search Runs Without Crawling

Build:

```text
Search form
Query generation
Search provider integration
Store search results
Display search results
Allow user to mark official website manually
```

---

### Milestone 3: Official Site Crawling

Build:

```text
Crawler
Relevant page detection
Store crawled source evidence
Show source evidence on conference detail page
```

---

### Milestone 4: LLM Extraction

Build:

```text
LLM JSON extraction
Conference extraction
Organizer extraction
Email validation
Confidence scoring
Manual correction UI
```

---

### Milestone 5: Full Automated Workflow

Build:

```text
Search run creates queries
Search provider finds candidates
Official website detector selects URLs
Crawler crawls selected URLs
LLM extracts data
Confidence scoring
Results appear in conference table
Export works
```

---

## 15. Example User Flow

```text
1. User opens app.
2. User clicks “New search”.
3. User enters:
   Field: AI in healthcare
   Region: Europe
   Months: May 2027 – September 2027
   Contact type: sponsorship
4. App generates search queries.
5. App searches the web.
6. App detects likely official conference websites.
7. App crawls official pages.
8. App extracts conference and organizer data.
9. App scores confidence.
10. User reviews results.
11. User corrects bad records.
12. User exports CSV/XLSX.
```

---

## 16. CSV Export Example

```csv
conference_name,field,start_date,end_date,location,country,official_url,organizer_name,organization,role,email,contact_type,confidence_score,source_url
"AI Health Summit 2027","AI in healthcare","2027-05-12","2027-05-14","Berlin","Germany","https://example.com","Jane Doe","Example Events","Sponsorship Manager","sponsors@example.com","sponsorship",95,"https://example.com/sponsors"
```

---

## 17. Legal and Compliance Notes

Be careful with scraping and personal contact data, especially in the EU.

Safer approach:

```text
Use official APIs where possible.
Respect robots.txt and website terms.
Store source URLs and extraction dates.
Prioritize generic business emails like sponsors@, info@, events@, partnerships@.
Avoid mass storing private personal emails unless clearly public and relevant.
Add opt-out/removal process.
Do not auto-email without proper legal basis and unsubscribe flow.
Do not scrape aggressively.
```

For B2B lead generation, the app can still be useful, but it should be GDPR-aware from the beginning.

---

## 18. Important Rules for the Coding AI

Tell the coding AI:

```text
Do not over-engineer the first version.
Do not build authentication yet.
Do not build email outreach yet.
Do not build a multi-tenant SaaS yet.
Do not scrape aggressively.
Do not invent contact data.
Always store source evidence.
Every extracted contact must be traceable to a source URL.
Prefer generic official business emails over personal emails.
Add manual correction tools because extracted data will never be perfect.
```

---

## 19. Best First Task for Local AI

Give your local AI this exact first task:

```text
Start by creating the backend and database for the Conference Organizer Contact Finder app.

Use FastAPI, SQLAlchemy, Alembic, and PostgreSQL.

Implement these models:
- Conference
- Organizer
- SourceEvidence
- SearchRun
- SearchResult

Implement CRUD endpoints for:
- conferences
- organizers
- search runs

Also implement CSV export for conferences with organizers.

Do not implement crawling or LLM extraction yet.
Create clean folder structure and include setup instructions.
```

---

## 20. Future Features After MVP

After the first version works, add:

```text
User accounts
Saved search templates
Scheduled monthly searches
Change detection for conference websites
CRM integrations
LinkedIn enrichment
Company enrichment
Speaker/CFP deadline tracking
Sponsorship package tracking
Duplicate detection across years
Recurring conference series tracking
Email outreach module
GDPR removal/opt-out workflow
Team accounts
Multi-tenant SaaS mode
```

---

## 21. Future SaaS / Multi-Organization Notes

If this becomes a SaaS app, add:

```text
users
organizations
organization_members
saved_searches
search_templates
workspace-level data separation
role-based access control
billing/subscriptions
```

For data separation, possible options:

```text
1. Row-level tenant_id in shared tables
2. Separate schemas per organization
3. Separate databases per organization
```

For MVP, use a single-user local app and avoid multi-tenancy.

---

## 22. Final Product Summary

This app should become a **conference organizer intelligence tool**.

It should not simply scrape a list of conferences.

It should help the user discover relevant conferences, identify who organizes them, find useful contact channels, verify those contacts with evidence, and export the results for business or research use.

The main principle:

```text
No contact without source evidence.
No invented data.
Confidence score everything.
Manual review is part of the product.
```
