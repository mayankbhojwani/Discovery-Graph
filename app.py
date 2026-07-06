import streamlit as st
import time
import sqlite3
from database import initialize_db, seed_mock_data
from engine import CuriosityEngine
from pipeline import harvest_ego_network, save_realm_to_db

# ─── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SynapseHorizon: Research & Innovation Engine",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── Database Init ───────────────────────────────────────────────────────────────
initialize_db()
try:
    conn = sqlite3.connect("curiosity.db")
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(nodes)")
    columns = [col[1] for col in cursor.fetchall()]
    has_realm_col = "realm" in columns
    if has_realm_col:
        cursor.execute("SELECT COUNT(*) FROM nodes WHERE title = 'Atari'")
        has_multi_realm = cursor.fetchone()[0] > 0
    else:
        has_multi_realm = False
    conn.close()
except Exception:
    has_multi_realm = False

if not has_multi_realm:
    seed_mock_data(force=True)
else:
    seed_mock_data()

# ─── Helper Functions ────────────────────────────────────────────────────────────

def get_path_summary(path):
    """Returns a professional, one-sentence B2B summary of the path's common thread."""
    start = path[0]
    end = path[-1]
    return f"This horizon traces how the foundational mechanisms of '{start}' propagate through structural linkages to enable the application vector of '{end}'."

def make_progress_callback(progress_bar, status_text):
    def callback(percent, msg):
        progress_bar.progress(percent)
        stage_num = 1 if percent < 33 else (2 if percent < 66 else 3)
        status_text.markdown(f"**Stage {stage_num}/3:** {msg}")
    return callback

# ─── Global B2B UI Styling CSS ──────────────────────────────────────────────────
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
    st.markdown('<div class="subtitle">B2B Graph-Driven Research & Innovation Engine</div>', unsafe_allow_html=True)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.info("**1. Harvest Knowledge Nodes**\nConstruct a comprehensive local research graph using high-speed Wikipedia scraping.")
    with col_b:
        st.info("**2. Topological Horizon Mapping**\nMap multi-hop conceptual chains using inverse connectivity penalties.")
    with col_c:
        st.info("**3. Deep-Dive Innovation Briefs**\nInspect core mechanisms, cross-over applications, and innovation questions.")

    st.markdown("---")

    left, middle, right = st.columns([1, 2, 1])
    with middle:
        st.markdown("### 📥 Build Research Sub-Graph")
        st.markdown("<p style='color:#64748b; font-size:0.9rem; margin-bottom:8px;'>Enter a topic seed to crawl and index a new sub-graph database.</p>", unsafe_allow_html=True)
        custom_topic = st.text_input(
            "Topic Core",
            key="custom_realm_input_welcome",
            placeholder="e.g. Artificial Intelligence, Cryptography, Blockchain, Astrophysics...",
            label_visibility="collapsed"
        )
        if st.button("🔌 Construct Graph Database", key="btn_manifest_welcome", use_container_width=True):
            if custom_topic.strip():
                progress_bar = st.progress(0)
                status_text = st.empty()
                cb = make_progress_callback(progress_bar, status_text)
                nodes, edges = harvest_ego_network(custom_topic, limit_hop1=15, progress_callback=cb)
                if nodes:
                    save_realm_to_db(custom_topic, nodes, edges)
                    st.session_state.selected_realm = custom_topic
                    st.success(f"Graph constructed successfully for '{custom_topic}'. Loading workspace...")
                    time.sleep(0.8)
                    st.rerun()
                else:
                    st.error("No pages found for the seed topic. Try another search term.")
            else:
                st.warning("Please type a topic core.")

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
            st.markdown("**📂 Existing Graph Databases**")
            for r in saved_realms:
                if st.button(f"🔎 Inspect Database: {r}", key=f"jump_{r}", use_container_width=True):
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
if "seed_topic" not in st.session_state or st.session_state.seed_topic not in engine.graph:
    st.session_state.seed_topic = default_seed

if "selected_path" not in st.session_state:
    st.session_state.selected_path = None


# Render Layout Columns
c_left, c_center, c_right = st.columns([1, 2, 2])

# ─── LEFT COLUMN: Configurator ──────────────────────────────────────────────────
with c_left:
    st.markdown('<div class="workspace-col-title">⚙️ Discovery Control</div>', unsafe_allow_html=True)
    st.markdown(f"**Current Database:** `{st.session_state.selected_realm}`")
    
    # Input for Seed Topic
    seed_input = st.text_input(
        "Core Seed Topic",
        value=st.session_state.seed_topic,
        help="Specify the starting topic node to branch out discovery pathways from."
    )
    
    # Slider for Innovation Horizon Width (1 to 5 tracks)
    width_val = st.slider(
        "Innovation Horizon Width",
        min_value=1,
        max_value=5,
        value=4,
        help="The number of alternative path tracks to extract."
    )
    
    # Execute button
    st.markdown('<div class="b2b-btn">', unsafe_allow_html=True)
    if st.button("⚡ Execute Discovery", use_container_width=True):
        # Validate node
        matched = None
        for n in all_nodes:
            if n.lower() == seed_input.strip().lower():
                matched = n
                break
        if matched:
            st.session_state.seed_topic = matched
            st.session_state.selected_path = None
            st.rerun()
        else:
            st.error(f"'{seed_input}' not found in active graph. Search terms are case-sensitive.")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Switch realm options
    st.markdown("**📂 Switch Sub-Graph**")
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
            if st.button(f"📁 {r}", key=f"switch_r_{r}", use_container_width=True):
                st.session_state.selected_realm = r
                st.session_state.pop("seed_topic", None)
                st.session_state.pop("selected_path", None)
                st.rerun()
                
    if st.button("➕ Construct New Graph", use_container_width=True):
        st.session_state.pop("selected_realm", None)
        st.session_state.pop("seed_topic", None)
        st.session_state.pop("selected_path", None)
        st.rerun()


# ─── CENTER COLUMN: Discovery Tracks ────────────────────────────────────────────
with c_center:
    st.markdown('<div class="workspace-col-title">🛣️ Discovery Horizons</div>', unsafe_allow_html=True)
    st.markdown(f"Displaying tracks branching out from **'{st.session_state.seed_topic}'**:")
    
    discovery_paths = engine.generate_discovery_horizons(
        seed_topic=st.session_state.seed_topic,
        max_depth=4,
        alpha=0.7,
        top_k=width_val
    )
    
    if not discovery_paths:
        st.warning("No discovery pathways found starting at this topic node. Set another topic core or depth.")
        st.info(f"Available node suggestions: {', '.join(all_nodes[:10])}...")
    else:
        # Default selection
        if st.session_state.selected_path is None or st.session_state.selected_path not in discovery_paths:
            st.session_state.selected_path = discovery_paths[0]
            
        for idx, path in enumerate(discovery_paths):
            # Check if selected
            is_selected = (st.session_state.selected_path == path)
            sel_class = "horizon-selected" if is_selected else ""
            
            # Format text chains: A ➔ B ➔ C
            chain_str = " ➔ ".join(path)
            summary_str = get_path_summary(path)
            
            # Styled container card
            st.markdown(f"""
            <div class="horizon-container {sel_class}">
                <div class="horizon-chain-text">🧬 Track {idx+1}: {chain_str}</div>
                <div class="horizon-summary-text">{summary_str}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Click action button
            btn_label = "📊 Selected Workspace" if is_selected else f"🔎 Select Track {idx+1}"
            if st.button(btn_label, key=f"sel_path_btn_{idx}", use_container_width=True, disabled=is_selected):
                st.session_state.selected_path = path
                st.rerun()


# ─── RIGHT COLUMN: Intelligence Workspace ───────────────────────────────────────
with c_right:
    st.markdown('<div class="workspace-col-title">📋 Intelligence Workspace</div>', unsafe_allow_html=True)
    
    if st.session_state.selected_path:
        path = st.session_state.selected_path
        st.markdown(f"### 🧪 Innovation Horizon Brief")
        st.markdown(f"Active Track: **{' ➔ '.join(path)}**")
        
        # Tabs for every node in the selected path
        node_tabs = st.tabs([node for node in path])
        for idx, node in enumerate(path):
            with node_tabs[idx]:
                profile = engine.node_summaries.get(node, {})
                st.markdown(f'<div class="profile-title">🔍 {node} Research Profile</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="profile-section-title">⚙️ Core Mechanism</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="profile-section-body">{profile.get("core_mechanism", "Details not loaded.")}</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="profile-section-title">🔀 Cross-Over Application</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="profile-section-body">{profile.get("cross_over_application", "Details not loaded.")}</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="profile-section-title">💡 Open Innovation Question</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="profile-section-body">{profile.get("open_innovation_question", "Details not loaded.")}</div>', unsafe_allow_html=True)
    else:
        st.info("Select an innovation track from the center column to compile a deep-dive intelligence brief.")
