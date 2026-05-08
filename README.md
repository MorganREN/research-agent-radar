<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Kimi-K2.5-6C5CE7?logo=data:image/svg+xml;base64,&logoColor=white" />
  <img src="https://img.shields.io/badge/Qwen-Plus-FF6B35?logoColor=white" />
  <img src="https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?logo=streamlit&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-B8860B" />
</p>

# 📚 PaperFlow.AI — Research Agent Radar

> 🤖 An autonomous multi-agent system that discovers, filters, analyzes, and visualizes academic papers — so you can focus on *reading*, not *searching*.

PaperFlow.AI monitors arXiv and ScienceDirect around the clock, uses LLM agents (Kimi K2.5 + Qwen-Plus) to score relevance and generate structured analysis reports, and presents everything in an elegant academic-themed dashboard.

---

## ✨ Highlights

- 🔍 **Multi-source discovery** — Automatically fetches papers from **arXiv** and **ScienceDirect** (Elsevier)
- 🧠 **LLM-powered relevance scoring** — Qwen-Plus rates every paper 1–10 against your research interests
- 📝 **Deep analysis reports** — Kimi K2.5 (128K context) generates comprehensive structured reports; Map-Reduce fallback for extreme cases
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
                          │ (Qwen-Plus)       │
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
                          │  (Kimi K2.5)      │
                          │  128K context     │
                          │  + Map-Reduce     │
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
| **RelevanceFilter** | Qwen-Plus | Scores title + abstract against your research interests (1–10) |
| **DownloadManager** | — | Downloads PDFs via HTTP (arXiv) or browser automation (authenticated) |
| **PaperReviewer** | Kimi K2.5 | Generates structured deep-analysis reports; 128K context, Map-Reduce fallback |
| **PDFUploadParser** | Kimi K2.5 | Extracts metadata from user-uploaded PDFs (50K char context) |
| **PromptAgent** | Qwen-Plus | Auto-generates analysis prompt templates tailored to your domain |

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
# Required — powers analysis & PDF parsing (Kimi / Moonshot AI)
KIMI_API_KEY=your-kimi-api-key

# Required — powers relevance filtering & prompt generation (Qwen / Dashscope)
QWEN_API_KEY=your-qwen-api-key

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

## ♾️ Persistent Run (macOS)

For long-running usage (close terminal without stopping services), you can run three background processes:

1. **Streamlit dashboard** (persistent)
2. **ngrok tunnel** (expose Streamlit localhost to internet)
3. **Radar scheduler daemon** (persistent)

### 1) Start Streamlit persistently

```bash
cd /Users/renmohan/code/research-agent-radar
mkdir -p logs pids

nohup poetry run streamlit run src/dashboard/app.py --server.port 8501 --server.address 0.0.0.0 \
  >> logs/streamlit.log 2>&1 &
echo $! > pids/streamlit.pid
```

Check / stop:

```bash
ps -p "$(cat pids/streamlit.pid)" -o pid,etime,command
tail -f logs/streamlit.log
kill "$(cat pids/streamlit.pid)"
```

### 2) Expose Streamlit via ngrok

Install + auth (first time only):

```bash
brew install ngrok/ngrok/ngrok
ngrok config add-authtoken <YOUR_NGROK_AUTHTOKEN>
```

Run ngrok persistently (map local `8501`):

```bash
cd /Users/renmohan/code/research-agent-radar
nohup ngrok http 8501 >> logs/ngrok.log 2>&1 &
echo $! > pids/ngrok.pid
```

Get public URL:

```bash
curl -s http://127.0.0.1:4040/api/tunnels | python -c "import sys,json;d=json.load(sys.stdin);print(d['tunnels'][0]['public_url'] if d.get('tunnels') else 'No tunnel')"
```

Check / stop:

```bash
ps -p "$(cat pids/ngrok.pid)" -o pid,etime,command
tail -f logs/ngrok.log
kill "$(cat pids/ngrok.pid)"
```

### 3) Start scheduler daemon persistently

```bash
cd /Users/renmohan/code/research-agent-radar
nohup poetry run radar >> logs/radar.log 2>&1 &
echo $! > pids/radar.pid
```

Check / stop:

```bash
ps -p "$(cat pids/radar.pid)" -o pid,etime,command
tail -f logs/radar.log
kill "$(cat pids/radar.pid)"
```

### Optional: restart all three quickly

```bash
cd /Users/renmohan/code/research-agent-radar

# stop old processes if pid files exist
for svc in streamlit ngrok radar; do
  [ -f "pids/${svc}.pid" ] && kill "$(cat pids/${svc}.pid)" 2>/dev/null || true
done

# start services
nohup poetry run streamlit run src/dashboard/app.py --server.port 8501 --server.address 0.0.0.0 >> logs/streamlit.log 2>&1 & echo $! > pids/streamlit.pid
nohup ngrok http 8501 >> logs/ngrok.log 2>&1 & echo $! > pids/ngrok.pid
nohup poetry run radar >> logs/radar.log 2>&1 & echo $! > pids/radar.pid
```

> ⚠️ Keep your API keys in `.env` and do not expose secrets through Streamlit pages.

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
| `KIMI_API_KEY` | ✅ Yes | Moonshot AI API key for Kimi K2.5 (analysis & PDF parsing) |
| `QWEN_API_KEY` or `BOB_API_KEY` | ✅ Yes | Qwen-compatible API key for relevance filtering & prompt generation |
| `ELSEVIER_API_KEY` | ❌ Optional | Elsevier API key for ScienceDirect access |

---

## 🧰 Tech Stack

| Component | Technology |
|-----------|------------|
| 🐍 Language | Python 3.12+ |
| 🧠 LLM | Kimi K2.5 (Moonshot AI, 128K context), Qwen-Plus (Dashscope) |
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
| `poetry run doctor` | 🩺 Check dependencies, imports, config, and key environment variables |
| `poetry run streamlit run src/dashboard/app.py` | 🖥️ Launch the Streamlit dashboard |
| `python tools/check.py` | 🔎 Inspect all papers in the database |

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  Made with ❤️ for researchers who'd rather read papers than search for them.
</p>
