import streamlit as st
import time
import sqlite3
import os
from database import initialize_db
from engine import CuriosityEngine
from pipeline import ingest_codebase

# ─── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SynapseHorizon: Codebase Architecture Engine",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── Database Init ───────────────────────────────────────────────────────────────
initialize_db()

# ─── Helper Functions ────────────────────────────────────────────────────────────

def get_path_summary(path):
    """Returns a professional, one-sentence summary of the codebase pathway connection."""
    start = path[0].split(".")[-1]
    end = path[-1].split(".")[-1]
    return f"Traces how control flow or dependencies propagate from '{start}' through structural intermediate modules to reach '{end}'."

# ─── Global UI Styling CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Outfit:wght@400;500;600;700&display=swap');

/* ── Reset & Base Styles ── */
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
    background-color: #0b0f19 !important;
    color: #f1f5f9 !important;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stHeader"] { background-color: transparent !important; }
h1, h2, h3, h4, h5, h6 { font-family: 'Outfit', sans-serif !important; color: #ffffff; }

/* ── Title ── */
.main-title {
    font-family: 'Outfit', sans-serif;
    background: linear-gradient(135deg, #3b82f6 0%, #10b981 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.8rem;
    font-weight: 800;
    text-align: center;
    margin-bottom: 0.1rem;
    letter-spacing: -0.5px;
}
.subtitle {
    text-align: center;
    color: #64748b;
    font-size: 1rem;
    margin-bottom: 2rem;
    font-weight: 400;
}

/* ── Columns layout boxes ── */
.workspace-col {
    background: #0f172a !important;
    border: 1px solid #1e293b !important;
    border-radius: 12px !important;
    padding: 24px !important;
    height: 100% !important;
    min-height: 700px !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
}
.workspace-col-title {
    font-family: 'Outfit', sans-serif !important;
    font-size: 1.25rem !important;
    font-weight: 700 !important;
    color: #3b82f6 !important;
    margin-bottom: 1rem !important;
    border-bottom: 1px solid #1e293b !important;
    padding-bottom: 8px !important;
}

/* ── Discovery Horizon Row Styling ── */
.horizon-container {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 1rem;
    cursor: pointer;
    transition: all 0.2s ease;
}
.horizon-container:hover {
    border-color: #3b82f6;
    background: #1e294b;
}
.horizon-selected {
    border: 1px solid #10b981 !important;
    background: #0d2720 !important;
}
.horizon-chain-text {
    font-family: 'Outfit', sans-serif !important;
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    color: #ffffff !important;
    margin-bottom: 6px !important;
}
.horizon-summary-text {
    font-size: 0.82rem !important;
    color: #94a3b8 !important;
    line-height: 1.4 !important;
}

/* ── Intel Profile Workspace styling ── */
.profile-title {
    font-family: 'Outfit', sans-serif !important;
    font-size: 1.2rem !important;
    font-weight: 700 !important;
    color: #10b981 !important;
    margin-bottom: 12px !important;
}
.profile-section-title {
    font-size: 0.8rem !important;
    font-weight: 700 !important;
    color: #64748b !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
    margin-top: 12px !important;
    margin-bottom: 4px !important;
}
.profile-section-body {
    font-size: 0.9rem !important;
    color: #cbd5e1 !important;
    line-height: 1.5 !important;
    background: rgba(255, 255, 255, 0.02) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
    padding: 8px 12px !important;
    border-radius: 6px !important;
}

/* Custom styled buttons */
.b2b-btn button {
    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
    color: #ffffff !important;
    border: none !important;
    padding: 12px 20px !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
}
.b2b-btn button:hover {
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3) !important;
    transform: translateY(-1px) !important;
}

/* Tab styling overrides */
div[data-baseweb="tab-list"] {
    gap: 8px !important;
}
button[data-baseweb="tab"] {
    background-color: #1e293b !important;
    color: #94a3b8 !important;
    border-radius: 6px 6px 0 0 !important;
    padding: 8px 16px !important;
    border: 1px solid #334155 !important;
    border-bottom: none !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    background-color: #3b82f6 !important;
    color: white !important;
    border-color: #3b82f6 !important;
}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════════
# WELCOME / DATABASE SETUP SCREEN
# ════════════════════════════════════════════════════════════════════════════════
if "selected_realm" not in st.session_state:
    st.markdown('<div class="main-title">🌐 SynapseHorizon</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Graph-Based Codebase Architecture understanding Engine</div>', unsafe_allow_html=True)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.info("**1. Parse Source Code AST**\nExtract class/method definitions, inheritances, modules, and call graphs directly from directories.")
    with col_b:
        st.info("**2. Topological Subsystem Mapping**\nIdentify critical bridge modules and trace diverse control paths while filtering generic helper utilities.")
    with col_c:
        st.info("**3. Interactive Code Metrics**\nBenchmark architectural serendipity, bottleneck centralities, and review refactoring questions.")

    st.markdown("---")

    left, middle, right = st.columns([1, 2, 1])
    with middle:
        st.markdown("### 📥 Index Codebase Repository")
        st.markdown("<p style='color:#64748b; font-size:0.9rem; margin-bottom:8px;'>Enter a local Python directory path to parse AST nodes.</p>", unsafe_allow_html=True)
        
        default_dir = os.getcwd()
        custom_topic = st.text_input(
            "Repository Path",
            value=default_dir,
            key="custom_realm_input_welcome",
            label_visibility="collapsed"
        )
        if st.button("🔌 Construct Graph Database", key="btn_manifest_welcome", use_container_width=True):
            if custom_topic.strip() and os.path.exists(custom_topic.strip()):
                with st.spinner("Analyzing codebase directory & generating AST sub-graph..."):
                    count = ingest_codebase(custom_topic.strip(), db_path="curiosity.db")
                    if count > 0:
                        st.session_state.selected_realm = custom_topic.strip()
                        st.success(f"Codebase parsed successfully! Indexed {count} call graph edges. Loading workspace...")
                        time.sleep(0.8)
                        st.rerun()
                    else:
                        st.error("No Python source files found or no call edges extracted. Verify repository content.")
            else:
                st.error("Repository directory path does not exist. Please enter a valid directory.")

        # Saved realms
        try:
            conn = sqlite3.connect("curiosity.db")
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT realm FROM nodes")
            saved_realms = [row[0] for row in cursor.fetchall() if row[0]]
            conn.close()
        except Exception:
            saved_realms = []

        if saved_realms:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**📂 Previously Loaded Codebases**")
            for r in saved_realms:
                if st.button(f"🔎 Inspect: {r}", key=f"jump_{r}", use_container_width=True):
                    st.session_state.selected_realm = r
                    st.rerun()

    st.stop()


# ════════════════════════════════════════════════════════════════════════════════
# ACTIVE THREE-COLUMN PARADIGM
# ════════════════════════════════════════════════════════════════════════════════

engine = CuriosityEngine(realm=st.session_state.selected_realm)
all_nodes = sorted(list(engine.graph.nodes()))
default_seed = all_nodes[0] if all_nodes else ""

# State setup
if "selected_path" not in st.session_state:
    st.session_state.selected_path = None


# Render Layout Columns
c_left, c_center, c_right = st.columns([1, 2, 2])

# ─── LEFT COLUMN: Configurator ──────────────────────────────────────────────────
with c_left:
    st.markdown('<div class="workspace-col-title">⚙️ Discovery Control</div>', unsafe_allow_html=True)
    st.markdown(f"**Codebase Folder:** `{st.session_state.selected_realm}`")
    
    # Dependency Toggle Checkbox
    include_external = st.checkbox(
        "🔍 Include External / Built-in Calls",
        value=False,
        help="When disabled (default), only project-defined modules, classes, and methods are traversed. Enable this to inspect built-ins and third-party library linkages."
    )
    
    # Define active nodes based on toggle
    active_nodes = sorted(list(engine.core_graph.nodes())) if not include_external else sorted(list(engine.graph.nodes()))
    if not active_nodes:
        active_nodes = sorted(list(engine.graph.nodes()))
        
    # State setup for seed topic
    if "seed_topic" not in st.session_state or st.session_state.seed_topic not in active_nodes:
        st.session_state.seed_topic = active_nodes[0] if active_nodes else ""
        
    # Input for Seed Topic
    if active_nodes:
        seed_input = st.selectbox(
            "Core Seed Component",
            options=active_nodes,
            index=active_nodes.index(st.session_state.seed_topic) if st.session_state.seed_topic in active_nodes else 0,
            help="Select the starting module, class, or method to trace architectural paths from."
        )
    else:
        seed_input = st.text_input("Core Seed Component", value="")

    # Slider for Innovation Horizon Width (1 to 5 tracks)
    width_val = st.slider(
        "Discovery Path Tracks",
        min_value=1,
        max_value=5,
        value=4,
        help="The maximum number of distinct architectural paths to extract."
    )
    
    # Execute button
    st.markdown('<div class="b2b-btn">', unsafe_allow_html=True)
    if st.button("⚡ Discover Execution Paths", use_container_width=True):
        if seed_input in active_nodes:
            st.session_state.seed_topic = seed_input
            st.session_state.selected_path = None
            st.rerun()
        else:
            st.error("Selected seed component is invalid.")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Rescan codebase button
    st.markdown('<div class="b2b-btn" style="margin-top: 8px;">', unsafe_allow_html=True)
    if st.button("🔄 Rescan Repository Directory", use_container_width=True):
        with st.spinner("Re-parsing source files & rebuilding call graph..."):
            count = ingest_codebase(st.session_state.selected_realm, db_path="curiosity.db")
            if count > 0:
                st.toast(f"🚀 Rescan complete! Refreshed {count} relationships.")
                time.sleep(1.0)
                st.rerun()
            else:
                st.error("Rescan failed. Check folder files.")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Switch realm options
    st.markdown("**📂 Switch Codebase**")
    try:
        conn = sqlite3.connect("curiosity.db")
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT realm FROM nodes")
        saved_realms = [row[0] for row in cursor.fetchall() if row[0]]
        conn.close()
    except Exception:
        saved_realms = []
        
    for r in saved_realms:
        if r != st.session_state.selected_realm:
            if st.button(f"📁 {os.path.basename(r)}", key=f"switch_r_{r}", use_container_width=True, help=r):
                st.session_state.selected_realm = r
                st.session_state.pop("seed_topic", None)
                st.session_state.pop("selected_path", None)
                st.rerun()
                
    if st.button("➕ Parse New Codebase", use_container_width=True):
        st.session_state.pop("selected_realm", None)
        st.session_state.pop("seed_topic", None)
        st.session_state.pop("selected_path", None)
        st.rerun()


# ─── CENTER COLUMN: Discovery Tracks ────────────────────────────────────────────
with c_center:
    st.markdown('<div class="workspace-col-title">🛣️ Architectural Pathways</div>', unsafe_allow_html=True)
    st.markdown(f"Displaying tracks tracing out from **'{st.session_state.seed_topic}'**:")
    
    discovery_paths = engine.generate_discovery_horizons(
        seed_topic=st.session_state.seed_topic,
        max_depth=4,
        alpha=0.7,
        top_k=width_val,
        include_external=include_external
    )
    
    if not discovery_paths:
        st.warning("No architectural pathways found starting from this code component.")
        st.info("Check if this node is connected to other components in the parsed graph.")
    else:
        # Default selection
        if st.session_state.selected_path is None or st.session_state.selected_path not in discovery_paths:
            st.session_state.selected_path = discovery_paths[0]
            
        for idx, path in enumerate(discovery_paths):
            # Check if selected
            is_selected = (st.session_state.selected_path == path)
            sel_class = "horizon-selected" if is_selected else ""
            
            # Format text chains: A ➔ B ➔ C
            chain_str = " ➔ ".join([p.split(".")[-1] for p in path])
            summary_str = get_path_summary(path)
            
            # Styled container card
            st.markdown(f"""
            <div class="horizon-container {sel_class}">
                <div class="horizon-chain-text">🧬 Path Track {idx+1}: {chain_str}</div>
                <div class="horizon-summary-text">{summary_str}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Click action button
            btn_label = "📊 Selected Workspace" if is_selected else f"🔎 Select Track {idx+1}"
            if st.button(btn_label, key=f"sel_path_btn_{idx}", use_container_width=True, disabled=is_selected):
                st.session_state.selected_path = path
                st.rerun()


# ─── RIGHT COLUMN: Component Workspace ──────────────────────────────────────────
with c_right:
    st.markdown('<div class="workspace-col-title">📋 Architectural Workspace</div>', unsafe_allow_html=True)
    
    if st.session_state.selected_path:
        path = st.session_state.selected_path
        st.markdown(f"### 🧪 Execution Path Brief")
        
        # Display full path
        st.markdown(f"Active Track: **{' ➔ '.join([p.split('.')[-1] for p in path])}**")
        
        # Tabs for every node in the selected path
        node_tabs = st.tabs([node.split(".")[-1] for node in path])
        for idx, node in enumerate(path):
            with node_tabs[idx]:
                profile = engine.node_summaries.get(node, {})
                node_type = engine.node_types.get(node, "unknown")
                
                st.markdown(f'<div class="profile-title">🔍 {node} ({node_type})</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="profile-section-title">⚙️ Core Mechanism & Signature</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="profile-section-body">{profile.get("core_mechanism", "Details not loaded.")}</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="profile-section-title">🔀 Dependency Coupling Context</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="profile-section-body">{profile.get("cross_over_application", "Details not loaded.")}</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="profile-section-title">💡 Architectural / Refactoring Question</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="profile-section-body">{profile.get("open_innovation_question", "Details not loaded.")}</div>', unsafe_allow_html=True)
                
        # ─── Algorithmic Path Evaluation ───
        metrics = engine.evaluate_path_metrics(path)
        
        st.markdown("---")
        st.markdown("### 📊 Algorithmic Path Evaluation")
        
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric(
                label="Serendipity Index", 
                value=f"{metrics['serendipity']:.2f}",
                help="Measures average log-inverse degree. High values indicate discovery pathways that traverse specialized, low-degree leaf nodes (specific code logics) rather than generic hubs."
            )
        with col_m2:
            st.metric(
                label="Bridge Centrality", 
                value=f"{metrics['bridge_factor']:.4f}",
                help="Measures average betweenness centrality. High values indicate intermediate components that cross-link distinct architectural subsystems."
            )
        with col_m3:
            comp = metrics['composite_score']
            if comp >= 0.8:
                label = "OPTIMAL"
            elif comp >= 0.6:
                label = "EXCELLENT"
            elif comp >= 0.4:
                label = "STABLE"
            else:
                label = "STANDARD"
            st.metric(
                label="Composite Score", 
                value=f"{comp * 100:.1f}%",
                delta=label,
                help="Normalized architectural understanding index balancing serendipity and bottleneck centrality."
            )
            
        st.info(
            "💡 **Topological Benchmarking Insight:**\n\n"
            "The **Serendipity Index** calculates the inverse log-degree to verify if this pathway leverages specialized, low-degree leaf nodes to bypass standard helper/utility hubs. "
            "The **Bridge Centrality** tracks how successfully the path routes through high-betweenness bottleneck nodes that link separate software subsystems. "
            "A higher **Composite Score** indicates a pathway that highlights clean structural code relationships while crossing architectural boundaries."
        )
    else:
        st.info("Select an architectural path from the center column to compile a deep-dive structure brief.")
