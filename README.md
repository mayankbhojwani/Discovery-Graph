# 🌐 SynapseHorizon: Graph-Driven Research & Innovation Engine

**An executive-level B2B knowledge discovery platform that uncovers hidden connections and pathways between disparate domains of human knowledge using graph topology.**

SynapseHorizon crawls and indexes 2-Hop ego networks from Wikipedia's live API to construct structured graph databases, then analyzes structural bridge linkages to trace diverse research pathways.

---

## 🛠️ System Architecture & Workflow

1. **Graph Construction (`pipeline.py`)**
   - Harvests a paced 2-Hop ego network around any search seed topic (e.g. *Quantum Computing*).
   - Resolves all outbound intro links and page summaries in parallel using a `ThreadPoolExecutor`.
   - Cleans dead ends and reinforces graph walkability, saving structured sub-graphs into a local SQLite repository.
   
2. **Topological Discovery (`engine.py`)**
   - **Multi-Path Discovery**: Extracts up to 5 alternative discovery paths branching from the seed topic node.
   - **Path Diversity Filter**: Implements a greedy node penalization algorithm that penalizes node overlap, ensuring diverse branches.
   - **Topological Ranking Matrix**: Scores path viability by calculating the average node score using degree centrality penalties (surprise factor $\alpha$) and local clustering coefficients:
     $$NodeScore(v) = \frac{1}{(Degree(v) + 1.0)^\alpha \cdot (ClusteringCoeff(v) + 0.05)}$$
   - **Strategic Bottleneck Bridge Detection**: Calculates network-wide betweenness centrality to isolate the top 3 critical bottleneck nodes.

3. **Cognitive Translation Layer**
   - Enriches Wikipedia entries on the fly into multi-dimensional Research Profiles containing:
     - **Core Mechanism**: A clear technical summary.
     - **Cross-Over Application**: Deployments in unrelated industries.
     - **Open Innovation Question**: Bottlenecks limiting research/product scale.

---

## 💻 Research Workbench Workspace (`app.py`)

The user interface uses a high-density, three-column executive cockpit layout:

- **Left Column (Discovery Configurator)**:
  - Input fields to target Seed Topics.
  - Interactive slider for **'Innovation Horizon Width'** to specify track count.
  - Graph database selectors to swap between loaded networks.
- **Center Column (Discovery Tracks)**:
  - Displays the 4 best discovered paths as visual horizontal chains: `Node A ➔ Node B ➔ Node C`.
  - Prints a one-sentence text summary explaining the hidden common thread of each specific track.
  - Interactive selection button to focus the workspace brief on a specific track.
- **Right Column (Intelligence Workspace)**:
  - Renders the executive-level innovation brief.
  - Provides interactive tabs for each node in the path containing the structured B2B Research Profiles.

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

> No API keys needed — everything operates using public Wikipedia feeds.

---

## 📦 Project Structure

```
synapse-horizon/
├── app.py          # Streamlit UI — three-column executive workspace
├── engine.py       # CuriosityEngine — path scoring, diversity loops, centrality metrics
├── pipeline.py     # Harvester — 2-Hop parallel MediaWiki crawler
├── database.py     # Database interface — SQLite schema operations
├── requirements.txt# Python requirements
└── README.md       # Product Documentation
```

---

*Powered by NetworkX, Streamlit, and Wikipedia.*
