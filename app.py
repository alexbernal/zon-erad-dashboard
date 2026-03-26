"""
ZON ERAD Experiment Dashboard
Construct CSS Theme (Matrix Green) — Live ERAD experiment monitoring
6-Tab Layout: Overview | Experiments | Analysis | Servers | Activity Log | Wiki

Runs on bizon1 with direct access to Supabase + Temporal.
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
import time
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

REFRESH_INTERVAL = 15  # seconds
WORKFLOW_ID = "erad-experiment-loop-v2"

# On bizon1 these are local
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "http://127.0.0.1:31443")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")
TEMPORAL_ADDRESS = st.secrets.get("TEMPORAL_ADDRESS", "localhost:31733")
TEMPORAL_NAMESPACE = st.secrets.get("TEMPORAL_NAMESPACE", "default")

STRATEGIES = ["shadow_mode", "ab_tester", "thompson_bandit", "bayesian_opt"]
METHODS = ["power_state", "io_scheduler", "memory_manager", "forecaster"]

STRATEGY_LABELS = {
    "shadow_mode": "Shadow Mode", "ab_tester": "A/B Tester",
    "thompson_bandit": "Thompson Bandit", "bayesian_opt": "Bayesian Opt",
}
STRATEGY_SHORT = {
    "shadow_mode": "Shadow", "ab_tester": "A/B",
    "thompson_bandit": "Thompson", "bayesian_opt": "Bayesian",
}
METHOD_LABELS = {
    "power_state": "Power State", "io_scheduler": "I/O Scheduler",
    "memory_manager": "Memory Manager", "forecaster": "Forecaster",
}
METHOD_SHORT = {
    "power_state": "Power", "io_scheduler": "I/O",
    "memory_manager": "Memory", "forecaster": "Forecast",
}
STRATEGY_DESC = {
    "shadow_mode": "Observe-only — no changes applied. Collects pure baseline metrics for comparison.",
    "ab_tester": "Split traffic A/B test with statistical significance testing (t-test, Cohen's d).",
    "thompson_bandit": "Multi-armed bandit using Thompson Sampling with Bayesian reward modeling.",
    "bayesian_opt": "Gaussian process optimization over the configuration space with EI acquisition.",
}
METHOD_DESC = {
    "power_state": "CPU governor, frequency scaling, RAPL power limits, PCIe ASPM, scheduler tuning.",
    "io_scheduler": "Disk I/O scheduler (mq-deadline, none, bfq), queue depth, read-ahead, rq_affinity.",
    "memory_manager": "Hugepages, swappiness, cache pressure, dirty ratios, NUMA policy.",
    "forecaster": "Predictive pre-configuration based on load pattern forecasting.",
}
METHOD_METRICS = {
    "io_scheduler": {"iops_total": (0.40, "max"), "avg_read_latency_ms": (0.35, "min"),
                     "throughput_read_mbps": (0.15, "max"), "power_watts": (0.10, "min")},
    "memory_manager": {"pgmajfault_per_sec": (0.30, "min"), "numa_hit_ratio": (0.25, "max"),
                       "memory_pressure_psi_avg10": (0.20, "min"), "swap_used_mb": (0.15, "min"),
                       "power_watts": (0.10, "min")},
    "power_state": {"power_watts": (0.50, "min"), "context_switches_per_sec": (0.15, "min"),
                    "cpu_pressure_psi_avg10": (0.15, "min"), "cpu_percent": (0.20, "min")},
    "forecaster": {"cpu_percent": (0.35, "min"), "power_watts": (0.25, "min"),
                   "context_switches_per_sec": (0.20, "min"), "cpu_pressure_psi_avg10": (0.20, "min")},
}


# ═══════════════════════════════════════════════════════════════
# Construct CSS Theme (Matrix Green)
# ═══════════════════════════════════════════════════════════════

CONSTRUCT_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');

    :root {
        --nexus-primary: #00ff41;
        --nexus-secondary: #003b00;
        --nexus-bg: #0a0f0a;
        --nexus-glow: rgba(0, 255, 65, 0.3);
        --nexus-border: rgba(0, 255, 65, 0.12);
        --color-ok: #2ecc71;
        --color-warn: #f1c40f;
        --color-error: #ff5555;
        --color-info: #8be9fd;
        --color-muted: #555;
        --color-text: #c0c0c0;
        --color-cyan: #8be9fd;
        --color-purple: #bd93f9;
        --color-orange: #f97316;
        --color-pink: #ff79c6;
        --color-yellow: #f1fa8c;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    .stApp {
        background: var(--nexus-bg);
        font-family: 'JetBrains Mono', monospace;
    }

    .stApp::before {
        content: '';
        position: fixed;
        inset: 0;
        background:
            linear-gradient(rgba(0, 255, 65, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 65, 0.03) 1px, transparent 1px);
        background-size: 50px 50px;
        z-index: 0;
        pointer-events: none;
    }

    [data-testid="stSidebar"] {
        background: #050805 !important;
        border-right: 1px solid var(--nexus-border) !important;
    }
    [data-testid="stSidebar"] .stRadio > label {
        color: var(--nexus-primary) !important;
        font-size: 0.9em;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }

    .sidebar-title {
        color: var(--nexus-primary);
        font-size: 1.5em;
        font-weight: 700;
        text-align: center;
        padding: 20px 0;
        border-bottom: 1px solid var(--nexus-border);
        margin-bottom: 20px;
        text-shadow: 0 0 10px var(--nexus-glow);
    }
    .dashboard-title {
        color: var(--nexus-primary);
        font-size: 2em;
        font-weight: 700;
        margin-bottom: 4px;
        text-shadow: 0 0 10px var(--nexus-glow);
    }
    .dashboard-subtitle {
        color: var(--color-muted);
        font-size: 0.85em;
        margin-bottom: 20px;
    }
    .section-heading {
        color: var(--nexus-primary);
        font-size: 1.1em;
        margin: 20px 0 10px 0;
        border-bottom: 1px solid #222;
        padding-bottom: 6px;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    .metric-card {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid var(--nexus-border);
        border-radius: 6px;
        padding: 15px;
        text-align: center;
        height: 100%;
    }
    .metric-card-large {
        background: rgba(0, 255, 65, 0.05);
        border: 1px solid var(--nexus-border);
        border-radius: 8px;
        padding: 20px;
        text-align: center;
    }
    .metric-label {
        color: var(--color-muted);
        font-size: 0.7em;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 5px;
    }
    .metric-value {
        color: var(--nexus-primary);
        font-size: 1.6em;
        font-weight: 700;
    }
    .metric-value-xl {
        color: var(--nexus-primary);
        font-size: 2.5em;
        font-weight: 700;
    }
    .metric-value-sm {
        color: var(--nexus-primary);
        font-size: 1.2em;
        font-weight: 700;
    }
    .metric-sub {
        font-size: 0.7em;
        color: var(--color-muted);
        margin-top: 3px;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 4px;
        font-size: 0.8em;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .status-running { background: rgba(46, 204, 113, 0.2); color: #2ecc71; border: 1px solid #2ecc71; }
    .status-completed { background: rgba(139, 233, 253, 0.2); color: #8be9fd; border: 1px solid #8be9fd; }
    .status-failed { background: rgba(255, 85, 85, 0.2); color: #ff5555; border: 1px solid #ff5555; }
    .status-paused { background: rgba(241, 196, 15, 0.2); color: #f1c40f; border: 1px solid #f1c40f; }
    .status-cooldown { background: rgba(189, 147, 249, 0.2); color: #bd93f9; border: 1px solid #bd93f9; }

    .text-cyan { color: var(--color-cyan); }
    .text-purple { color: var(--color-purple); }
    .text-orange { color: var(--color-orange); }
    .text-pink { color: var(--color-pink); }
    .text-yellow { color: var(--color-yellow); }
    .text-ok { color: var(--color-ok); }
    .text-warn { color: var(--color-warn); }
    .text-error { color: var(--color-error); }

    .experiment-card {
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid var(--nexus-border);
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
    }
    .experiment-card.running {
        border-left: 3px solid #2ecc71;
        background: rgba(0, 255, 65, 0.03);
    }
    .experiment-card.completed { border-left: 3px solid #8be9fd; }
    .experiment-card.failed { border-left: 3px solid #ff5555; }

    .pipeline-step {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 0.8em;
        margin: 2px;
    }
    .pipeline-active {
        background: rgba(0, 255, 65, 0.15);
        color: var(--nexus-primary);
        border: 1px solid var(--nexus-primary);
    }
    .pipeline-done {
        background: rgba(139, 233, 253, 0.1);
        color: var(--color-cyan);
        border: 1px solid rgba(139, 233, 253, 0.3);
    }
    .pipeline-pending {
        background: rgba(85, 85, 85, 0.2);
        color: var(--color-muted);
        border: 1px solid #333;
    }

    .heatmap-cell {
        display: inline-block;
        width: 80px;
        height: 40px;
        text-align: center;
        line-height: 40px;
        font-size: 0.8em;
        font-weight: 600;
        border-radius: 4px;
        margin: 2px;
    }

    .wiki-section {
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid var(--nexus-border);
        border-radius: 8px;
        padding: 20px;
        margin: 15px 0;
    }
    .wiki-section h3 {
        color: var(--nexus-primary);
        margin-bottom: 15px;
        border-bottom: 1px solid #222;
        padding-bottom: 8px;
    }
    .wiki-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85em;
    }
    .wiki-table th {
        background: rgba(0, 255, 65, 0.1);
        color: var(--nexus-primary);
        padding: 10px;
        text-align: left;
        border-bottom: 1px solid var(--nexus-border);
    }
    .wiki-table td {
        padding: 10px;
        border-bottom: 1px solid #1a1a1a;
        color: var(--color-text);
    }
    .wiki-table tr:hover { background: rgba(0, 255, 65, 0.05); }
    .glossary-term {
        color: var(--color-cyan);
        font-weight: 600;
    }
    .code-block {
        background: #0d0d0d;
        border: 1px solid #222;
        border-radius: 4px;
        padding: 10px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85em;
        color: var(--color-text);
        overflow-x: auto;
    }
    .progress-bar-outer {
        background: rgba(0, 0, 0, 0.6);
        border: 1px solid var(--nexus-border);
        border-radius: 4px;
        height: 24px;
        width: 100%;
        overflow: hidden;
    }
    .progress-bar-inner {
        height: 100%;
        border-radius: 3px;
        transition: width 0.5s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.7em;
        font-weight: 700;
        color: #000;
    }

    [data-testid="stMetricValue"] {
        color: var(--nexus-primary) !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid var(--nexus-border);
        border-radius: 4px 4px 0 0;
        color: var(--color-text);
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85em;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(0, 255, 65, 0.1) !important;
        border-color: var(--nexus-primary) !important;
        color: var(--nexus-primary) !important;
    }
</style>
"""


# ═══════════════════════════════════════════════════════════════
# Data Fetchers
# ═══════════════════════════════════════════════════════════════

def _run_async(coro):
    """Run async coroutine from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result(timeout=15)
        return loop.run_until_complete(coro)
    except Exception:
        return asyncio.run(coro)


@st.cache_resource(ttl=300)
def get_temporal_client():
    """Create Temporal client (cached for 5 min)."""
    try:
        from temporalio.client import Client
        client = _run_async(Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_NAMESPACE))
        return client
    except Exception as e:
        st.warning(f"Temporal connection failed: {e}")
        return None


def query_temporal(query_name: str) -> Optional[Any]:
    """Query the ERAD workflow."""
    client = get_temporal_client()
    if not client:
        return None
    try:
        handle = client.get_workflow_handle(WORKFLOW_ID)
        return _run_async(handle.query(query_name))
    except Exception:
        return None


def fetch_supabase(endpoint: str, params: dict = None) -> list:
    """Fetch from Supabase REST API with erad schema."""
    try:
        import httpx
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Accept-Profile": "erad",
        }
        with httpx.Client(timeout=10.0) as c:
            r = c.get(f"{SUPABASE_URL}/rest/v1/{endpoint}", headers=headers, params=params or {})
            return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def fetch_experiment_results(limit: int = 50) -> List[Dict]:
    """Fetch recent experiment results from Supabase."""
    return fetch_supabase("experiment_results", {
        "select": "id,strategy,method,server_hostname,status,wall_time_seconds,"
                  "conclusion_json,config_json,iteration_log_json,error_message,created_at",
        "order": "created_at.desc",
        "limit": str(limit),
    })


def fetch_effectiveness_matrix() -> List[Dict]:
    """Fetch strategy x method effectiveness matrix."""
    return fetch_supabase("strategy_method_effectiveness", {"select": "*"})


def fetch_config_evolution() -> List[Dict]:
    """Fetch config evolution data."""
    return fetch_supabase("config_evolution", {
        "select": "config_json,fitness_score,generation,strategy,method,hardware_profile,created_at",
        "order": "created_at.desc",
        "limit": "200",
    })


@st.cache_data(ttl=REFRESH_INTERVAL)
def load_all_data() -> Dict:
    """Load all data sources in one call (cached per refresh interval)."""
    status = query_temporal("get_status")
    progress = query_temporal("get_progress")
    knowledge = query_temporal("get_knowledge_summary")
    results = fetch_experiment_results(50)
    matrix = fetch_effectiveness_matrix()
    evolution = fetch_config_evolution()
    return {
        "status": status, "progress": progress, "knowledge": knowledge,
        "results": results, "matrix": matrix, "evolution": evolution,
        "fetched_at": datetime.now(timezone.utc),
    }


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

def fitness_color(score: float) -> str:
    if score >= 5.0: return "#2ecc71"
    if score >= 2.0: return "#00ff41"
    if score >= 0.5: return "#f1c40f"
    if score > 0: return "#f97316"
    return "#ff5555"


def status_badge(status: str) -> str:
    css_class = {
        "completed": "status-completed", "failed": "status-failed",
        "running": "status-running", "timeout": "status-paused",
        "rolled_back": "status-failed",
    }.get(status, "status-cooldown")
    return f'<span class="status-badge {css_class}">{status.upper()}</span>'


def policies_deployed(r: dict) -> str:
    """Extract compact policy pills from config_json."""
    cfg = r.get("config_json") or {}
    if isinstance(cfg, str):
        try: cfg = json.loads(cfg)
        except Exception: cfg = {}

    method = r.get("method", "")
    parts = []

    def _v(d, key):
        return d.get(key, d) if isinstance(d, dict) else d

    if method == "io_scheduler":
        if "set_io_scheduler" in cfg: parts.append(str(_v(cfg["set_io_scheduler"], "scheduler")))
        if "set_queue_depth" in cfg: parts.append(f'depth={_v(cfg["set_queue_depth"], "depth")}')
        if "set_read_ahead_kb" in cfg: parts.append(f'ra={_v(cfg["set_read_ahead_kb"], "kb")}KB')
        if "set_rq_affinity" in cfg: parts.append(f'rq={_v(cfg["set_rq_affinity"], "mode")}')
    elif method == "memory_manager":
        if "set_swappiness" in cfg: parts.append(f'swap={_v(cfg["set_swappiness"], "value")}')
        if "set_dirty_ratio" in cfg: parts.append(f'dirty={_v(cfg["set_dirty_ratio"], "pct")}%')
        if "set_hugepages" in cfg: parts.append(f'thp={_v(cfg["set_hugepages"], "mode")}')
        if "set_numa_policy" in cfg: parts.append(f'numa={_v(cfg["set_numa_policy"], "policy")}')
    elif method == "power_state":
        if "set_pcie_aspm" in cfg: parts.append(f'aspm={_v(cfg["set_pcie_aspm"], "policy")}')
        if "set_sched_migration_cost" in cfg:
            try: parts.append(f'mig={int(_v(cfg["set_sched_migration_cost"], "ns"))//1000}us')
            except Exception: parts.append("mig=?")
        if "set_sched_latency" in cfg:
            try: parts.append(f'lat={int(_v(cfg["set_sched_latency"], "ns"))//1000000}ms')
            except Exception: parts.append("lat=?")
    elif method == "forecaster":
        if "mode" in cfg: parts.append(f'scaling={cfg["mode"]}')
        if "preemptive_scaling" in cfg: parts.append(f'scaling={cfg["preemptive_scaling"]}')
        if "schedule_policy" in cfg: parts.append(f'sched={cfg["schedule_policy"]}')

    if not parts:
        for k, v in list(cfg.items())[:3]:
            sk = k.replace("set_", "")
            sv = str(list(v.values())[0])[:10] if isinstance(v, dict) and v else str(v)[:10]
            parts.append(f"{sk}={sv}")

    joined = " | ".join(str(p) for p in parts)
    return joined[:80] if joined else "(no details)"


def parse_conclusion(r: dict) -> dict:
    conc = r.get("conclusion_json") or {}
    if isinstance(conc, str):
        try: conc = json.loads(conc)
        except Exception: conc = {}
    return conc


# ═══════════════════════════════════════════════════════════════
# TAB 1: OVERVIEW
# ═══════════════════════════════════════════════════════════════

def render_overview_tab(data: Dict):
    st.markdown('<div class="dashboard-title">ERAD EXPERIMENT ENGINE</div>', unsafe_allow_html=True)
    st.markdown('<div class="dashboard-subtitle">Evaluate \u2022 Recommend \u2022 Adapt \u2022 Discover \u2014 Live Experiment Monitoring</div>', unsafe_allow_html=True)

    status = data.get("status") or {}
    progress = data.get("progress") or {}
    knowledge = data.get("knowledge") or {}
    results = data.get("results") or []
    matrix = data.get("matrix") or []

    current = status.get("current_experiment")
    done = status.get("experiments_completed", 0)
    total = status.get("experiments_total", 0)
    cycle = status.get("cycle_number", 0)
    paused = status.get("paused", False)
    servers = status.get("servers", [])
    total_all = status.get("total_experiments_completed", 0)
    total_cyc = status.get("total_cycles_completed", 0)

    # Connection status
    if not status:
        st.markdown('''<div class="experiment-card" style="border-left: 3px solid #f1c40f;">
            <span style="color: #f1c40f; font-size: 1.2em; font-weight: 700;">CONNECTING...</span><br>
            <span style="color: var(--color-muted); font-size: 0.9em;">Attempting to reach Temporal workflow at ''' + TEMPORAL_ADDRESS + '''</span>
        </div>''', unsafe_allow_html=True)
        return

    # ── Top Metrics ──
    st.markdown('<div class="section-heading">SYSTEM STATUS</div>', unsafe_allow_html=True)
    col1, col2, col3, col4, col5 = st.columns(5)

    state_label = "PAUSED" if paused else ("RUNNING" if current else "COOLDOWN")
    state_class = "status-paused" if paused else ("status-running" if current else "status-cooldown")

    with col1:
        st.markdown(f'''<div class="metric-card-large">
            <div class="metric-label">Engine State</div>
            <div style="margin-top: 8px;"><span class="status-badge {state_class}">{state_label}</span></div>
        </div>''', unsafe_allow_html=True)
    with col2:
        st.markdown(f'''<div class="metric-card-large">
            <div class="metric-label">Current Cycle</div>
            <div class="metric-value-xl">{cycle}</div>
            <div class="metric-sub">{done}/{total} experiments</div>
        </div>''', unsafe_allow_html=True)
    with col3:
        st.markdown(f'''<div class="metric-card-large">
            <div class="metric-label">Total Experiments</div>
            <div class="metric-value-xl text-cyan">{total_all}</div>
            <div class="metric-sub">{total_cyc} cycles completed</div>
        </div>''', unsafe_allow_html=True)
    with col4:
        st.markdown(f'''<div class="metric-card-large">
            <div class="metric-label">Servers</div>
            <div class="metric-value-xl text-purple">{len(servers)}</div>
            <div class="metric-sub">{', '.join(s.split('.')[0] for s in servers) if servers else 'none'}</div>
        </div>''', unsafe_allow_html=True)
    with col5:
        completed = [r for r in results if r.get("status") == "completed"]
        improvements = [parse_conclusion(r).get("primary_metric_improvement", 0) for r in completed if parse_conclusion(r).get("primary_metric_improvement")]
        avg_imp = np.mean(improvements) if improvements else 0
        st.markdown(f'''<div class="metric-card-large">
            <div class="metric-label">Avg Improvement</div>
            <div class="metric-value-xl {'text-ok' if avg_imp > 0 else 'text-warn'}">{avg_imp:+.1f}%</div>
            <div class="metric-sub">across {len(improvements)} results</div>
        </div>''', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Current Experiment ──
    left_col, right_col = st.columns([3, 2])

    with left_col:
        st.markdown('<div class="section-heading">CURRENT EXPERIMENT</div>', unsafe_allow_html=True)
        if current:
            strat = current.get("strategy", "?")
            meth = current.get("method", "?")
            srv = current.get("server", "?")
            hw = current.get("hardware_profile", "?")
            started = status.get("current_experiment_started_at", "")
            elapsed = ""
            if started:
                try:
                    dt = datetime.fromisoformat(started)
                    secs = (datetime.now(timezone.utc) - dt).total_seconds()
                    em, es = divmod(int(secs), 60)
                    elapsed = f"{em}m {es}s"
                except Exception:
                    elapsed = "..."

            st.markdown(f'''<div class="experiment-card running">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: #2ecc71; font-size: 1.3em; font-weight: 700;">EXPERIMENT {done+1} OF {total}</span>
                    <span class="status-badge status-running">LIVE</span>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 15px;">
                    <div><span style="color: var(--color-muted); font-size: 0.8em;">STRATEGY</span><br>
                        <span style="color: var(--color-cyan); font-size: 1.1em; font-weight: 600;">{STRATEGY_LABELS.get(strat, strat)}</span></div>
                    <div><span style="color: var(--color-muted); font-size: 0.8em;">METHOD</span><br>
                        <span style="color: var(--color-purple); font-size: 1.1em; font-weight: 600;">{METHOD_LABELS.get(meth, meth)}</span></div>
                    <div><span style="color: var(--color-muted); font-size: 0.8em;">SERVER</span><br>
                        <span style="color: var(--nexus-primary); font-size: 1.1em; font-weight: 600;">{srv}</span></div>
                    <div><span style="color: var(--color-muted); font-size: 0.8em;">ELAPSED</span><br>
                        <span style="color: var(--color-yellow); font-size: 1.1em; font-weight: 600;">{elapsed}</span></div>
                </div>
                <div style="margin-top: 15px;">
                    <span style="color: var(--color-muted); font-size: 0.8em;">PIPELINE</span><br>
                    <span class="pipeline-step pipeline-done">Collect Metrics</span>
                    <span style="color: var(--color-muted);">\u2192</span>
                    <span class="pipeline-step pipeline-active">Apply Actions</span>
                    <span style="color: var(--color-muted);">\u2192</span>
                    <span class="pipeline-step pipeline-pending">Measure Results</span>
                    <span style="color: var(--color-muted);">\u2192</span>
                    <span class="pipeline-step pipeline-pending">ASIT Analysis</span>
                </div>
                <div style="margin-top: 12px; color: var(--color-muted); font-size: 0.8em;">
                    {STRATEGY_DESC.get(strat, '')}<br>
                    {METHOD_DESC.get(meth, '')}
                </div>
            </div>''', unsafe_allow_html=True)
        elif paused:
            st.markdown('''<div class="experiment-card" style="border-left: 3px solid #f1c40f;">
                <span style="color: #f1c40f; font-size: 1.2em; font-weight: 700;">PAUSED</span><br>
                <span style="color: var(--color-muted);">Experiment loop is paused. Resume via Temporal or TUI.</span>
            </div>''', unsafe_allow_html=True)
        else:
            st.markdown(f'''<div class="experiment-card" style="border-left: 3px solid #bd93f9;">
                <span style="color: #bd93f9; font-size: 1.2em; font-weight: 700;">COOLDOWN</span><br>
                <span style="color: var(--color-muted);">Between experiments ({done}/{total} completed). Next starting soon...</span>
            </div>''', unsafe_allow_html=True)

    # ── Cycle Progress ──
    with right_col:
        st.markdown('<div class="section-heading">CYCLE PROGRESS</div>', unsafe_allow_html=True)
        pct = (done / total * 100) if total > 0 else 0
        bar_color = "#00ff41" if pct > 0 else "#333"

        st.markdown(f'''<div style="margin-bottom: 12px;">
            <div class="progress-bar-outer">
                <div class="progress-bar-inner" style="width: {max(pct, 2)}%; background: linear-gradient(90deg, #003b00, {bar_color});">
                    {pct:.0f}%
                </div>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 4px; font-size: 0.75em; color: var(--color-muted);">
                <span>{done} done</span>
                <span>{total - done} remaining</span>
            </div>
        </div>''', unsafe_allow_html=True)

        # Strategy breakdown
        order = progress.get("experiment_order", [])
        if order:
            ns = len(servers) if servers else 1
            ci = done // ns if ns else done
            breakdown_html = ""
            for strat in STRATEGIES:
                idxs = [i for i, (s, _) in enumerate(order) if s == strat]
                st_total = len(idxs)
                st_done = sum(1 for idx in idxs if idx * ns < done)
                label = STRATEGY_SHORT.get(strat, strat)
                if strat == (order[ci][0] if ci < len(order) else None):
                    icon, color = "\u25b6", "#00ff41"
                elif st_done == st_total and st_total > 0:
                    icon, color = "\u2713", "#2ecc71"
                else:
                    icon, color = "\u00b7", "#555"
                dots = '<span style="color: #2ecc71;">\u25cf</span>' * st_done + '<span style="color: #333;">\u25cb</span>' * (st_total - st_done)
                breakdown_html += f'<div style="margin: 3px 0; font-size: 0.85em;"><span style="color: {color};">{icon}</span> <span style="color: {color}; width: 70px; display: inline-block;">{label}</span> {dots} <span style="color: var(--color-muted);"> {st_done}/{st_total}</span></div>'
            st.markdown(f'<div style="background: rgba(0,0,0,0.3); border: 1px solid var(--nexus-border); border-radius: 6px; padding: 12px;">{breakdown_html}</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Bottom row: Heatmap + Knowledge ──
    heat_col, know_col = st.columns([3, 2])

    with heat_col:
        st.markdown('<div class="section-heading">STRATEGY \u00d7 METHOD EFFECTIVENESS</div>', unsafe_allow_html=True)
        render_heatmap(matrix)

    with know_col:
        st.markdown('<div class="section-heading">KNOWLEDGE BASE</div>', unsafe_allow_html=True)
        te = knowledge.get("total_experiments", 0) if knowledge else 0
        tc = knowledge.get("total_cycles", 0) if knowledge else 0
        best = knowledge.get("best_combos", []) if knowledge else []

        know_html = f'''<div style="background: rgba(0,0,0,0.3); border: 1px solid var(--nexus-border); border-radius: 6px; padding: 15px;">
            <div style="display: flex; gap: 30px; margin-bottom: 12px;">
                <div><span style="color: var(--color-muted); font-size: 0.75em;">EXPERIMENTS</span><br>
                    <span style="color: var(--nexus-primary); font-size: 1.4em; font-weight: 700;">{te}</span></div>
                <div><span style="color: var(--color-muted); font-size: 0.75em;">CYCLES</span><br>
                    <span style="color: var(--color-cyan); font-size: 1.4em; font-weight: 700;">{tc}</span></div>
            </div>
            <div style="color: var(--color-muted); font-size: 0.8em; margin-bottom: 8px;">TOP COMBINATIONS</div>'''

        if best:
            for i, c in enumerate(best[:5], 1):
                s = STRATEGY_SHORT.get(c.get("strategy", ""), "?")
                m = METHOD_SHORT.get(c.get("method", ""), "?")
                f = c.get("fitness", 0)
                fc = fitness_color(f)
                know_html += f'''<div style="margin: 4px 0; font-size: 0.85em;">
                    <span style="color: var(--color-muted);">#{i}</span>
                    <span style="color: var(--color-cyan);">{s}</span>
                    <span style="color: var(--color-muted);">\u00d7</span>
                    <span style="color: var(--color-purple);">{m}</span>
                    <span style="color: {fc}; float: right;">fitness={f:.2f}</span>
                </div>'''
        else:
            know_html += '<div style="color: var(--color-muted); font-size: 0.85em; font-style: italic;">Building knowledge... best combos appear after cycle 1.</div>'

        know_html += "</div>"
        st.markdown(know_html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Recent Results ──
    st.markdown('<div class="section-heading">RECENT EXPERIMENT RESULTS</div>', unsafe_allow_html=True)
    render_results_compact(results[:8])


def render_heatmap(matrix: List[Dict]):
    """Render strategy x method heatmap using Plotly."""
    import plotly.graph_objects as go

    lookup = {}
    for row in matrix:
        key = f"{row.get('strategy', '')}|{row.get('method', '')}"
        lookup[key] = row.get("avg_improvement", 0.0)

    z = []
    for s in STRATEGIES:
        row = []
        for m in METHODS:
            row.append(lookup.get(f"{s}|{m}", 0.0))
        z.append(row)

    text = []
    for row in z:
        text.append([f"{v:+.4f}" if v != 0 else "--" for v in row])

    fig = go.Figure(data=go.Heatmap(
        z=z, x=[METHOD_SHORT[m] for m in METHODS],
        y=[STRATEGY_SHORT[s] for s in STRATEGIES],
        text=text, texttemplate="%{text}", textfont={"size": 12, "color": "white"},
        colorscale=[[0, "#1a0000"], [0.3, "#331100"], [0.5, "#333300"], [0.7, "#003300"], [1, "#00ff41"]],
        showscale=True,
        colorbar=dict(title=dict(text="Improvement", font=dict(color="#888")), tickfont=dict(color="#888")),
    ))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0.2)",
        margin=dict(l=80, r=30, t=10, b=50), height=220,
        xaxis=dict(side="bottom", tickfont=dict(color="#00ff41")),
        yaxis=dict(tickfont=dict(color="#00ff41"), autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_results_compact(results: List[Dict]):
    """Render compact results table."""
    if not results:
        st.markdown('<div style="color: var(--color-muted); padding: 20px; text-align: center;">No experiment results yet. Waiting for first experiment to complete...</div>', unsafe_allow_html=True)
        return

    header = '''<div style="display: grid; grid-template-columns: 70px 85px 85px 80px 60px 1fr; gap: 4px; padding: 8px 12px; border-bottom: 1px solid var(--nexus-border); font-size: 0.75em; color: var(--color-muted); text-transform: uppercase;">
        <span>Time</span><span>Strategy</span><span>Method</span><span>Status</span><span>Duration</span><span>Policies Deployed & Results</span></div>'''

    rows = ""
    for r in results:
        created = (r.get("created_at", "") or "")[11:19] or "--"
        s_status = r.get("status", "?")
        conc = parse_conclusion(r)
        imp = conc.get("primary_metric_improvement", 0)
        wt = r.get("wall_time_seconds", 0)
        dur = f"{wt // 60}m{wt % 60}s" if wt else "--"
        pol = policies_deployed(r)

        imp_html = ""
        if imp and imp > 0:
            imp_html = f'<span style="color: #2ecc71; font-weight: 600;">+{imp:.1f}%</span> '
        elif imp:
            imp_html = f'<span style="color: #f97316;">{imp:+.1f}%</span> '

        rows += f'''<div style="display: grid; grid-template-columns: 70px 85px 85px 80px 60px 1fr; gap: 4px; padding: 6px 12px; border-bottom: 1px solid #111; font-size: 0.82em; align-items: center;">
            <span style="color: var(--color-muted);">{created}</span>
            <span style="color: var(--color-cyan);">{STRATEGY_SHORT.get(r.get('strategy', ''), '?')}</span>
            <span style="color: var(--color-purple);">{METHOD_SHORT.get(r.get('method', ''), '?')}</span>
            <span>{status_badge(s_status)}</span>
            <span style="color: var(--color-text);">{dur}</span>
            <span>{imp_html}<span style="color: var(--color-muted);">\u21b3</span> <span style="color: var(--color-cyan); font-size: 0.9em;">{pol}</span></span>
        </div>'''

    st.markdown(f'''<div style="background: rgba(0,0,0,0.3); border: 1px solid var(--nexus-border); border-radius: 6px; overflow: hidden;">
        {header}{rows}</div>''', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# TAB 2: EXPERIMENTS
# ═══════════════════════════════════════════════════════════════

def render_experiments_tab(data: Dict):
    st.markdown('<div class="dashboard-title">EXPERIMENT RESULTS</div>', unsafe_allow_html=True)
    st.markdown('<div class="dashboard-subtitle">Detailed View \u2022 Policies Deployed \u2022 Iteration Logs \u2022 Winners</div>', unsafe_allow_html=True)

    results = data.get("results") or []
    if not results:
        st.info("No experiment results available yet.")
        return

    # Filters
    st.markdown('<div class="section-heading">FILTERS</div>', unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        strat_filter = st.multiselect("Strategy", STRATEGIES, format_func=lambda x: STRATEGY_LABELS.get(x, x))
    with fc2:
        meth_filter = st.multiselect("Method", METHODS, format_func=lambda x: METHOD_LABELS.get(x, x))
    with fc3:
        status_filter = st.multiselect("Status", ["completed", "failed", "timeout", "rolled_back"])

    filtered = results
    if strat_filter:
        filtered = [r for r in filtered if r.get("strategy") in strat_filter]
    if meth_filter:
        filtered = [r for r in filtered if r.get("method") in meth_filter]
    if status_filter:
        filtered = [r for r in filtered if r.get("status") in status_filter]

    st.markdown(f'<div style="color: var(--color-muted); font-size: 0.85em; margin-bottom: 10px;">Showing {len(filtered)} of {len(results)} experiments</div>', unsafe_allow_html=True)

    for r in filtered:
        conc = parse_conclusion(r)
        created = r.get("created_at", "")[:19] or "--"
        strat = r.get("strategy", "?")
        meth = r.get("method", "?")
        srv = (r.get("server_hostname", "?") or "?").split(".")[0]
        s_status = r.get("status", "?")
        wt = r.get("wall_time_seconds", 0)
        dur = f"{wt // 60}m {wt % 60}s" if wt else "--"
        winner = conc.get("winner", "baseline")
        imp = conc.get("primary_metric_improvement", 0)
        conf = conc.get("confidence", 0)
        iters = conc.get("iterations_completed", 0)
        summary = conc.get("summary", "")
        pol = policies_deployed(r)
        error = r.get("error_message", "")

        card_class = {"completed": "completed", "failed": "failed", "running": "running"}.get(s_status, "")
        imp_html = f'<span style="color: #2ecc71; font-size: 1.1em; font-weight: 700;">+{imp:.1f}%</span>' if imp and imp > 0 else (
            f'<span style="color: #f97316;">{imp:+.1f}%</span>' if imp else '<span style="color: var(--color-muted);">--</span>')

        with st.expander(f"{created} | {STRATEGY_SHORT.get(strat, strat)} \u00d7 {METHOD_SHORT.get(meth, meth)} | {srv} | {s_status.upper()}", expanded=False):
            st.markdown(f'''<div class="experiment-card {card_class}">
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 15px;">
                    <div><span style="color: var(--color-muted); font-size: 0.75em;">STRATEGY</span><br>
                        <span style="color: var(--color-cyan); font-weight: 600;">{STRATEGY_LABELS.get(strat, strat)}</span></div>
                    <div><span style="color: var(--color-muted); font-size: 0.75em;">METHOD</span><br>
                        <span style="color: var(--color-purple); font-weight: 600;">{METHOD_LABELS.get(meth, meth)}</span></div>
                    <div><span style="color: var(--color-muted); font-size: 0.75em;">SERVER</span><br>
                        <span style="color: var(--nexus-primary); font-weight: 600;">{srv}</span></div>
                    <div><span style="color: var(--color-muted); font-size: 0.75em;">STATUS</span><br>
                        {status_badge(s_status)}</div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 15px;">
                    <div><span style="color: var(--color-muted); font-size: 0.75em;">WINNER</span><br>
                        <span style="color: {'#2ecc71' if winner != 'baseline' else 'var(--color-muted)'}; font-weight: 600;">{winner}</span></div>
                    <div><span style="color: var(--color-muted); font-size: 0.75em;">IMPROVEMENT</span><br>{imp_html}</div>
                    <div><span style="color: var(--color-muted); font-size: 0.75em;">CONFIDENCE</span><br>
                        <span style="color: var(--color-text);">{conf:.0%}</span></div>
                    <div><span style="color: var(--color-muted); font-size: 0.75em;">DURATION</span><br>
                        <span style="color: var(--color-yellow);">{dur} ({iters} iters)</span></div>
                </div>
                <div style="margin-bottom: 10px;">
                    <span style="color: var(--color-muted); font-size: 0.75em;">POLICIES DEPLOYED</span><br>
                    <span style="color: var(--color-cyan); font-size: 0.9em;">{pol}</span>
                </div>
                {f'<div style="color: var(--color-text); font-size: 0.85em; background: rgba(0,0,0,0.3); padding: 10px; border-radius: 4px;">{summary}</div>' if summary else ''}
                {f'<div style="color: var(--color-error); font-size: 0.85em; margin-top: 8px;">Error: {error}</div>' if error else ''}
            </div>''', unsafe_allow_html=True)

            # Iteration log
            log = r.get("iteration_log_json") or []
            if isinstance(log, str):
                try: log = json.loads(log)
                except Exception: log = []
            if log:
                st.markdown('<span style="color: var(--color-muted); font-size: 0.8em;">ITERATION LOG</span>', unsafe_allow_html=True)
                df_log = pd.DataFrame(log)
                if not df_log.empty:
                    st.dataframe(df_log, use_container_width=True, height=200)


# ═══════════════════════════════════════════════════════════════
# TAB 3: ANALYSIS
# ═══════════════════════════════════════════════════════════════

def render_analysis_tab(data: Dict):
    st.markdown('<div class="dashboard-title">EXPERIMENT ANALYSIS</div>', unsafe_allow_html=True)
    st.markdown('<div class="dashboard-subtitle">Trends \u2022 Convergence \u2022 Fitness Evolution \u2022 Strategy Comparison</div>', unsafe_allow_html=True)

    results = data.get("results") or []
    evolution = data.get("evolution") or []

    if not results:
        st.info("No experiment data available for analysis yet.")
        return

    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    # ── Improvement over time ──
    st.markdown('<div class="section-heading">IMPROVEMENT OVER TIME</div>', unsafe_allow_html=True)
    completed = [r for r in results if r.get("status") == "completed"]
    if completed:
        df_imp = pd.DataFrame([{
            "created_at": pd.to_datetime(r.get("created_at")),
            "strategy": STRATEGY_SHORT.get(r.get("strategy", ""), "?"),
            "method": METHOD_SHORT.get(r.get("method", ""), "?"),
            "improvement": parse_conclusion(r).get("primary_metric_improvement", 0),
            "fitness": parse_conclusion(r).get("fitness_score", 0),
        } for r in completed]).sort_values("created_at")

        fig = go.Figure()
        for strat in df_imp["strategy"].unique():
            mask = df_imp["strategy"] == strat
            fig.add_trace(go.Scatter(
                x=df_imp[mask]["created_at"], y=df_imp[mask]["improvement"],
                mode="lines+markers", name=strat,
                line=dict(width=2), marker=dict(size=6),
            ))
        fig.add_hline(y=0, line_dash="dash", line_color="#555", annotation_text="baseline")
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0.2)",
            margin=dict(l=50, r=20, t=30, b=50), height=350,
            yaxis=dict(title="Improvement %", gridcolor="rgba(0, 255, 65, 0.1)"),
            xaxis=dict(gridcolor="rgba(0, 255, 65, 0.1)"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.markdown('<div style="color: var(--color-muted); padding: 30px; text-align: center;">No completed experiments yet.</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Strategy x Method bar chart ──
    st.markdown('<div class="section-heading">STRATEGY \u00d7 METHOD PERFORMANCE</div>', unsafe_allow_html=True)
    if completed:
        perf_data = []
        for r in completed:
            conc = parse_conclusion(r)
            perf_data.append({
                "combo": f"{STRATEGY_SHORT.get(r.get('strategy', ''), '?')} \u00d7 {METHOD_SHORT.get(r.get('method', ''), '?')}",
                "improvement": conc.get("primary_metric_improvement", 0),
            })
        df_perf = pd.DataFrame(perf_data)
        df_avg = df_perf.groupby("combo")["improvement"].agg(["mean", "count"]).reset_index()
        df_avg = df_avg.sort_values("mean", ascending=True)

        colors = ["#ff5555" if v < 0 else "#00ff41" for v in df_avg["mean"]]
        fig = go.Figure(go.Bar(
            x=df_avg["mean"], y=df_avg["combo"], orientation="h",
            marker_color=colors,
            text=[f"{v:+.2f}% (n={int(n)})" for v, n in zip(df_avg["mean"], df_avg["count"])],
            textposition="auto",
            textfont=dict(color="white"),
        ))
        fig.add_vline(x=0, line_color="#555")
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0.2)",
            margin=dict(l=120, r=20, t=10, b=40), height=max(250, len(df_avg) * 35),
            xaxis=dict(title="Avg Improvement %", gridcolor="rgba(0, 255, 65, 0.1)"),
            yaxis=dict(gridcolor="rgba(0, 255, 65, 0.1)"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Experiment Duration Distribution ──
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="section-heading">EXPERIMENT DURATION</div>', unsafe_allow_html=True)
        durations = [r.get("wall_time_seconds", 0) for r in results if r.get("wall_time_seconds")]
        if durations:
            fig = go.Figure(go.Histogram(
                x=[d/60 for d in durations], nbinsx=20,
                marker_color="#00ff41", marker_line_color="#003b00", marker_line_width=1,
            ))
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0.2)",
                margin=dict(l=50, r=20, t=10, b=40), height=280,
                xaxis=dict(title="Duration (minutes)", gridcolor="rgba(0, 255, 65, 0.1)"),
                yaxis=dict(title="Count", gridcolor="rgba(0, 255, 65, 0.1)"),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with c2:
        st.markdown('<div class="section-heading">SUCCESS RATE BY STATUS</div>', unsafe_allow_html=True)
        status_counts = {}
        for r in results:
            s = r.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1
        if status_counts:
            colors_map = {"completed": "#8be9fd", "failed": "#ff5555", "timeout": "#f1c40f", "rolled_back": "#f97316"}
            fig = go.Figure(go.Pie(
                labels=list(status_counts.keys()),
                values=list(status_counts.values()),
                marker=dict(colors=[colors_map.get(s, "#555") for s in status_counts.keys()]),
                textfont=dict(color="white"),
                hole=0.4,
            ))
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=10, b=20), height=280,
                legend=dict(font=dict(color="#c0c0c0")),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Fitness Evolution ──
    if evolution:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-heading">FITNESS EVOLUTION (CONFIG SPACE)</div>', unsafe_allow_html=True)
        df_evo = pd.DataFrame(evolution)
        if "fitness_score" in df_evo.columns and "generation" in df_evo.columns:
            df_evo["generation"] = pd.to_numeric(df_evo["generation"], errors="coerce")
            df_evo["fitness_score"] = pd.to_numeric(df_evo["fitness_score"], errors="coerce")
            df_evo = df_evo.dropna(subset=["generation", "fitness_score"])

            if not df_evo.empty:
                df_gen = df_evo.groupby("generation")["fitness_score"].agg(["mean", "max"]).reset_index()
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_gen["generation"], y=df_gen["max"], mode="lines+markers", name="Best Fitness", line=dict(color="#00ff41", width=2)))
                fig.add_trace(go.Scatter(x=df_gen["generation"], y=df_gen["mean"], mode="lines", name="Avg Fitness", line=dict(color="#8be9fd", width=1, dash="dash")))
                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0.2)",
                    margin=dict(l=50, r=20, t=30, b=50), height=300,
                    xaxis=dict(title="Generation", gridcolor="rgba(0, 255, 65, 0.1)"),
                    yaxis=dict(title="Fitness Score", gridcolor="rgba(0, 255, 65, 0.1)"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ═══════════════════════════════════════════════════════════════
# TAB 4: SERVERS
# ═══════════════════════════════════════════════════════════════

def render_servers_tab(data: Dict):
    st.markdown('<div class="dashboard-title">SERVER VIEW</div>', unsafe_allow_html=True)
    st.markdown('<div class="dashboard-subtitle">Per-Server Experiment History \u2022 Policies Applied \u2022 Performance Impact</div>', unsafe_allow_html=True)

    results = data.get("results") or []
    status = data.get("status") or {}
    servers = status.get("servers", [])

    if not servers and results:
        servers = list(set(r.get("server_hostname", "unknown") for r in results if r.get("server_hostname")))

    if not servers:
        st.info("No servers detected. Waiting for experiments to start...")
        return

    selected = st.selectbox("Select Server:", servers, format_func=lambda x: x.split(".")[0])

    server_results = [r for r in results if r.get("server_hostname") == selected]
    st.markdown(f'<div class="section-heading">{selected.split(".")[0].upper()} \u2014 {len(server_results)} EXPERIMENTS</div>', unsafe_allow_html=True)

    if not server_results:
        st.markdown('<div style="color: var(--color-muted); padding: 20px; text-align: center;">No experiments completed on this server yet.</div>', unsafe_allow_html=True)
        return

    # Summary stats
    completed = [r for r in server_results if r.get("status") == "completed"]
    failed = [r for r in server_results if r.get("status") in ("failed", "rolled_back")]
    improvements = [parse_conclusion(r).get("primary_metric_improvement", 0) for r in completed if parse_conclusion(r).get("primary_metric_improvement")]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Total Experiments</div><div class="metric-value">{len(server_results)}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Completed</div><div class="metric-value text-ok">{len(completed)}</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Failed</div><div class="metric-value text-error">{len(failed)}</div></div>', unsafe_allow_html=True)
    with c4:
        avg = np.mean(improvements) if improvements else 0
        st.markdown(f'<div class="metric-card"><div class="metric-label">Avg Improvement</div><div class="metric-value {"text-ok" if avg > 0 else "text-warn"}">{avg:+.1f}%</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Method breakdown for this server
    st.markdown('<div class="section-heading">METHOD BREAKDOWN</div>', unsafe_allow_html=True)
    for meth in METHODS:
        meth_results = [r for r in server_results if r.get("method") == meth]
        if not meth_results:
            continue
        meth_completed = [r for r in meth_results if r.get("status") == "completed"]
        meth_imp = [parse_conclusion(r).get("primary_metric_improvement", 0) for r in meth_completed if parse_conclusion(r).get("primary_metric_improvement")]
        avg_imp = np.mean(meth_imp) if meth_imp else 0

        # Metrics being measured
        metrics_info = METHOD_METRICS.get(meth, {})
        metrics_html = " | ".join(f'{k} <span style="color: var(--color-muted);">({w:.0%}, {d})</span>' for k, (w, d) in metrics_info.items())

        st.markdown(f'''<div class="experiment-card" style="border-left: 3px solid var(--color-purple);">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="color: var(--color-purple); font-weight: 700; font-size: 1.1em;">{METHOD_LABELS.get(meth, meth)}</span>
                <span style="color: {'#2ecc71' if avg_imp > 0 else '#f97316'}; font-weight: 700;">{avg_imp:+.1f}% avg</span>
            </div>
            <div style="color: var(--color-muted); font-size: 0.8em; margin-top: 5px;">
                {len(meth_completed)} completed, {len(meth_results) - len(meth_completed)} other
            </div>
            <div style="color: var(--color-cyan); font-size: 0.75em; margin-top: 8px;">
                Metrics: {metrics_html}
            </div>
        </div>''', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Results table
    st.markdown('<div class="section-heading">EXPERIMENT HISTORY</div>', unsafe_allow_html=True)
    render_results_compact(server_results)


# ═══════════════════════════════════════════════════════════════
# TAB 5: ACTIVITY LOG
# ═══════════════════════════════════════════════════════════════

def render_activity_tab(data: Dict):
    st.markdown('<div class="dashboard-title">ACTIVITY LOG</div>', unsafe_allow_html=True)
    st.markdown('<div class="dashboard-subtitle">Temporal Workflow Events \u2022 Raw Iteration Data \u2022 System Log</div>', unsafe_allow_html=True)

    results = data.get("results") or []
    status = data.get("status") or {}

    # Workflow info
    st.markdown('<div class="section-heading">TEMPORAL WORKFLOW</div>', unsafe_allow_html=True)

    wf_html = f'''<div style="background: rgba(0,0,0,0.3); border: 1px solid var(--nexus-border); border-radius: 6px; padding: 15px;">
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
            <div><span style="color: var(--color-muted); font-size: 0.75em;">WORKFLOW ID</span><br>
                <span style="color: var(--color-cyan);">{WORKFLOW_ID}</span></div>
            <div><span style="color: var(--color-muted); font-size: 0.75em;">TEMPORAL ADDRESS</span><br>
                <span style="color: var(--color-text);">{TEMPORAL_ADDRESS}</span></div>
            <div><span style="color: var(--color-muted); font-size: 0.75em;">NAMESPACE</span><br>
                <span style="color: var(--color-text);">{TEMPORAL_NAMESPACE}</span></div>
        </div>'''

    if status:
        wf_html += f'''<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-top: 15px;">
            <div><span style="color: var(--color-muted); font-size: 0.75em;">CYCLE</span><br>
                <span style="color: var(--nexus-primary); font-weight: 700;">{status.get('cycle_number', 0)}</span></div>
            <div><span style="color: var(--color-muted); font-size: 0.75em;">EXPERIMENTS THIS CYCLE</span><br>
                <span style="color: var(--color-text);">{status.get('experiments_completed', 0)}/{status.get('experiments_total', 0)}</span></div>
            <div><span style="color: var(--color-muted); font-size: 0.75em;">TOTAL EXPERIMENTS</span><br>
                <span style="color: var(--color-cyan);">{status.get('total_experiments_completed', 0)}</span></div>
            <div><span style="color: var(--color-muted); font-size: 0.75em;">TOTAL CYCLES</span><br>
                <span style="color: var(--color-text);">{status.get('total_cycles_completed', 0)}</span></div>
        </div>'''

    wf_html += "</div>"
    st.markdown(wf_html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Activity timeline
    st.markdown('<div class="section-heading">EXPERIMENT TIMELINE</div>', unsafe_allow_html=True)
    for r in results[:20]:
        created = r.get("created_at", "")[:19] or "--"
        strat = STRATEGY_SHORT.get(r.get("strategy", ""), "?")
        meth = METHOD_SHORT.get(r.get("method", ""), "?")
        srv = (r.get("server_hostname", "?") or "?").split(".")[0]
        s_status = r.get("status", "?")
        wt = r.get("wall_time_seconds", 0)
        error = r.get("error_message", "")
        conc = parse_conclusion(r)
        imp = conc.get("primary_metric_improvement", 0)

        icon_map = {"completed": "\u2705", "failed": "\u274c", "timeout": "\u23f0", "rolled_back": "\u21a9\ufe0f"}
        icon = icon_map.get(s_status, "\u2022")

        imp_text = f' <span style="color: #2ecc71;">+{imp:.1f}%</span>' if imp and imp > 0 else ""
        err_text = f' <span style="color: #ff5555; font-size: 0.8em;">{error[:60]}</span>' if error else ""

        st.markdown(f'''<div style="display: flex; gap: 12px; padding: 6px 0; border-bottom: 1px solid #111; font-size: 0.85em;">
            <span style="color: var(--color-muted); min-width: 140px;">{created}</span>
            <span style="min-width: 24px;">{icon}</span>
            <span style="color: var(--color-cyan); min-width: 70px;">{strat}</span>
            <span style="color: var(--color-purple); min-width: 70px;">{meth}</span>
            <span style="color: var(--nexus-primary); min-width: 100px;">{srv}</span>
            <span style="color: var(--color-text);">{wt//60}m{wt%60}s{imp_text}{err_text}</span>
        </div>''', unsafe_allow_html=True)

    if not results:
        st.markdown('<div style="color: var(--color-muted); padding: 20px; text-align: center;">No activity yet.</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Raw data export
    st.markdown('<div class="section-heading">RAW DATA</div>', unsafe_allow_html=True)
    if results:
        df = pd.DataFrame(results)
        cols = ["created_at", "strategy", "method", "server_hostname", "status", "wall_time_seconds"]
        available_cols = [c for c in cols if c in df.columns]
        st.dataframe(df[available_cols], use_container_width=True, height=300)

        csv = df.to_csv(index=False)
        st.download_button("Download CSV", csv, "erad_experiments.csv", "text/csv")


# ═══════════════════════════════════════════════════════════════
# TAB 6: WIKI
# ═══════════════════════════════════════════════════════════════

def render_wiki_tab():
    st.markdown('<div class="dashboard-title">ERAD WIKI</div>', unsafe_allow_html=True)
    st.markdown('<div class="dashboard-subtitle">System Guide \u2022 Strategy Reference \u2022 Method Reference \u2022 Glossary</div>', unsafe_allow_html=True)

    wiki_nav = st.radio("Navigate:", ["\U0001f4d6 ERAD Overview", "\U0001f3af Strategies", "\U0001f527 Methods", "\U0001f4dd Glossary", "\u2699\ufe0f How It Works"], horizontal=True, label_visibility="collapsed")
    st.markdown("<br>", unsafe_allow_html=True)

    if wiki_nav == "\U0001f4d6 ERAD Overview":
        st.markdown('''<div class="wiki-section"><h3>What is ERAD?</h3>
        <p style="color: var(--color-text); line-height: 1.8;">
            <strong>ERAD</strong> (Evaluate \u2013 Recommend \u2013 Adapt \u2013 Discover) is ZON Radiance's intelligent learning system for server optimization.
            It continuously runs experiments on live servers, testing different tuning configurations and learning which optimizations work best for each hardware profile.
        </p><br>
        <p style="color: var(--nexus-primary); font-style: italic; padding: 10px; background: rgba(0,255,65,0.05); border-radius: 4px;">
            "ERAD watches how your servers perform, tries small improvements, measures the results scientifically, and remembers what works \u2014 getting smarter over time."
        </p></div>''', unsafe_allow_html=True)

        st.markdown('''<div class="wiki-section"><h3>The ERAD Cycle</h3>
        <div class="code-block">
EVALUATE  \u2192  Classify server state (idle, light, moderate, heavy, burst)
RECOMMEND \u2192  Propose optimization policy from knowledge base
ADAPT     \u2192  Run live A/B experiment to validate improvement
DISCOVER  \u2192  Record results, update knowledge, share across fleet
        </div>
        <p style="color: var(--color-text); margin-top: 15px; line-height: 1.8;">
            Each cycle runs <strong>16 strategy\u00d7method combinations</strong> across all target servers
            (currently 32 experiments per cycle = 4 strategies \u00d7 4 methods \u00d7 2 servers).
            Results feed into the knowledge base, making each subsequent cycle smarter.
        </p></div>''', unsafe_allow_html=True)

        st.markdown('''<div class="wiki-section"><h3>System Architecture</h3>
        <table class="wiki-table">
            <tr><th>Component</th><th>Role</th><th>Description</th></tr>
            <tr><td><span class="glossary-term">Temporal Workflow</span></td><td>Orchestrator</td>
                <td>Durable workflow engine. Manages experiment lifecycle, survives restarts.</td></tr>
            <tr><td><span class="glossary-term">Experiment Executor</span></td><td>Runner</td>
                <td>Temporal activity that collects metrics, applies policies via MCP, measures results.</td></tr>
            <tr><td><span class="glossary-term">Genetic Optimizer</span></td><td>Config Evolver</td>
                <td>Evolves configuration parameters using genetic algorithms across generations.</td></tr>
            <tr><td><span class="glossary-term">SCBO Engine</span></td><td>Safe Optimizer</td>
                <td>Safe Contextual Bayesian Optimization \u2014 GP-backed acquisition with safety constraints.</td></tr>
            <tr><td><span class="glossary-term">Knowledge Base</span></td><td>Memory</td>
                <td>Stores experiment results, tracks best combos, enables cross-server learning.</td></tr>
            <tr><td><span class="glossary-term">MCP Probe</span></td><td>Eyes & Hands</td>
                <td>Agent on each server: collects metrics and applies tuning via system calls.</td></tr>
        </table></div>''', unsafe_allow_html=True)

    elif wiki_nav == "\U0001f3af Strategies":
        st.markdown('''<div class="wiki-section"><h3>Experiment Strategies</h3>
        <p style="color: var(--color-text); margin-bottom: 15px;">ERAD uses 4 strategies to explore the optimization space. Each trades off exploration vs. exploitation differently.</p>
        <table class="wiki-table">
            <tr><th>Strategy</th><th>Type</th><th>Description</th><th>Best For</th></tr>
            <tr><td><span class="glossary-term">Shadow Mode</span></td><td>Passive</td>
                <td>Observe-only. Collects metrics without applying any changes. Pure baseline.</td>
                <td>Initial data collection, safety verification</td></tr>
            <tr><td><span class="glossary-term">A/B Tester</span></td><td>Statistical</td>
                <td>Classic split test. Alternates baseline/treatment iterations, uses t-test + Cohen's d for significance.</td>
                <td>Rigorous comparison with statistical confidence</td></tr>
            <tr><td><span class="glossary-term">Thompson Bandit</span></td><td>Bayesian</td>
                <td>Multi-armed bandit using Thompson Sampling. Maintains Beta distributions per action, samples to select.</td>
                <td>Fast convergence when many options exist</td></tr>
            <tr><td><span class="glossary-term">Bayesian Opt</span></td><td>Model-Based</td>
                <td>Gaussian Process regression over the configuration space. Uses Expected Improvement (EI) acquisition function.</td>
                <td>Efficient optimization of continuous parameter spaces</td></tr>
        </table></div>''', unsafe_allow_html=True)

        # SCBO extension
        st.markdown('''<div class="wiki-section"><h3>SCBO \u2014 Safe Contextual Bayesian Optimization</h3>
        <p style="color: var(--color-text); line-height: 1.8;">
            Built on top of Bayesian Opt, the SCBO engine adds:
        </p>
        <ul style="color: var(--color-text); line-height: 2;">
            <li><strong>Context Vectors</strong> \u2014 5-dimensional: CPU pressure, memory pressure, IO pressure, time-of-day, workload volatility</li>
            <li><strong>Epistemic Tracking</strong> \u2014 Knows what it doesn't know; adds exploration bonus to under-sampled regions</li>
            <li><strong>Proactive Safety</strong> \u2014 GP-backed prediction of guardrail violations BEFORE applying actions</li>
            <li><strong>Adaptive Loop</strong> \u2014 Auto-tunes exploration/exploitation ratio and acquisition strategy based on convergence</li>
            <li><strong>Multi-Objective Scalarization</strong> \u2014 Weighted sum, Tchebycheff, or achievement scalarization for competing objectives</li>
            <li><strong>Transfer Learning</strong> \u2014 Reuses GP knowledge across similar hardware profiles</li>
        </ul></div>''', unsafe_allow_html=True)

    elif wiki_nav == "\U0001f527 Methods":
        st.markdown('''<div class="wiki-section"><h3>Optimization Methods</h3>
        <p style="color: var(--color-text); margin-bottom: 15px;">
            Each method targets a specific subsystem of the server. They apply real system-level changes via MCP probe tools.
        </p></div>''', unsafe_allow_html=True)

        for meth, desc in METHOD_DESC.items():
            label = METHOD_LABELS[meth]
            metrics = METHOD_METRICS.get(meth, {})
            metrics_rows = "".join(f'<tr><td><code>{k}</code></td><td>{w:.0%}</td><td>{d}imize</td></tr>' for k, (w, d) in metrics.items())

            st.markdown(f'''<div class="wiki-section"><h3>{label}</h3>
            <p style="color: var(--color-text); margin-bottom: 10px;">{desc}</p>
            <table class="wiki-table">
                <tr><th>Metric</th><th>Weight</th><th>Direction</th></tr>
                {metrics_rows}
            </table></div>''', unsafe_allow_html=True)

    elif wiki_nav == "\U0001f4dd Glossary":
        st.markdown('''<div class="wiki-section"><h3>Key Terms</h3>
        <table class="wiki-table">
            <tr><th>Term</th><th>Definition</th></tr>
            <tr><td><span class="glossary-term">ERAD</span></td><td>Evaluate-Recommend-Adapt-Discover. The 4-phase optimization learning loop.</td></tr>
            <tr><td><span class="glossary-term">Cycle</span></td><td>One complete pass through all 16 strategy\u00d7method combinations across all servers.</td></tr>
            <tr><td><span class="glossary-term">Experiment</span></td><td>A single run of one strategy + one method on one server. Multiple iterations inside.</td></tr>
            <tr><td><span class="glossary-term">Iteration</span></td><td>One baseline-treatment-measure loop within an experiment.</td></tr>
            <tr><td><span class="glossary-term">Fitness Score</span></td><td>Composite improvement metric. Weighted sum of per-method metrics.</td></tr>
            <tr><td><span class="glossary-term">Reward Signal</span></td><td>Per-method metric set used to evaluate if a policy change helped or hurt.</td></tr>
            <tr><td><span class="glossary-term">Policy</span></td><td>A set of system-level configuration changes (e.g., scheduler, swappiness, power limit).</td></tr>
            <tr><td><span class="glossary-term">MCP</span></td><td>Model Context Protocol. Standardized tool interface for probes to collect metrics and apply changes.</td></tr>
            <tr><td><span class="glossary-term">GP</span></td><td>Gaussian Process. Probabilistic model used by Bayesian Opt and SCBO.</td></tr>
            <tr><td><span class="glossary-term">EI</span></td><td>Expected Improvement. Acquisition function that balances exploration and exploitation.</td></tr>
            <tr><td><span class="glossary-term">Guardrail</span></td><td>Safety threshold. If a metric exceeds its guardrail, the action is rolled back.</td></tr>
            <tr><td><span class="glossary-term">Context Vector</span></td><td>5-dim feature: CPU/mem/IO pressure, time-of-day, volatility. Conditions GP predictions.</td></tr>
            <tr><td><span class="glossary-term">Cohen's d</span></td><td>Effect size measure. Used by A/B Tester to quantify how large the improvement is.</td></tr>
            <tr><td><span class="glossary-term">Thompson Sampling</span></td><td>Bayesian exploration strategy. Samples from posterior to select actions.</td></tr>
            <tr><td><span class="glossary-term">Temporal</span></td><td>Durable workflow engine. Ensures experiments survive crashes and restarts.</td></tr>
        </table></div>''', unsafe_allow_html=True)

    elif wiki_nav == "\u2699\ufe0f How It Works":
        st.markdown('''<div class="wiki-section"><h3>Experiment Lifecycle</h3>
        <div class="code-block">
1. ERAD workflow starts a new experiment:
   \u2192 Strategy = bayesian_opt, Method = io_scheduler, Server = metal-erad-001

2. Experiment Executor (Temporal Activity) runs:
   a. Connect to server via MCP probe
   b. Collect BASELINE metrics (method-specific):
      - iops_total, avg_read_latency_ms, throughput_read_mbps, power_watts
   c. Strategy selects ACTION (e.g., set scheduler=kyber, queue_depth=256)
   d. Apply action via MCP probe tools
   e. Wait stabilization period (30s)
   f. Collect TREATMENT metrics
   g. Compute composite reward using method weights
   h. Strategy observes result, updates its model
   i. Repeat for N iterations (typically 8-14)

3. After all iterations:
   a. Analyze: t-test for significance, compute improvement %
   b. Pick winner (baseline or best treatment)
   c. If treatment won: deploy as permanent policy
   d. Record everything to knowledge base

4. Move to next strategy\u00d7method\u00d7server combo
        </div></div>''', unsafe_allow_html=True)

        st.markdown('''<div class="wiki-section"><h3>Reading the Dashboard</h3>
        <table class="wiki-table">
            <tr><th>Panel</th><th>What It Shows</th><th>What to Look For</th></tr>
            <tr><td>Overview</td><td>Live experiment, cycle progress, system health</td><td>Engine state, current experiment running</td></tr>
            <tr><td>Experiments</td><td>Full history with policies deployed</td><td>Which combos produce positive improvements</td></tr>
            <tr><td>Analysis</td><td>Trend charts, convergence, comparisons</td><td>Is the system converging? Which methods work best?</td></tr>
            <tr><td>Servers</td><td>Per-server view</td><td>Does a specific server respond better to certain methods?</td></tr>
            <tr><td>Activity Log</td><td>Temporal events, raw data</td><td>Timeline of all actions taken</td></tr>
        </table></div>''', unsafe_allow_html=True)

        st.markdown('''<div class="wiki-section"><h3>Safety Guarantees</h3>
        <ul style="color: var(--color-text); line-height: 2;">
            <li>\u2705 <strong>Guardrails</strong> \u2014 Each method has max/min thresholds. Violations trigger automatic rollback.</li>
            <li>\u2705 <strong>Proactive Safety</strong> \u2014 GP predicts if an action WILL violate a guardrail before applying it.</li>
            <li>\u2705 <strong>Shadow Mode</strong> \u2014 First strategy in each cycle is observe-only. No changes applied.</li>
            <li>\u2705 <strong>Temporal Durability</strong> \u2014 If the worker crashes mid-experiment, it resumes from the last checkpoint.</li>
            <li>\u2705 <strong>Rate Limiting</strong> \u2014 Max 10 concurrent workflows, max 5 child workflows, 10 req/min.</li>
            <li>\u2705 <strong>Rollback on Failure</strong> \u2014 Any failed experiment reverts all system changes.</li>
        </ul></div>''', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="ZON ERAD Dashboard",
        page_icon="\U0001f9ea",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CONSTRUCT_CSS, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown('<div class="sidebar-title">\U0001f9ea ERAD ENGINE</div>', unsafe_allow_html=True)
        tab = st.radio("Navigation", [
            "\U0001f3e0 Overview",
            "\U0001f4ca Experiments",
            "\U0001f4c8 Analysis",
            "\U0001f5a5\ufe0f Servers",
            "\U0001f4cb Activity Log",
            "\U0001f4da Wiki",
        ], label_visibility="collapsed")

        st.markdown("---")

        # Connection info
        fetched = datetime.now().strftime("%H:%M:%S")
        st.markdown(f'''<div style="color: var(--color-muted); font-size: 0.8em; padding: 10px;">
            <strong>Refresh:</strong> {REFRESH_INTERVAL}s<br>
            <strong>Source:</strong> bizon1 Supabase + Temporal<br>
            <strong>Temporal:</strong> {TEMPORAL_ADDRESS}<br>
            <strong>Theme:</strong> Construct<br>
            <strong>Updated:</strong> {fetched}
        </div>''', unsafe_allow_html=True)

    # Load data
    data = load_all_data()

    # Route to tab
    if tab == "\U0001f3e0 Overview":
        render_overview_tab(data)
    elif tab == "\U0001f4ca Experiments":
        render_experiments_tab(data)
    elif tab == "\U0001f4c8 Analysis":
        render_analysis_tab(data)
    elif tab == "\U0001f5a5\ufe0f Servers":
        render_servers_tab(data)
    elif tab == "\U0001f4cb Activity Log":
        render_activity_tab(data)
    elif tab == "\U0001f4da Wiki":
        render_wiki_tab()

    # Auto-refresh (skip for wiki)
    if tab != "\U0001f4da Wiki":
        time.sleep(REFRESH_INTERVAL)
        st.rerun()


if __name__ == "__main__":
    main()
