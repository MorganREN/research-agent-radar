# Research Agent Radar

An autonomous multi-agent system for continuous academic paper discovery, relevance filtering, deep analysis, and interactive visualization. Built with Python, OpenAI GPT models, and Streamlit.

## Architecture

```
                          +------------------+
                          |   User Config    |
                          | (fields/journals)|
                          +--------+---------+
                                   |
              +--------------------v--------------------+
              |            Scout Phase                   |
              |  ArxivScout        ElsevierScout         |
              |  (arXiv API)    (ScienceDirect API)      |
              +--------------------+--------------------+
                                   |
                          +--------v---------+
                          |   Filter Phase   |
                          | RelevanceFilter  |
                          | (GPT-4o-mini)    |
                          | Score: 1-10      |
                          +--------+---------+
                                   |
                          +--------v---------+
                          | Acquisition Phase|
                          | DownloadManager  |
                          | (HTTP / Browser) |
                          +--------+---------+
                                   |
                          +--------v---------+
                          |  Analysis Phase  |
                          |  PaperReviewer   |
                          |  (GPT-4o)        |
                          |  Map-Reduce for  |
                          |  long papers     |
                          +--------+---------+
                                   |
              +--------------------v--------------------+
              |              Presentation                |
              |  Dashboard (Streamlit)   Scheduler Page  |
              |  Papers / Analysis       Status / History|
              +-------------------+---------------------+
                                  ^
                                  |
                          +-------+--------+
                          |   Scheduler    |
                          |   (src/run.py) |
                          |   Daemon loop  |
                          +----------------+
```

### Agents

| Agent | Model | Role |
|---|---|---|
| **ArxivScout** | - | Fetches latest papers from arXiv by category (e.g. `cs.AI`, `cs.CE`) |
| **ElsevierScout** | - | Searches ScienceDirect journals via Elsevier API, parses XML full text |
| **RelevanceFilter** | GPT-4o-mini | Evaluates title + abstract against user research interests, returns relevance boolean + 1-10 score |
| **DownloadManager** | - | Downloads PDFs via direct HTTP (arXiv) or browser automation (authenticated sources) |
| **PaperReviewer** | GPT-4o | Generates structured analysis reports; uses Map-Reduce chunking for papers exceeding context limits |
| **PDFUploadParser** | GPT-4o | Extracts metadata (title, abstract, authors) from user-uploaded PDFs |
| **PromptAgent** | GPT-5-mini | Auto-generates a professional analysis prompt template based on user research fields |

### Data Flow

1. **Scout** agents discover papers from arXiv and ScienceDirect
2. **RelevanceFilter** scores each paper (1-10) against user-defined research interests
3. **DownloadManager** fetches PDFs for relevant papers
4. **PaperReviewer** produces a structured deep-analysis report per paper
5. **Dashboard** displays everything with filtering, sorting, and bookmarking
6. **Scheduler** automates the pipeline at the configured frequency

## Features

- **Multi-source discovery** -- arXiv and ScienceDirect (Elsevier), extensible to more
- **LLM-powered relevance scoring** -- 1-10 scale with color-coded badges
- **Deep paper analysis** -- structured reports via GPT-4o with Map-Reduce for long documents
- **Scheduled automation** -- daemon process runs the full pipeline at a configurable frequency (6h / 12h / 24h / weekly)
- **Scheduler dashboard** -- dedicated page showing scheduler status, next run time, and execution history
- **PDF upload** -- drag-and-drop PDFs into the dashboard for immediate analysis
- **Background analysis** -- PDF analysis runs in background threads, UI stays responsive
- **Bookmark system** -- star/unstar papers, filter by bookmarks
- **Interactive dashboard** -- card-based paper list, detail panel, sort by date or score
- **First-run configuration** -- guided setup form for research fields, journals, and sources
- **Auto-generated prompts** -- analysis prompt templates tailored to your research domain
- **SQLite storage** -- lightweight, zero-config database

## Project Structure

```
research-agent-radar/
├── src/
│   ├── run.py                               # Production entry point (scheduler daemon)
│   ├── main_demo.py                         # Legacy pipeline entry point
│   ├── dashboard/
│   │   ├── app.py                           # Streamlit dashboard UI (main page)
│   │   ├── config.py                        # First-run config form & YAML persistence
│   │   ├── database.py                      # DB operations, background analysis, bookmarks
│   │   └── pages/
│   │       └── 1_Scheduler.py               # Scheduler status & history page
│   └── research_agent/
│       ├── acquisition/
│       │   └── downloader.py                # PDF download (HTTP direct / browser)
│       ├── agents/
│       │   ├── scout/
│       │   │   ├── arxiv_scout.py           # arXiv paper discovery
│       │   │   └── elsevier_scout.py        # ScienceDirect paper discovery
│       │   ├── filter/
│       │   │   └── triage_agent.py          # LLM relevance filter + scoring
│       │   ├── analysis/
│       │   │   ├── parser.py                # PDF -> Markdown (pymupdf4llm)
│       │   │   ├── reviewer.py              # Deep analysis with Map-Reduce
│       │   │   └── extracter.py             # Metadata extraction for uploaded PDFs
│       │   └── prompt/
│       │       └── prompt_agent.py          # Auto-generate analysis prompt templates
│       ├── config/
│       │   ├── user_config.yaml             # User preferences (git-ignored)
│       │   └── analysis_prompt.yaml         # Generated prompt template (git-ignored)
│       ├── scheduler/
│       │   ├── __init__.py
│       │   ├── runner.py                    # Config-driven pipeline logic
│       │   └── status.py                    # Scheduler state & run history DB ops
│       └── storage/
│           └── models.py                    # SQLModel schemas + SQLite engine
├── pyproject.toml                           # Dependencies (Poetry)
├── poetry.lock
├── LICENSE                                  # MIT
└── README.md
```

## Prerequisites

- **Python 3.12+**
- **Poetry** (dependency manager)
- **OpenAI API Key** -- required for all LLM agents
- **Elsevier API Key** -- required only if using ScienceDirect source

## Deployment

### 1. Clone the repository

```bash
git clone https://github.com/your-username/research-agent-radar.git
cd research-agent-radar
```

### 2. Install dependencies

```bash
# Install Poetry if not already installed
pip install poetry

# Install project dependencies
poetry install
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```bash
# Required
OPENAI_API_KEY=sk-your-openai-api-key

# Optional (only needed for ScienceDirect source)
ELSEVIER_API_KEY=your-elsevier-api-key
```

### 4. First-run configuration (via Dashboard)

Launch the dashboard first. On the initial run, a configuration form will appear where you can set:

- **Research fields** -- your areas of interest (e.g. "Digital Twin", "Large Language Models")
- **Journals** -- target ScienceDirect journals (e.g. "Automation in Construction")
- **Data sources** -- which platforms to monitor (arXiv, ScienceDirect, ASCE)
- **Update frequency** -- how often to refresh (Every 6 hours / 12 hours / 24 hours / Weekly)

```bash
poetry run streamlit run src/dashboard/app.py
```

The configuration is saved to `src/research_agent/config/user_config.yaml` and an analysis prompt template is auto-generated to `src/research_agent/config/analysis_prompt.yaml`.

### 5. Start the scheduler

The scheduler daemon reads your configuration and automatically runs the full pipeline (scout, filter, download, analyze) at the frequency you chose during setup.

```bash
# Start the scheduler daemon (runs continuously)
poetry run radar

# Or run the pipeline just once and exit
poetry run radar --once
```

The scheduler:
- Runs the first pipeline cycle immediately on start
- Waits for the configured interval, then runs again
- Logs all execution results to the database
- Handles Ctrl+C gracefully (cleans up scheduler state)

### 6. View results in the dashboard

```bash
poetry run streamlit run src/dashboard/app.py
```

The dashboard has two pages (accessible via sidebar navigation):

**Papers page** (main):
- **Left panel** -- paper list with source badges, relevance scores, and status indicators
- **Right panel** -- full detail view with analysis report and abstract tabs
- **Sidebar** -- source filter, relevance filter, sort by date/score, bookmark filter, PDF upload

**Scheduler page**:
- **Status panel** -- shows if the scheduler daemon is running, the PID, frequency, and next run time
- **Manual trigger** -- "Run Pipeline Now" button for on-demand execution
- **Execution history** -- table of all past runs with paper counts and duration

### Running in production

Run the dashboard and scheduler in separate terminals (or as background services):

```bash
# Terminal 1: Dashboard
poetry run streamlit run src/dashboard/app.py

# Terminal 2: Scheduler daemon
poetry run radar
```

Both processes share the same SQLite database. The scheduler writes paper data and execution history; the dashboard reads and displays them.

### Uploading PDFs manually

You can also upload individual PDF papers directly through the dashboard sidebar. The system will:
1. Extract metadata (title, abstract, authors) using GPT-4o
2. Store the paper in the database with full relevance score
3. Run deep analysis in the background
4. Display the report once complete

## Configuration Reference

### `user_config.yaml`

```yaml
fields:
  - Artificial Intelligence
  - Digital Twin
  - Large Language Models
journals:
  - Automation in Construction
  - Tunnelling and Underground Space Technology
sources:
  - arxiv
  - sciencedirect
update_frequency: Every 24 hours
```

### Update Frequency Options

| Setting | Interval |
|---|---|
| `Every 6 hours` | 6 hours |
| `Every 12 hours` | 12 hours |
| `Every 24 hours` | 24 hours |
| `Weekly` | 7 days |

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | OpenAI API key for GPT-4o / GPT-4o-mini |
| `ELSEVIER_API_KEY` | No | Elsevier API key for ScienceDirect access |

## CLI Reference

| Command | Description |
|---|---|
| `poetry run radar` | Start the scheduler daemon (recurring pipeline runs) |
| `poetry run radar --once` | Run the pipeline once and exit |
| `poetry run streamlit run src/dashboard/app.py` | Launch the Streamlit dashboard |

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| LLM | OpenAI GPT-4o, GPT-4o-mini |
| ORM | SQLModel + SQLAlchemy |
| Database | SQLite |
| Dashboard | Streamlit |
| PDF parsing | pymupdf4llm |
| XML parsing | BeautifulSoup4 |
| Dependency mgmt | Poetry |

## License

MIT License. See [LICENSE](LICENSE) for details.
