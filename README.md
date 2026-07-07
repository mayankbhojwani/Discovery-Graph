# 🌐 SynapseHorizon: Graph-Driven Research & Innovation Engine

**An executive-level B2B knowledge discovery platform that uncovers hidden connections and pathways between disparate domains of human knowledge using graph topology.**

SynapseHorizon queries, crawls, and indexes 2-Hop semantic relationships from Wikidata's SPARQL endpoint to construct structured graph databases, then analyzes structural bridge linkages to trace diverse research pathways.

---

## 🛠️ System Architecture & Workflow

1. **Semantic Ingestion Engine (`pipeline.py`)**
   - Resolves search keywords to normalized Wikidata entities using the Wikidata API.
   - Executes SPARQL queries against `https://query.wikidata.org/sparql` using a specific User-Agent to extract direct connections (Hop 1) and batch-queries the top 12 targets for Hop 2 connections.
   - Crawls entity descriptions directly to build structured B2B Research Profiles, saving them with transactional `INSERT OR IGNORE` queries into a local SQLite repository.
   
2. **Topological Discovery (`engine.py`)**
   - **Multi-Path Discovery**: Extracts up to 5 alternative discovery paths branching from the seed topic node.
   - **Path Diversity Filter**: Implements a greedy node-penalization algorithm that penalizes node overlap, ensuring diverse branches.
   - **Topological Ranking Matrix**: Scores path viability by calculating the average node score using degree centrality penalties (surprise factor $\alpha$) and local clustering coefficients:
     $$NodeScore(v) = \frac{1}{(Degree(v) + 1.0)^\alpha \cdot (ClusteringCoeff(v) + 0.05)}$$
   - **Strategic Bottleneck Bridge Detection**: Calculates network-wide betweenness centrality to isolate the top 3 critical bottleneck nodes.

3. **Data Science Telemetry & Path Evaluation (`engine.py`)**
   - **Metrics Calculator (`evaluate_path_metrics`)**: Evaluates the intermediate nodes of any pathway to compute:
     - *Serendipity Index*: Average log-inverse degree ($1/\log(Degree(v) + 2.0)$) to measure how effectively the path leverages obscure, niche nodes.
     - *Bridge Centrality*: Average betweenness centrality to measure how successfully it routes through structural bottleneck nodes.
     - *Composite Score*: A combined, normalized index in `[0, 1]` indicating the path's overall structural discovery quality.
   - **Automated Session Telemetry (`log_session_telemetry`)**: Automatically records every discovery run's timestamp, seed topic, active database, path tracks, and calculated metrics to a local `telemetry_logs.json` file.

4. **Cognitive Translation Layer**
   - Enriches Wikidata entries on the fly into multi-dimensional Research Profiles containing:
     - **Core Mechanism**: A clear technical explanation.
     - **Cross-Over Application**: Deployments in unrelated domains.
     - **Open Innovation Question**: Current research bottlenecks limiting scale.

---

## 💻 Research Workbench Workspace (`app.py`)

The user interface uses a high-density, three-column executive cockpit layout:

- **Left Column (Discovery Configurator)**:
  - Input fields to target Seed Topics.
  - Interactive slider for **'Innovation Horizon Width'** to specify track count.
  - Graph database selectors to swap between loaded networks.
  - A **"🌐 Sync with Wikidata Core"** action button to refresh the active workspace with live Wikidata semantic paths.
- **Center Column (Discovery Tracks)**:
  - Displays the discovered paths as visual horizontal chains: `Node A ➔ Node B ➔ Node C`.
  - Prints a one-sentence text summary explaining the hidden common thread of each specific track.
  - Interactive selection button to focus the workspace brief on a specific track.
- **Right Column (Intelligence Workspace)**:
  - Renders the executive-level innovation brief.
  - Provides interactive tabs for each node in the path containing the structured B2B Research Profiles.
  - **Algorithmic Path Evaluation Panel**: Displays metrics boxes for Serendipity Index, Bridge Centrality, and Composite Score alongside benchmarking insights.

---

## 🚀 Running Locally

**Requirements:** Python 3.9+

```bash
# 1. Clone the repository
git clone https://github.com/your-username/synapse-horizon.git
cd synapse-horizon

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run Streamlit Server
streamlit run app.py
```

Then open **http://localhost:8501** in your browser.

> No API keys needed — everything operates using public Wikidata SPARQL feeds.

---

## 📦 Project Structure

```
synapse-horizon/
├── app.py           # Streamlit UI — three-column workspace, metrics dashboard
├── engine.py        # CuriosityEngine — path evaluation, diversity loops, telemetry
├── pipeline.py      # Wikidata Ingestor — SPARQL 2-Hop crawler & SQLite loader
├── database.py      # Database interface — SQLite schema operations
├── requirements.txt # Python requirements
└── README.md        # Product Documentation
```

---

*Powered by NetworkX, Streamlit, and Wikidata.*
