<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenAI-GPT--5.1-412991?logo=openai&logoColor=white" />
  <img src="https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?logo=streamlit&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-B8860B" />
</p>

# 📚 PaperFlow.AI — Research Agent Radar

> 🤖 An autonomous multi-agent system that discovers, filters, analyzes, and visualizes academic papers — so you can focus on *reading*, not *searching*.

PaperFlow.AI monitors arXiv and ScienceDirect around the clock, uses GPT models to score relevance and generate structured analysis reports, and presents everything in an elegant academic-themed dashboard.

---

## ✨ Highlights

- 🔍 **Multi-source discovery** — Automatically fetches papers from **arXiv** and **ScienceDirect** (Elsevier)
- 🧠 **LLM-powered relevance scoring** — GPT-4o-mini rates every paper 1–10 against your research interests
- 📝 **Deep analysis reports** — GPT-5.1 generates comprehensive structured reports with Map-Reduce for long papers
- ⏰ **Scheduled automation** — Daemon process runs the full pipeline every 6h / 12h / 24h / weekly
- 📊 **Interactive dashboard** — Plotly charts, daily feed, source distribution, trend lines — all in real-time
- 📤 **PDF upload & analysis** — Drag-and-drop your own PDFs for instant metadata extraction and deep analysis
- ⭐ **Bookmark system** — Star papers, filter by bookmarks, never lose an important find
- 🎨 **Academic aesthetic** — Playfair Display serif headings, warm ivory palette, gold accents

---

## 🏗️ Architecture

```
                          ┌──────────────────┐
                          │   📋 User Config  │
                          │ (fields/journals) │
                          └────────┬─────────┘
                                   │
              ┌────────────────────▼────────────────────┐
              │             🔍 Scout Phase               │
              │   ArxivScout          ElsevierScout      │
              │   (arXiv API)      (ScienceDirect API)   │
              └────────────────────┬────────────────────┘
                                   │
                          ┌────────▼─────────┐
                          │  🧠 Filter Phase  │
                          │ RelevanceFilter   │
                          │ (GPT-4o-mini)     │
                          │ Score: 1-10       │
                          └────────┬─────────┘
                                   │
                          ┌────────▼─────────┐
                          │ 📥 Acquisition    │
                          │ DownloadManager   │
                          │ (HTTP / Browser)  │
                          └────────┬─────────┘
                                   │
                          ┌────────▼─────────┐
                          │  📝 Analysis      │
                          │  PaperReviewer    │
                          │  (GPT-5.1)        │
                          │  Map-Reduce for   │
                          │  long papers      │
                          └────────┬─────────┘
                                   │
              ┌────────────────────▼────────────────────┐
              │            🖥️ Presentation               │
              │  Dashboard (Streamlit)   Daily Feed      │
              │  Papers / Analysis       Scheduler Page  │
              └───────────────────┬─────────────────────┘
                                  ▲
                          ┌───────┴────────┐
                          │  ⏰ Scheduler   │
                          │  (src/run.py)   │
                          │  Daemon loop    │
                          └────────────────┘
```

### 🤖 Agents

| Agent | Model | Role |
|-------|-------|------|
| **ArxivScout** | — | Fetches latest papers from arXiv by category & date range |
| **ElsevierScout** | — | Searches ScienceDirect journals, parses XML full text to Markdown |
| **RelevanceFilter** | GPT-4o-mini | Scores title + abstract against your research interests (1–10) |
| **DownloadManager** | — | Downloads PDFs via HTTP (arXiv) or browser automation (authenticated) |
| **PaperReviewer** | GPT-5.1 | Generates structured deep-analysis reports; Map-Reduce for long papers |
| **PDFUploadParser** | GPT-5.1 | Extracts metadata from user-uploaded PDFs |
| **PromptAgent** | GPT-5-mini | Auto-generates analysis prompt templates tailored to your domain |

---

## 🖥️ Dashboard Preview

The dashboard consists of three pages:

### 📖 Papers (Main Page)
- **Left panel** — Paper card list with source badges, relevance scores, bookmark stars
- **Right panel** — Full detail view with Analysis Report and Abstract tabs
- **Sidebar** — Search, source filter, relevance filter, sort options, PDF upload

### ⏰ Scheduler
- Live status display (running / stopped / crashed)
- "Run Pipeline Now" manual trigger button
- Execution history with paper counts and duration

### 📰 Daily Feed
- Papers grouped by fetch date with day headers
- Interactive Plotly charts:
  - 📊 Stacked bar chart + trend line for daily paper intake
  - 🥧 Source distribution donut (all-time + today)
- Feed-style cards with metadata and optional abstracts

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/your-username/research-agent-radar.git
cd research-agent-radar

# Install Poetry if needed
pip install poetry

# Install all dependencies
poetry install
```

### 2. Configure API Keys

Create a `.env` file in the project root:

```bash
# Required — powers all LLM agents
OPENAI_API_KEY=sk-your-openai-api-key

# Optional — only needed for ScienceDirect source
ELSEVIER_API_KEY=your-elsevier-api-key
```

### 3. Launch the Dashboard

```bash
poetry run streamlit run src/dashboard/app.py
```

On first launch, a **guided setup form** will appear where you configure:

| Setting | Example |
|---------|---------|
| 🔬 Research fields | "Digital Twin", "Large Language Models", "Computer Vision" |
| 📰 Journals | "Automation in Construction", "Nature Machine Intelligence" |
| 🌐 Data sources | arXiv, ScienceDirect |
| ⏰ Update frequency | Every 24 hours |

### 4. Start the Scheduler

```bash
# 🔄 Start daemon (runs continuously at your configured frequency)
poetry run radar

# ▶️ Or run the pipeline just once and exit
poetry run radar --once
```

> 💡 **Tip:** Run the dashboard and scheduler in separate terminals. Both share the same SQLite database.

---

## 📂 Project Structure

```
research-agent-radar/
├── src/
│   ├── run.py                          # 🚀 CLI entry point (scheduler daemon)
│   ├── main_demo.py                    # 🧪 Standalone demo pipeline
│   ├── dashboard/
│   │   ├── app.py                      # 🖥️ Main Streamlit dashboard
│   │   ├── config.py                   # ⚙️ First-run config form
│   │   ├── database.py                 # 💾 DB operations & background tasks
│   │   ├── components.py              # 🎨 Reusable UI components (HTML)
│   │   ├── styles.py                  # 🎨 CSS injection
│   │   ├── theme.py                   # 🎨 Color palette & constants
│   │   └── pages/
│   │       ├── 1_Scheduler.py         # ⏰ Scheduler status & history
│   │       └── 2_Daily_Feed.py        # 📰 Daily paper feed + charts
│   └── research_agent/
│       ├── agents/
│       │   ├── scout/                 # 🔍 Paper discovery agents
│       │   ├── filter/                # 🧠 Relevance filtering
│       │   ├── analysis/              # 📝 Deep analysis & PDF parsing
│       │   └── prompt/                # 💬 Auto prompt generation
│       ├── acquisition/               # 📥 PDF downloading
│       ├── config/                    # ⚙️ YAML configuration files
│       ├── scheduler/                 # ⏰ Pipeline runner & status tracking
│       └── storage/                   # 💾 SQLModel schemas & engine
├── tools/
│   ├── check.py                       # 🔎 Database inspection script
│   └── migrate_fetched_date.py        # 🔧 Migration utility
├── pyproject.toml                     # 📦 Dependencies (Poetry)
└── LICENSE                            # MIT
```

---

## ⚙️ Configuration Reference

### `user_config.yaml`

```yaml
fields:
  - Artificial Intelligence
  - Digital Twin
  - Large Language Models
  - Computer Vision
journals:
  - Automation in Construction
  - Tunnelling and Underground Space Technology
sources:
  - arxiv
  - sciencedirect
update_frequency: Every 24 hours
```

### ⏰ Update Frequency Options

| Setting | Interval |
|---------|----------|
| `Every 6 hours` | 6h |
| `Every 12 hours` | 12h |
| `Every 24 hours` | 24h |
| `Weekly` | 7 days |

### 🔑 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | ✅ Yes | OpenAI API key for GPT-5.1 / GPT-4o-mini |
| `ELSEVIER_API_KEY` | ❌ Optional | Elsevier API key for ScienceDirect access |

---

## 🧰 Tech Stack

| Component | Technology |
|-----------|------------|
| 🐍 Language | Python 3.12+ |
| 🧠 LLM | OpenAI GPT-5.1, GPT-5-mini, GPT-4o-mini |
| 💾 ORM | SQLModel + SQLAlchemy |
| 🗄️ Database | SQLite (zero-config) |
| 🖥️ Dashboard | Streamlit |
| 📊 Charts | Plotly (interactive) |
| 📄 PDF Parsing | pymupdf4llm |
| 🌐 Web Scraping | Playwright + BeautifulSoup4 |
| 📦 Package Manager | Poetry |

---

## 📋 CLI Reference

| Command | Description |
|---------|-------------|
| `poetry run radar` | 🔄 Start the scheduler daemon (recurring pipeline runs) |
| `poetry run radar --once` | ▶️ Run the pipeline once and exit |
| `poetry run streamlit run src/dashboard/app.py` | 🖥️ Launch the Streamlit dashboard |
| `python tools/check.py` | 🔎 Inspect all papers in the database |

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  Made with ❤️ for researchers who'd rather read papers than search for them.
</p>
