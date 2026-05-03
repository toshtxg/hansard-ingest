# Singapore Hansard Dashboard — Product Requirements Document

**Project:** hansard-dashboard  
**Author:** Tosh Goh  
**Date:** March 2026  
**Status:** Spec for Claude Code implementation  
**Repo:** github.com/toshtxg/sg-hansard  
**Live:** toshtxg.github.io/sg-hansard  

---

## 1. Overview

### 1.1 What This Is

A public-facing data exploration dashboard for Singapore Parliamentary Hansard records. The site presents factual, publicly-sourced Hansard data in an accessible and visually polished format. The data covers Parliaments 12–15 (Sept 2012 to present), with 92,000+ speech records across 412 sittings and 238 unique speakers.

### 1.2 Goals

- Transform a basic chart-only dashboard into a proper multi-view exploration tool
- Enable researchers, journalists, and citizens to discover patterns in parliamentary activity
- Present data objectively and factually — this is a public-record transparency tool, not an editorial or scorecard
- Make the codebase easy to maintain and iterate on with Claude Code

### 1.3 Non-Goals

- NOT a real-time system — data is batch-ingested via a separate Python pipeline
- NOT an editorial platform — no opinion, scoring, or ranking of MP "performance"
- NOT a full-text reading tool — link out to official Hansard for full speeches
- NOT a mobile-first app (desktop-first, responsive is fine)

### 1.4 Editorial / Sensitivity Guidelines

This dashboard presents **Singapore government parliamentary data**. Follow these rules strictly:

- Use neutral, factual language throughout (e.g., "speaking activity" not "effort level")
- Never frame any visualization as a "scorecard", "ranking", or "performance review"
- Always attribute data to the official Hansard source (link to sprs.parl.gov.sg)
- Include an "About" page explaining data source, methodology, and limitations
- AI-generated summaries must be clearly labelled as AI-generated
- When displaying individual MP data, present it as factual record, not judgment

---

## 2. Tech Stack

### 2.1 Frontend

| Layer | Choice | Reason |
|-------|--------|--------|
| Build tool | **Vite** | Fast dev server, simple config, great with Claude Code |
| Framework | **React 18+ with TypeScript** | Claude Code's strongest stack; type safety for complex data |
| Styling | **Tailwind CSS** | Utility-first, no separate CSS files to manage |
| Components | **shadcn/ui** | Copy-paste components, not a dependency — easy to customize |
| Charts | **Recharts** | React-native charting, great for bar/line/area charts |
| Routing | **React Router v6** (hash-based) | Enables deep-linking (`/#/mp/K-Shanmugam`) without server config |
| Data fetching | **@supabase/supabase-js** | Official client, direct browser-to-Supabase RPC calls |
| State | **React hooks + URL params** | Keep it simple — no Redux/Zustand needed |

### 2.2 Backend / Data

| Layer | Choice | Reason |
|-------|--------|--------|
| Database | **Supabase (Postgres)** | Already in use; all data lives here |
| API layer | **Supabase RPC functions** | Postgres functions called from the browser via supabase-js |
| Auth | **None** | Public read-only dashboard; RLS policies allow anonymous reads |
| Hosting | **GitHub Pages** or **Vercel** (free tier) | Vercel preferred for cleaner SPA routing; GitHub Pages works with hash routing |

### 2.3 Ingestion Pipeline (No Changes)

The existing Python ingestion pipeline (`ingest.py` + `hansard_ingest/` package) is out of scope. It continues to populate Supabase tables independently.

### 2.4 Project Structure

```
hansard-dashboard/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── package.json
├── .env                          # VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY
├── src/
│   ├── main.tsx                  # Entry point
│   ├── App.tsx                   # Router + layout shell
│   ├── lib/
│   │   ├── supabase.ts           # Supabase client init
│   │   ├── types.ts              # TypeScript interfaces for all data shapes
│   │   └── utils.ts              # Formatting helpers (dates, numbers, etc.)
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Header.tsx        # Site header + nav
│   │   │   ├── Footer.tsx        # Attribution + links
│   │   │   └── Shell.tsx         # Main layout wrapper
│   │   ├── ui/                   # shadcn/ui components (Button, Card, Select, etc.)
│   │   └── charts/               # Reusable chart wrappers
│   │       ├── BarChart.tsx
│   │       ├── LineChart.tsx
│   │       └── HeatMap.tsx
│   ├── pages/
│   │   ├── Overview.tsx          # Landing / home page
│   │   ├── MPProfile.tsx         # Individual MP deep-dive
│   │   ├── TopicExplorer.tsx     # Search + browse topics
│   │   ├── Trends.tsx            # Parliament-over-time analysis
│   │   └── About.tsx             # Methodology + attribution
│   └── hooks/
│       ├── useSupabaseRpc.ts     # Generic RPC caller with loading/error states
│       └── useSittings.ts        # Shared sitting date list
└── public/
    └── favicon.ico
```

---

## 3. Data Model Reference

### 3.1 Existing Tables

**hansard_sittings** (412 rows)  
Primary key: `sitting_date`  
Fields: `sitting_date`, `source_url`, `fetched_at`

**hansard_speeches** (92,165 rows)  
Primary key: `(sitting_date, row_num)`  
Key fields:
- `parliament_no` (int) — Parliament number (12, 13, 14, 15)
- `mp_name_fuzzy_matched` (text) — Cleaned speaker name
- `discussion_title` (text) — Topic/motion title
- `section_type` (text) — One of: `OS` (Oral Speech), `OA` (Oral Answer), `WA` (Written Answer), `WANA` (Written Answer Not Answered), `BP` (Bill Proceedings), `BI` (Bill Introduction), `WS` (Written Statement)
- `word_count` (int)
- `speech_details` (text) — Full speech text
- `one_liner` (text) — AI-generated one-line summary (~5,500 populated)
- `themes` (jsonb) — AI-extracted theme tags (~5,500 populated)
- `key_claims` (jsonb) — AI-extracted key claims (~5,500 populated)
- `dim_is_question_for_oral_answer` (smallint) — 1 if this is a question
- `dim_is_oral_speech` (smallint) — 1 if oral speech
- `dim_is_written_answer_not_answered` (smallint)
- `dim_is_written_answer_to_questions` (smallint)

**hansard_attendance** (1,296 rows)  
Primary key: `(sitting_date, mp_name_raw)`  
Fields: `parliament_no`, `mp_name_cleaned`, `dim_is_speaker`, `dim_is_deputy_speaker`, `dim_is_present`

**hansard_ptba** (51 rows)  
Primary key: `(sitting_date, mp_name_raw, ptba_from, ptba_to)`

**hansard_ai_summaries** (12 rows)  
Primary key: `sitting_date`  
Fields: `provider`, `model`, `summary_3_sentences`

### 3.2 Section Type Reference

| Code | Meaning | Count | Total Words |
|------|---------|-------|-------------|
| OS | Oral Speeches | 27,435 | 13.1M |
| OA | Oral Answers | 23,583 | 3.7M |
| WA | Written Answers | 16,820 | 1.9M |
| WANA | Written Answers (Not Answered) | 15,437 | 2.2M |
| BP | Bill Proceedings | 8,446 | 6.2M |
| BI | Bill Introduction | 227 | 9.4K |
| WS | Written Statements | 217 | 23K |

---

## 4. Pages & Features

### 4.1 Overview / Home Page

**Route:** `/#/`

The landing page should immediately communicate what this site is and give a high-level snapshot of the dataset.

**Components:**
- **Hero section**: Site title ("Singapore Hansard Explorer"), one-line description, dataset stats (e.g., "92,000+ speeches · 412 sittings · 2012–2026")
- **Quick stats cards**: Total sittings, total unique speakers, most recent sitting date, total words spoken in Parliament
- **Recent sittings list**: Last 10 sittings with date, number of speeches, and link to the sitting's detail or AI summary
- **Navigation cards**: Visual entry points to the three main sections (MP Profiles, Topic Explorer, Trends)

**Supabase RPCs needed:**
- `overview_stats()` — returns total speeches, sittings, speakers, words, latest sitting date
- `recent_sittings(limit)` — returns last N sittings with speech count

### 4.2 MP Profile / Deep-Dive

**Route:** `/#/mp` (list view) and `/#/mp/:name` (detail view)

#### 4.2.1 MP List View (`/#/mp`)

- Searchable/filterable list of all 238 MPs
- Each row shows: name, total word count, total speeches, number of sittings active, primary section type
- Sortable by any column
- Click any MP to go to their profile

**Supabase RPC:**
- `mp_list()` — returns all MPs with aggregate stats

#### 4.2.2 MP Detail View (`/#/mp/:name`)

This is the flagship page. Show everything we know about one MP.

**Section A: Header & Summary**
- MP name, total words, total speeches, sittings active, parliament(s) served
- "Active from [first sitting] to [last sitting]"

**Section B: Speaking Activity Over Time** (Line Chart)
- X-axis: time (by quarter or year)
- Y-axis: total words spoken
- Option to toggle between word count and speech count
- This shows how active an MP has been over their career

**Section C: Topic Breakdown** (Horizontal Bar Chart)
- Top 20 discussion titles by word count for this MP
- Gives a snapshot of what this MP focuses on
- Filter option by section_type (oral questions vs. speeches vs. bill debates)

**Section D: Section Type Distribution** (Donut/Pie Chart)
- Breakdown of this MP's speeches by section type (OS, OA, WA, BP, etc.)
- Shows whether they primarily ask questions, give speeches, or participate in bill debates

**Section E: Recent Speeches** (Table)
- Last 20 speeches by this MP
- Columns: Date, Discussion Title, Section Type, Word Count, One-liner (if available)
- Each row links to the official Hansard source URL
- Paginated or "load more"

**Supabase RPCs:**
- `mp_summary(mp_name)` — returns aggregate stats for one MP
- `mp_activity_over_time(mp_name, granularity)` — returns time-series data (quarterly or yearly)
- `mp_top_topics(mp_name, limit, section_type_filter)` — returns top discussion titles by word count
- `mp_section_breakdown(mp_name)` — returns count/words by section_type
- `mp_recent_speeches(mp_name, limit, offset)` — returns paginated speech list

### 4.3 Topic Explorer

**Route:** `/#/topics`

A searchable, filterable view across all parliamentary discussions.

**Section A: Search Bar**
- Full-text search on `discussion_title`
- Results appear as a filterable table below
- Debounced search (300ms)

**Section B: Filters** (sidebar or top bar)
- Date range picker (from/to)
- Section type multi-select (OS, OA, WA, BP, etc.)
- Parliament number selector (12, 13, 14, 15)

**Section C: Results Table**
- Columns: Discussion Title, Sitting Date, Section Type, # Speakers, Total Words, Parliament
- Sortable by any column
- Click a row to expand and show:
  - List of speakers who participated (with word count per speaker)
  - AI one-liner summary (if available)
  - Themes (if available)
  - Link to official Hansard

**Section D: Topic Trends** (Optional — P1)
- If a search term is entered, show a small line chart of how often that term appears over time
- X-axis: time (quarterly)
- Y-axis: number of discussions mentioning the search term

**Supabase RPCs:**
- `search_topics(query, date_from, date_to, section_types, parliament_no, limit, offset)` — full-text search with filters, returns discussion titles with aggregates
- `topic_detail(discussion_title, sitting_date)` — returns all speakers + speech metadata for one discussion on one date
- `topic_trend(query, granularity)` — (P1) returns time-series count of matching discussions

### 4.4 Parliament Trends

**Route:** `/#/trends`

Structural analysis of how Parliament's activity has changed over time. This is the "big picture" view.

**Section A: Volume Over Time** (Multi-line or Stacked Area Chart)
- X-axis: time (by year or quarter)
- Y-axis: total speeches (or words)
- Lines/areas broken down by section_type
- Shows the structural shift — e.g., growth in written answers vs. oral questions

**Section B: Parliament Comparison Cards**
- Side-by-side cards for Parliament 12, 13, 14, 15
- Each card shows: date range, total sittings, total speeches, total unique speakers, avg speeches per sitting
- Visual comparison of key metrics

**Section C: Sitting Intensity** (Bar chart or heatmap)
- Number of sitting days per year
- Average word count per sitting over time
- Shows whether sessions are getting longer/shorter/more frequent

**Section D: Speaker Diversity** (Line chart)
- Number of unique speakers per year
- Average words per speaker per year
- Shows whether a wider or narrower set of MPs is participating

**Supabase RPCs:**
- `trends_volume_over_time(granularity, section_type_filter)` — time-series of speech/word counts by section type
- `trends_parliament_summary()` — returns aggregate stats per parliament_no
- `trends_sitting_intensity(granularity)` — sittings per period, avg words per sitting
- `trends_speaker_diversity(granularity)` — unique speakers per period, avg words per speaker

### 4.5 About Page

**Route:** `/#/about`

Static content page. No RPCs needed.

**Content:**
- **Data Source**: All data is from the official Singapore Parliament Hansard, publicly available at sprs.parl.gov.sg
- **Methodology**: Brief explanation of the ingestion pipeline — data is scraped from the Parliament API, parsed, cleaned, and stored in a database. Names are fuzzy-matched for consistency.
- **AI Summaries**: Where AI-generated content appears (one-liners, themes, key claims, sitting summaries), it is clearly labelled. AI summaries are generated using [model name] and may contain inaccuracies.
- **Limitations**: Data may have parsing errors. Name matching is approximate. Not all sittings may be ingested. This is an independent project, not affiliated with the Singapore Government.
- **Author**: Created by Tosh Goh. Link to GitHub repo.
- **Contact**: GitHub issues link for feedback

---

## 5. Supabase RPC Specifications

All RPCs should be created as Postgres functions accessible via `supabase.rpc('function_name', { params })` from the browser. All functions should be `SECURITY DEFINER` with appropriate row-level security.

### 5.1 Overview RPCs

```sql
-- overview_stats()
-- Returns: { total_speeches, total_sittings, total_speakers, total_words, latest_sitting }
CREATE OR REPLACE FUNCTION overview_stats()
RETURNS json AS $$
  SELECT json_build_object(
    'total_speeches', (SELECT COUNT(*) FROM hansard_speeches),
    'total_sittings', (SELECT COUNT(*) FROM hansard_sittings),
    'total_speakers', (SELECT COUNT(DISTINCT mp_name_fuzzy_matched) FROM hansard_speeches WHERE mp_name_fuzzy_matched IS NOT NULL),
    'total_words', (SELECT SUM(word_count) FROM hansard_speeches),
    'latest_sitting', (SELECT MAX(sitting_date) FROM hansard_sittings)
  );
$$ LANGUAGE sql STABLE;

-- recent_sittings(p_limit int)
-- Returns: array of { sitting_date, source_url, speech_count, word_count }
CREATE OR REPLACE FUNCTION recent_sittings(p_limit int DEFAULT 10)
RETURNS json AS $$
  SELECT json_agg(r) FROM (
    SELECT s.sitting_date, s.source_url,
      COUNT(sp.row_num) as speech_count,
      SUM(sp.word_count) as word_count
    FROM hansard_sittings s
    LEFT JOIN hansard_speeches sp ON s.sitting_date = sp.sitting_date
    GROUP BY s.sitting_date, s.source_url
    ORDER BY s.sitting_date DESC
    LIMIT p_limit
  ) r;
$$ LANGUAGE sql STABLE;
```

### 5.2 MP Profile RPCs

```sql
-- mp_list()
-- Returns array of { mp_name, total_words, total_speeches, sittings_active, primary_section_type }
CREATE OR REPLACE FUNCTION mp_list()
RETURNS json AS $$
  SELECT json_agg(r ORDER BY total_words DESC) FROM (
    SELECT 
      mp_name_fuzzy_matched as mp_name,
      SUM(word_count) as total_words,
      COUNT(*) as total_speeches,
      COUNT(DISTINCT sitting_date) as sittings_active,
      MODE() WITHIN GROUP (ORDER BY section_type) as primary_section_type
    FROM hansard_speeches
    WHERE mp_name_fuzzy_matched IS NOT NULL
    GROUP BY mp_name_fuzzy_matched
  ) r;
$$ LANGUAGE sql STABLE;

-- mp_summary(p_mp_name text)
-- Returns: { mp_name, total_words, total_speeches, sittings_active, first_sitting, last_sitting, parliaments }
CREATE OR REPLACE FUNCTION mp_summary(p_mp_name text)
RETURNS json AS $$
  SELECT json_build_object(
    'mp_name', p_mp_name,
    'total_words', SUM(word_count),
    'total_speeches', COUNT(*),
    'sittings_active', COUNT(DISTINCT sitting_date),
    'first_sitting', MIN(sitting_date),
    'last_sitting', MAX(sitting_date),
    'parliaments', array_agg(DISTINCT parliament_no ORDER BY parliament_no)
  )
  FROM hansard_speeches
  WHERE mp_name_fuzzy_matched = p_mp_name;
$$ LANGUAGE sql STABLE;

-- mp_activity_over_time(p_mp_name text, p_granularity text DEFAULT 'quarter')
-- p_granularity: 'quarter' or 'year'
-- Returns array of { period, word_count, speech_count }
CREATE OR REPLACE FUNCTION mp_activity_over_time(p_mp_name text, p_granularity text DEFAULT 'quarter')
RETURNS json AS $$
  SELECT json_agg(r ORDER BY period) FROM (
    SELECT 
      CASE WHEN p_granularity = 'year' 
        THEN date_trunc('year', sitting_date)::date::text
        ELSE date_trunc('quarter', sitting_date)::date::text
      END as period,
      SUM(word_count) as word_count,
      COUNT(*) as speech_count
    FROM hansard_speeches
    WHERE mp_name_fuzzy_matched = p_mp_name
    GROUP BY period
  ) r;
$$ LANGUAGE sql STABLE;

-- mp_top_topics(p_mp_name text, p_limit int DEFAULT 20, p_section_type text DEFAULT NULL)
-- Returns array of { discussion_title, word_count, speech_count, section_type }
CREATE OR REPLACE FUNCTION mp_top_topics(p_mp_name text, p_limit int DEFAULT 20, p_section_type text DEFAULT NULL)
RETURNS json AS $$
  SELECT json_agg(r) FROM (
    SELECT 
      discussion_title,
      SUM(word_count) as word_count,
      COUNT(*) as speech_count,
      MODE() WITHIN GROUP (ORDER BY section_type) as section_type
    FROM hansard_speeches
    WHERE mp_name_fuzzy_matched = p_mp_name
      AND discussion_title IS NOT NULL
      AND (p_section_type IS NULL OR section_type = p_section_type)
    GROUP BY discussion_title
    ORDER BY word_count DESC
    LIMIT p_limit
  ) r;
$$ LANGUAGE sql STABLE;

-- mp_section_breakdown(p_mp_name text)
-- Returns array of { section_type, speech_count, word_count }
CREATE OR REPLACE FUNCTION mp_section_breakdown(p_mp_name text)
RETURNS json AS $$
  SELECT json_agg(r ORDER BY word_count DESC) FROM (
    SELECT section_type, COUNT(*) as speech_count, SUM(word_count) as word_count
    FROM hansard_speeches
    WHERE mp_name_fuzzy_matched = p_mp_name
    GROUP BY section_type
  ) r;
$$ LANGUAGE sql STABLE;

-- mp_recent_speeches(p_mp_name text, p_limit int DEFAULT 20, p_offset int DEFAULT 0)
-- Returns array of { sitting_date, discussion_title, section_type, word_count, one_liner, source_url }
CREATE OR REPLACE FUNCTION mp_recent_speeches(p_mp_name text, p_limit int DEFAULT 20, p_offset int DEFAULT 0)
RETURNS json AS $$
  SELECT json_agg(r) FROM (
    SELECT 
      sp.sitting_date, sp.discussion_title, sp.section_type, 
      sp.word_count, sp.one_liner,
      s.source_url
    FROM hansard_speeches sp
    JOIN hansard_sittings s ON sp.sitting_date = s.sitting_date
    WHERE sp.mp_name_fuzzy_matched = p_mp_name
    ORDER BY sp.sitting_date DESC, sp.row_num
    LIMIT p_limit OFFSET p_offset
  ) r;
$$ LANGUAGE sql STABLE;
```

### 5.3 Topic Explorer RPCs

```sql
-- search_topics(p_query text, p_date_from date, p_date_to date, p_section_types text[], p_parliament_no int, p_limit int, p_offset int)
-- Returns array of { discussion_title, sitting_date, section_type, speaker_count, total_words, parliament_no }
CREATE OR REPLACE FUNCTION search_topics(
  p_query text DEFAULT NULL,
  p_date_from date DEFAULT NULL,
  p_date_to date DEFAULT NULL,
  p_section_types text[] DEFAULT NULL,
  p_parliament_no int DEFAULT NULL,
  p_limit int DEFAULT 50,
  p_offset int DEFAULT 0
)
RETURNS json AS $$
  SELECT json_agg(r) FROM (
    SELECT 
      discussion_title,
      sitting_date,
      MODE() WITHIN GROUP (ORDER BY section_type) as section_type,
      COUNT(DISTINCT mp_name_fuzzy_matched) as speaker_count,
      SUM(word_count) as total_words,
      MAX(parliament_no) as parliament_no
    FROM hansard_speeches
    WHERE discussion_title IS NOT NULL
      AND (p_query IS NULL OR discussion_title ILIKE '%' || p_query || '%')
      AND (p_date_from IS NULL OR sitting_date >= p_date_from)
      AND (p_date_to IS NULL OR sitting_date <= p_date_to)
      AND (p_section_types IS NULL OR section_type = ANY(p_section_types))
      AND (p_parliament_no IS NULL OR parliament_no = p_parliament_no)
    GROUP BY discussion_title, sitting_date
    ORDER BY sitting_date DESC
    LIMIT p_limit OFFSET p_offset
  ) r;
$$ LANGUAGE sql STABLE;

-- topic_detail(p_discussion_title text, p_sitting_date date)
-- Returns: { discussion_title, sitting_date, speakers: [{ mp_name, word_count, one_liner, themes }], source_url }
CREATE OR REPLACE FUNCTION topic_detail(p_discussion_title text, p_sitting_date date)
RETURNS json AS $$
  SELECT json_build_object(
    'discussion_title', p_discussion_title,
    'sitting_date', p_sitting_date,
    'source_url', (SELECT source_url FROM hansard_sittings WHERE sitting_date = p_sitting_date),
    'speakers', (
      SELECT json_agg(json_build_object(
        'mp_name', mp_name_fuzzy_matched,
        'word_count', word_count,
        'one_liner', one_liner,
        'themes', themes,
        'section_type', section_type
      ) ORDER BY row_num)
      FROM hansard_speeches
      WHERE discussion_title = p_discussion_title AND sitting_date = p_sitting_date
    )
  );
$$ LANGUAGE sql STABLE;
```

### 5.4 Trends RPCs

```sql
-- trends_volume_over_time(p_granularity text DEFAULT 'quarter', p_section_type text DEFAULT NULL)
-- Returns array of { period, section_type, speech_count, word_count }
CREATE OR REPLACE FUNCTION trends_volume_over_time(p_granularity text DEFAULT 'quarter', p_section_type text DEFAULT NULL)
RETURNS json AS $$
  SELECT json_agg(r ORDER BY period, section_type) FROM (
    SELECT 
      CASE WHEN p_granularity = 'year' 
        THEN date_trunc('year', sitting_date)::date::text
        ELSE date_trunc('quarter', sitting_date)::date::text
      END as period,
      section_type,
      COUNT(*) as speech_count,
      SUM(word_count) as word_count
    FROM hansard_speeches
    WHERE (p_section_type IS NULL OR section_type = p_section_type)
    GROUP BY period, section_type
  ) r;
$$ LANGUAGE sql STABLE;

-- trends_parliament_summary()
-- Returns array of { parliament_no, date_range, total_sittings, total_speeches, total_speakers, avg_speeches_per_sitting }
CREATE OR REPLACE FUNCTION trends_parliament_summary()
RETURNS json AS $$
  SELECT json_agg(r ORDER BY parliament_no) FROM (
    SELECT 
      parliament_no,
      MIN(sitting_date)::text || ' to ' || MAX(sitting_date)::text as date_range,
      COUNT(DISTINCT sitting_date) as total_sittings,
      COUNT(*) as total_speeches,
      COUNT(DISTINCT mp_name_fuzzy_matched) as total_speakers,
      ROUND(COUNT(*)::numeric / NULLIF(COUNT(DISTINCT sitting_date), 0), 1) as avg_speeches_per_sitting
    FROM hansard_speeches
    WHERE parliament_no IS NOT NULL
    GROUP BY parliament_no
  ) r;
$$ LANGUAGE sql STABLE;

-- trends_sitting_intensity(p_granularity text DEFAULT 'year')
-- Returns array of { period, sitting_count, avg_words_per_sitting }
CREATE OR REPLACE FUNCTION trends_sitting_intensity(p_granularity text DEFAULT 'year')
RETURNS json AS $$
  SELECT json_agg(r ORDER BY period) FROM (
    SELECT 
      CASE WHEN p_granularity = 'year' 
        THEN date_trunc('year', s.sitting_date)::date::text
        ELSE date_trunc('quarter', s.sitting_date)::date::text
      END as period,
      COUNT(DISTINCT s.sitting_date) as sitting_count,
      ROUND(SUM(sp.word_count)::numeric / NULLIF(COUNT(DISTINCT s.sitting_date), 0), 0) as avg_words_per_sitting
    FROM hansard_sittings s
    LEFT JOIN hansard_speeches sp ON s.sitting_date = sp.sitting_date
    GROUP BY period
  ) r;
$$ LANGUAGE sql STABLE;

-- trends_speaker_diversity(p_granularity text DEFAULT 'year')
-- Returns array of { period, unique_speakers, avg_words_per_speaker }
CREATE OR REPLACE FUNCTION trends_speaker_diversity(p_granularity text DEFAULT 'year')
RETURNS json AS $$
  SELECT json_agg(r ORDER BY period) FROM (
    SELECT 
      CASE WHEN p_granularity = 'year' 
        THEN date_trunc('year', sitting_date)::date::text
        ELSE date_trunc('quarter', sitting_date)::date::text
      END as period,
      COUNT(DISTINCT mp_name_fuzzy_matched) as unique_speakers,
      ROUND(SUM(word_count)::numeric / NULLIF(COUNT(DISTINCT mp_name_fuzzy_matched), 0), 0) as avg_words_per_speaker
    FROM hansard_speeches
    WHERE mp_name_fuzzy_matched IS NOT NULL
    GROUP BY period
  ) r;
$$ LANGUAGE sql STABLE;
```

---

## 6. Design Direction

### 6.1 Visual Style

- **Clean, data-forward, institutional** — think The Pudding or Our World in Data, not a corporate SaaS dashboard
- **Color palette**: Use a restrained, professional palette. Primary: deep navy/slate. Accent: a warm teal or blue-green. Charts: a diverging palette that works in grayscale too.
- **Typography**: Inter or system fonts. Large, readable headings. Don't go below 14px for body text.
- **Whitespace**: Generous. Let the data breathe.
- **Dark mode**: Nice to have, not P0. If implemented, use Tailwind's dark mode classes.

### 6.2 Layout Principles

- Full-width layout with a max-width container (~1280px)
- Persistent top navigation bar with site title + page links
- No sidebar navigation — use tab-style nav within pages where needed
- Cards for grouping related content
- Charts should be large and readable, not crammed into small cards

### 6.3 Responsive Behavior

- Desktop-first design
- On mobile: stack columns, hide less-important chart dimensions, simplify tables
- Navigation collapses to a hamburger menu on mobile

---

## 7. Implementation Plan

### Phase 1: Foundation + Overview (Week 1)

1. Initialize Vite + React + TypeScript + Tailwind + shadcn/ui project
2. Set up Supabase client and `.env` configuration
3. Create layout shell (Header, Footer, Shell) with React Router
4. Build the Overview/Home page with stats cards and recent sittings
5. Create the About page (static content)
6. Deploy to GitHub Pages or Vercel
7. Create `overview_stats()` and `recent_sittings()` RPCs

### Phase 2: MP Profiles (Week 2)

1. Create all MP-related Supabase RPCs
2. Build MP list page with search + sorting
3. Build MP detail page with all 5 sections (header, activity chart, topics, section breakdown, recent speeches)
4. Add deep-linking via URL params

### Phase 3: Topic Explorer (Week 3)

1. Create topic-related Supabase RPCs
2. Build search interface with filters
3. Build results table with expandable row detail
4. Test with various search terms

### Phase 4: Parliament Trends (Week 4)

1. Create trends-related Supabase RPCs
2. Build volume-over-time stacked area chart
3. Build parliament comparison cards
4. Build sitting intensity and speaker diversity charts

### Phase 5: Polish + Ship (Week 5)

1. Cross-browser testing
2. Performance optimization (add Supabase indexes if needed)
3. Open Graph / social sharing metadata
4. Final deploy + update GitHub repo README

---

## 8. Supabase Indexes to Consider

These may be needed for performance as the dataset grows:

```sql
-- For MP queries
CREATE INDEX IF NOT EXISTS idx_speeches_mp_name ON hansard_speeches (mp_name_fuzzy_matched);

-- For topic search
CREATE INDEX IF NOT EXISTS idx_speeches_discussion_title ON hansard_speeches USING gin (discussion_title gin_trgm_ops);

-- For date range queries
CREATE INDEX IF NOT EXISTS idx_speeches_sitting_date ON hansard_speeches (sitting_date);

-- For section type filtering
CREATE INDEX IF NOT EXISTS idx_speeches_section_type ON hansard_speeches (section_type);

-- Composite for common query patterns
CREATE INDEX IF NOT EXISTS idx_speeches_mp_date ON hansard_speeches (mp_name_fuzzy_matched, sitting_date);
```

Note: The trigram index requires `CREATE EXTENSION IF NOT EXISTS pg_trgm;`

---

## 9. Future Considerations (Post-MVP)

These are explicitly out of scope for initial build but worth noting for future iterations:

- **Question Flow Analysis**: Who asks → which ministry answers. Interesting but needs cleaner ministry mapping.
- **AI Theme Explorer**: Once more speeches have themes populated, build a tag cloud or theme-based browsing experience.
- **Sitting Detail Page**: A per-sitting view showing the full agenda, all speakers, timeline of the day.
- **Export / API**: Let researchers download filtered datasets as CSV.
- **Comparison Mode**: Side-by-side comparison of two MPs or two time periods.

---

## 10. Claude Code Usage Notes

When working with Claude Code on this project:

- **Start each session** by reading this PRD and the current codebase state
- **One page at a time** — implement and test each page before moving to the next
- **RPC-first**: Create and test the Supabase RPC before building the frontend component that consumes it
- **Use shadcn/ui CLI** to add components: `npx shadcn-ui@latest add button card table select input`
- **Environment variables**: Store Supabase URL and anon key in `.env` as `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`
- **Test with real data**: Always test RPCs against the production Supabase instance (read-only access via anon key is safe)
- **Commit frequently**: One commit per feature/page, clear commit messages

---

*End of PRD*
