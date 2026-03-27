"""
policy_tester_page.py — Policy Tester Dashboard Page (v2)

Reads from erad.policy_test_cycles and erad.policy_test_results to show
whether each policy actually affects server metrics.

v2 features:
  - Global progress bar with live ticker for running cycles
  - Before/During/After 3-phase metric visualization
  - Proper effect heatmap with formatted percentages and multi-column layout
  - Expanded summary with workload groups, wall time, timeline
  - Post-cycle diagnostic summary with ranked action items
  - Full policy health diagnostic table
  - Graceful v1/v2 column fallback via .get() everywhere

Integration into app.py:
───────────────────────
1. Add import:
       from policy_tester_page import render_policy_tester_tab

2. Add sidebar nav entry:
       "🔬 Policy Tester"

3. Add routing:
       elif tab == "🔬 Policy Tester":
           render_policy_tester_tab(data)
"""

import streamlit as st
import httpx
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import plotly.graph_objects as go


# ═══════════════════════════════════════════════════════════════
# Supabase Config (mirrors app.py)
# ═══════════════════════════════════════════════════════════════

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "http://127.0.0.1:31443")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")
HEADERS = {
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "apikey": SUPABASE_KEY,
    "Accept-Profile": "erad",
    "Content-Profile": "erad",
}

METHOD_LABELS = {
    "power_state": "Power State",
    "io_scheduler": "I/O Scheduler",
    "memory_manager": "Memory Manager",
    "forecaster": "Forecaster",
}

SEVERITY_BADGES = {
    "critical": ("🔴", "#ff5555"),
    "high": ("🟠", "#f97316"),
    "medium": ("🟡", "#f1c40f"),
    "low": ("🟢", "#2ecc71"),
}

VERDICT_ORDER = {
    "BROKEN": 0,
    "HARMFUL": 1,
    "DEAD WEIGHT": 2,
    "MARGINAL": 3,
    "EFFECTIVE": 4,
}


# ═══════════════════════════════════════════════════════════════
# Data Loading
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def _load_policy_test_data() -> Dict[str, Any]:
    """Load cycles and results from Supabase policy test tables."""
    try:
        with httpx.Client(timeout=10.0) as c:
            cycles_resp = c.get(
                f"{SUPABASE_URL}/rest/v1/policy_test_cycles",
                headers=HEADERS,
                params={"select": "*", "order": "started_at.desc", "limit": "50"},
            )
            cycles = cycles_resp.json() if cycles_resp.status_code == 200 else []

            results_resp = c.get(
                f"{SUPABASE_URL}/rest/v1/policy_test_results",
                headers=HEADERS,
                params={"select": "*", "order": "created_at.desc", "limit": "500"},
            )
            results = results_resp.json() if results_resp.status_code == 200 else []
    except Exception:
        cycles, results = [], []

    return {"cycles": cycles, "results": results}


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _classify_color(pct_change: float) -> str:
    """Return CSS color based on magnitude of change."""
    if pct_change >= 5.0:
        return "#2ecc71"
    if pct_change >= 1.0:
        return "#00ff41"
    if pct_change >= -1.0:
        return "#555"
    if pct_change >= -5.0:
        return "#f97316"
    return "#ff5555"


def _delta_arrow_color(pct: float) -> Tuple[str, str]:
    """Return (arrow, color) for a delta percentage."""
    if pct > 0.5:
        return "▲", "#2ecc71"
    if pct < -0.5:
        return "▼", "#ff5555"
    return "—", "#555"


def _safe_json(val: Any) -> Any:
    """Parse JSON string if needed, return dict/list."""
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return {}
    return val or {}


def _fmt_pct(val: Optional[float]) -> str:
    """Format percentage change with sign."""
    if val is None:
        return "--"
    return f"{val:+.1f}%"


def _fmt_pct_padded(val: Optional[float]) -> str:
    """Format as +07.08% style (zero-padded, 2 decimal)."""
    if val is None:
        return "  --.--% "
    sign = "+" if val >= 0 else "-"
    return f"{sign}{abs(val):05.2f}%"


def _fmt_duration(seconds: Optional[float]) -> str:
    """Format seconds into human-readable duration."""
    if not seconds:
        return "--"
    s = float(seconds)
    if s >= 3600:
        return f"{s / 3600:.1f}h"
    if s >= 60:
        return f"{s / 60:.0f}m"
    return f"{s:.0f}s"


def _fmt_duration_hms(seconds: Optional[float]) -> str:
    """Format seconds as HH:MM:SS."""
    if not seconds:
        return "00:00:00"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _status_class(status: str) -> str:
    """Map status string to CSS badge class."""
    return {
        "completed": "status-completed",
        "running": "status-running",
        "failed": "status-failed",
        "in_progress": "status-running",
        "pending": "status-cooldown",
    }.get(status.lower(), "status-cooldown")


def _action_label(test: Dict) -> str:
    """Build a compact label like 'set_io_scheduler(scheduler=kyber)'."""
    label = test.get("action_label")
    if label:
        return label
    action = test.get("action_name", test.get("action", "unknown"))
    params = _safe_json(test.get("action_params", test.get("params", {})))
    if isinstance(params, dict) and params:
        param_str = ", ".join(f"{k}={v}" for k, v in list(params.items())[:3])
        return f"{action}({param_str})"
    return action


def _rgb_from_hex(hex_color: str) -> str:
    """Convert #RRGGBB or #RGB to 'R, G, B' string for rgba()."""
    h = hex_color.lstrip("#") if hex_color else ""
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    if len(h) < 6:
        return "85, 85, 85"
    try:
        return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"
    except ValueError:
        return "85, 85, 85"


def _fmt_metric_val(key: str, val: float) -> str:
    """Format a metric value with appropriate units."""
    if "latency" in key or "_ms" in key:
        return f"{val:.2f}ms"
    if "watts" in key:
        return f"{val:.0f}W"
    if "mbps" in key or "throughput" in key:
        return f"{val:.0f}MB/s"
    if "ratio" in key or "percent" in key or "pct" in key:
        return f"{val:.1f}%"
    if val >= 10000:
        return f"{val:,.0f}"
    if val >= 100:
        return f"{val:.0f}"
    return f"{val:.2f}"


def _extract_metric_means(raw: Any) -> Dict[str, float]:
    """Extract flat {metric_name: mean_value} from baseline/treatment JSONB."""
    parsed = _safe_json(raw)
    if not isinstance(parsed, dict):
        return {}
    source = parsed.get("measurements", parsed)
    if not isinstance(source, dict):
        return {}
    out: Dict[str, float] = {}
    for mkey, mdata in source.items():
        if isinstance(mdata, dict) and "mean" in mdata:
            try:
                out[mkey] = float(mdata["mean"])
            except (ValueError, TypeError):
                pass
        elif isinstance(mdata, (int, float)):
            out[mkey] = float(mdata)
    return out


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    """Parse ISO timestamp string to datetime (UTC)."""
    if not ts:
        return None
    try:
        cleaned = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        return None


def _now_utc() -> datetime:
    """Current UTC time."""
    return datetime.now(timezone.utc)


def _compute_primary_pct(test: Dict) -> Optional[float]:
    """Get primary metric pct change — prefer v2 column, else compute."""
    v2_val = test.get("primary_metric_pct")
    if v2_val is not None:
        try:
            return float(v2_val)
        except (ValueError, TypeError):
            pass
    deltas = _safe_json(test.get("metric_deltas", "[]"))
    if isinstance(deltas, list) and deltas:
        max_d = max(deltas, key=lambda d: abs(d.get("pct_change", 0)))
        return max_d.get("pct_change")
    return None


def _compute_total_effect_pct(test: Dict) -> Optional[float]:
    """Get total effect pct — prefer v2 column, else use primary."""
    v2_val = test.get("total_effect_pct")
    if v2_val is not None:
        try:
            return float(v2_val)
        except (ValueError, TypeError):
            pass
    return _compute_primary_pct(test)


def _compute_effect_direction(test: Dict) -> str:
    """Get effect direction — prefer v2 column, else infer."""
    v2_val = test.get("effect_direction")
    if v2_val:
        return str(v2_val).lower()
    pct = _compute_primary_pct(test)
    if pct is None:
        return "neutral"
    if pct > 0.5:
        return "better"
    if pct < -0.5:
        return "worse"
    return "neutral"


def _compute_verdict(test: Dict) -> Tuple[str, str, str]:
    """Compute (verdict_label, emoji, color) for a test result."""
    deploy_ok = test.get("deploy_success")
    if deploy_ok is False:
        return "BROKEN", "⚠️", "#ff5555"

    effect = test.get("effect_detected")
    direction = _compute_effect_direction(test)
    pct = _compute_primary_pct(test)

    if not effect and effect is not None:
        return "DEAD WEIGHT", "💤", "#555"

    if effect and direction == "worse":
        return "HARMFUL", "🔴", "#ff5555"

    if effect and pct is not None and abs(pct) < 1.0:
        return "MARGINAL", "🟡", "#f1c40f"

    if effect:
        return "EFFECTIVE", "✅", "#2ecc71"

    # Pending / unknown
    return "PENDING", "⏳", "#f1c40f"


# ═══════════════════════════════════════════════════════════════
# CSS for Policy Tester v2 (injected once)
# ═══════════════════════════════════════════════════════════════

_PT_CSS = """
<style>
@keyframes pulse-border {
    0%, 100% { border-color: rgba(0, 255, 65, 0.6); box-shadow: 0 0 8px rgba(0, 255, 65, 0.2); }
    50% { border-color: rgba(139, 233, 253, 0.8); box-shadow: 0 0 16px rgba(139, 233, 253, 0.3); }
}
.pt-live-bar {
    background: rgba(0, 255, 65, 0.04);
    border: 2px solid rgba(0, 255, 65, 0.6);
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 20px;
    animation: pulse-border 2s ease-in-out infinite;
}
.pt-live-title {
    color: #00ff41;
    font-size: 1.1em;
    font-weight: 700;
    margin-bottom: 6px;
}
.pt-live-detail {
    color: #c0c0c0;
    font-size: 0.85em;
    margin-bottom: 10px;
}
.pt-live-elapsed {
    color: #8be9fd;
    font-weight: 600;
}
.pt-progress-outer {
    background: rgba(0, 0, 0, 0.5);
    border-radius: 6px;
    height: 22px;
    overflow: hidden;
    border: 1px solid rgba(0, 255, 65, 0.15);
}
.pt-progress-inner {
    height: 100%;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75em;
    font-weight: 700;
    color: #0a0f0a;
    transition: width 0.5s ease;
}
.pt-phase-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82em;
    margin: 8px 0;
}
.pt-phase-table th {
    color: #555;
    font-size: 0.75em;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 6px 8px;
    border-bottom: 1px solid #222;
    text-align: center;
}
.pt-phase-table th:first-child {
    text-align: left;
}
.pt-phase-table td {
    padding: 5px 8px;
    border-bottom: 1px solid #111;
    text-align: center;
    color: #c0c0c0;
}
.pt-phase-table td:first-child {
    text-align: left;
    color: #8be9fd;
}
.pt-action-card {
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(0, 255, 65, 0.12);
    border-left: 3px solid #555;
    border-radius: 6px;
    padding: 12px 16px;
    margin: 6px 0;
}
.pt-action-card.critical { border-left-color: #ff5555; }
.pt-action-card.high { border-left-color: #f97316; }
.pt-action-card.medium { border-left-color: #f1c40f; }
.pt-action-card.low { border-left-color: #2ecc71; }
.pt-severity-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 0.7em;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.pt-timeline-bar {
    display: flex;
    align-items: center;
    gap: 2px;
    margin: 4px 0;
    height: 28px;
}
.pt-timeline-segment {
    height: 100%;
    border-radius: 3px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.65em;
    font-weight: 600;
    color: #0a0f0a;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    padding: 0 4px;
}
.pt-health-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82em;
}
.pt-health-table th {
    color: #555;
    font-size: 0.72em;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 8px 10px;
    border-bottom: 1px solid #333;
    text-align: left;
}
.pt-health-table td {
    padding: 6px 10px;
    border-bottom: 1px solid #111;
    color: #c0c0c0;
}
.pt-health-table tr:hover {
    background: rgba(0, 255, 65, 0.03);
}
.pt-method-subtotal {
    background: rgba(0, 255, 65, 0.06);
    font-weight: 600;
}
.pt-method-subtotal td {
    color: #8be9fd;
    border-bottom: 2px solid #222;
    padding: 8px 10px;
}
</style>
"""


# ═══════════════════════════════════════════════════════════════
# Section 1: Global Progress Bar (running cycles)
# ═══════════════════════════════════════════════════════════════

def _render_global_progress(cycles: List[Dict], results: List[Dict]) -> None:
    """If any cycle is running, show a prominent live progress bar at the top."""
    running = [c for c in cycles if c.get("status", "").lower() in ("running", "in_progress")]
    if not running:
        return

    cycle = running[0]
    cycle_id = cycle.get("id")
    cycle_results = [r for r in results if r.get("cycle_id") == cycle_id]
    completed_results = [
        r for r in cycle_results
        if r.get("status", "").lower() in ("completed", "effect_detected", "no_effect", "deploy_failed")
    ]

    total_tests = cycle.get("total_tests") or len(cycle_results) or 1
    tests_done = cycle.get("tests_completed") or len(completed_results)
    pct = min(tests_done / max(total_tests, 1) * 100, 100)

    # v2 workload group info
    wg_total = cycle.get("workload_groups_total")
    wg_completed = cycle.get("workload_groups_completed")
    if wg_total is None:
        # Fallback: count distinct workload_group_id from results
        groups = {r.get("workload_group_id") for r in cycle_results if r.get("workload_group_id")}
        done_groups = {
            r.get("workload_group_id") for r in completed_results if r.get("workload_group_id")
        }
        if groups:
            wg_total = len(groups)
            wg_completed = len(done_groups)

    # Current group info — find the latest in-progress result
    current_server = ""
    current_method = ""
    in_progress = [r for r in cycle_results if r.get("status", "").lower() in ("running", "in_progress")]
    if in_progress:
        latest = in_progress[-1]
        current_server = (latest.get("server_hostname", "") or "").split(".")[0]
        current_method = latest.get("method", "")
    elif cycle_results:
        latest = cycle_results[0]  # most recent by created_at desc
        current_server = (latest.get("server_hostname", "") or "").split(".")[0]
        current_method = latest.get("method", "")

    # Elapsed time
    started = _parse_iso(cycle.get("started_at"))
    elapsed_str = ""
    if started:
        elapsed_s = (_now_utc() - started).total_seconds()
        elapsed_str = _fmt_duration_hms(max(elapsed_s, 0))

    # Build detail line
    detail_parts = [f"{tests_done}/{total_tests} tests"]
    if wg_total is not None and wg_completed is not None:
        method_label = METHOD_LABELS.get(current_method, current_method)
        detail_parts.append(f"Group {wg_completed + 1}/{wg_total}")
        if method_label:
            detail_parts[-1] += f" ({method_label})"
    if current_server:
        detail_parts.append(current_server)
    detail_line = " · ".join(detail_parts)

    bar_color = "linear-gradient(90deg, #003b00, #00ff41)"

    st.markdown(
        f'<div class="pt-live-bar">'
        f'<div class="pt-live-title">POLICY TEST RUNNING</div>'
        f'<div class="pt-live-detail">'
        f'{detail_line}'
        f'{f" &nbsp;·&nbsp; <span class=pt-live-elapsed>⏱ {elapsed_str}</span>" if elapsed_str else ""}'
        f'</div>'
        f'<div class="pt-progress-outer">'
        f'<div class="pt-progress-inner" style="width: {max(pct, 3)}%; background: {bar_color};">'
        f'{pct:.0f}%</div></div></div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════
# Section 2: Cycle Selector + Status
# ═══════════════════════════════════════════════════════════════

def _render_cycle_status(cycles: List[Dict], results: List[Dict]) -> Optional[Dict]:
    """Render cycle status bar and return the selected cycle."""
    st.markdown(
        '<div class="dashboard-title">POLICY TESTER</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="dashboard-subtitle">'
        "Verify each policy actually affects server metrics"
        "</div>",
        unsafe_allow_html=True,
    )

    if not cycles:
        st.markdown(
            '<div class="experiment-card" style="border-left: 3px solid #f1c40f;">'
            '<span style="color: #f1c40f; font-size: 1.1em; font-weight: 700;">'
            "NO POLICY TEST CYCLES</span><br>"
            '<span style="color: var(--color-muted); font-size: 0.9em;">'
            "No policy test cycles yet. Start one from the ERAD CLI."
            "</span></div>",
            unsafe_allow_html=True,
        )
        return None

    if len(cycles) > 1:
        cycle_options = {
            f"Cycle #{c.get('cycle_number', i + 1)} — {c.get('status', '?').upper()} — "
            f"{(c.get('started_at', '')[:10])}": c
            for i, c in enumerate(cycles)
        }
        selected_label = st.selectbox(
            "Select Cycle",
            list(cycle_options.keys()),
            label_visibility="collapsed",
        )
        cycle = cycle_options[selected_label]
    else:
        cycle = cycles[0]

    cycle_num = cycle.get("cycle_number", 1)
    cycle_status = cycle.get("status", "unknown")
    cycle_id = cycle.get("id")

    # Duration: prefer v2 total_wall_time_seconds, else compute
    duration_s = cycle.get("total_wall_time_seconds")
    if duration_s is None:
        started = _parse_iso(cycle.get("started_at"))
        ended = _parse_iso(cycle.get("completed_at"))
        if started and ended:
            duration_s = (ended - started).total_seconds()
        else:
            duration_s = cycle.get("duration_seconds", 0)
    duration_str = _fmt_duration(duration_s)

    cycle_results = [r for r in results if r.get("cycle_id") == cycle_id]
    total_tests = cycle.get("total_tests", len(cycle_results))
    completed_tests = len([
        r for r in cycle_results
        if r.get("status", "").lower() in ("completed", "effect_detected", "no_effect", "deploy_failed")
    ])
    servers = sorted({
        (r.get("server_hostname", "") or "").split(".")[0]
        for r in cycle_results if r.get("server_hostname")
    })
    pct = (completed_tests / total_tests * 100) if total_tests > 0 else 0

    status_cls = _status_class(cycle_status)
    bar_color = "#00ff41" if cycle_status.lower() == "completed" else "#8be9fd"

    st.markdown(
        f'<div class="experiment-card" style="border-left: 3px solid {bar_color};">'
        f'<div style="display: flex; justify-content: space-between; align-items: center;">'
        f'<span style="color: var(--nexus-primary); font-size: 1.2em; font-weight: 700;">'
        f"CYCLE #{cycle_num}</span>"
        f'<span class="status-badge {status_cls}">{cycle_status.upper()}</span>'
        f"</div>"
        f'<div style="color: var(--color-text); font-size: 0.9em; margin-top: 8px;">'
        f"{completed_tests}/{total_tests} tests"
        f'{f" across {len(servers)} server" + ("s" if len(servers) != 1 else "") if servers else ""}'
        f" &nbsp;·&nbsp; Duration: {duration_str}"
        f"</div>"
        f'<div style="margin-top: 10px;">'
        f'<div class="progress-bar-outer">'
        f'<div class="progress-bar-inner" style="width: {max(pct, 2)}%; '
        f'background: linear-gradient(90deg, #003b00, {bar_color});">'
        f"{pct:.0f}%</div></div></div></div>",
        unsafe_allow_html=True,
    )

    return cycle


# ═══════════════════════════════════════════════════════════════
# Section 3: Expanded Summary Metrics (3 rows)
# ═══════════════════════════════════════════════════════════════

def _metric_card_html(label: str, value: str, color: str = "var(--nexus-primary)") -> str:
    """Generate HTML for a single metric card."""
    return (
        f'<div class="metric-card">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value" style="color: {color};">{value}</div></div>'
    )


def _render_summary_metrics(cycle: Dict, cycle_results: List[Dict]) -> None:
    """Render expanded 3-row summary metrics."""
    st.markdown(
        '<div class="section-heading">SUMMARY</div>',
        unsafe_allow_html=True,
    )

    total = len(cycle_results)
    effect_detected = len([
        r for r in cycle_results
        if r.get("effect_detected") or r.get("status", "").lower() == "effect_detected"
    ])
    no_effect = len([
        r for r in cycle_results
        if r.get("status", "").lower() == "no_effect"
        or (r.get("effect_detected") is False and r.get("deploy_success") is not False)
    ])
    deploy_failed = len([
        r for r in cycle_results
        if r.get("deploy_success") is False or r.get("status", "").lower() == "deploy_failed"
    ])

    # Row 1: Core counts
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(_metric_card_html("Tests Run", str(total)), unsafe_allow_html=True)
    with c2:
        st.markdown(
            _metric_card_html("Effect Detected", str(effect_detected), "#2ecc71"),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            _metric_card_html("No Effect", str(no_effect), "#555"),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            _metric_card_html("Deploy Failed", str(deploy_failed), "#ff5555"),
            unsafe_allow_html=True,
        )

    # Row 2: v2 operational metrics
    # Workload groups
    wg_total = cycle.get("workload_groups_total")
    if wg_total is None:
        groups = {r.get("workload_group_id") for r in cycle_results if r.get("workload_group_id")}
        wg_total = len(groups) if groups else "--"
    wg_str = str(wg_total)

    # Total wall time
    wall_s = cycle.get("total_wall_time_seconds")
    if wall_s is None:
        started = _parse_iso(cycle.get("started_at"))
        ended = _parse_iso(cycle.get("completed_at"))
        if started and ended:
            wall_s = (ended - started).total_seconds()
    wall_str = _fmt_duration(wall_s) if wall_s else "--"

    # Avg test duration
    durations: List[float] = [float(r["wall_time_seconds"]) for r in cycle_results if r.get("wall_time_seconds") is not None]
    avg_dur = sum(durations) / len(durations) if durations else None
    avg_dur_str = _fmt_duration(avg_dur) if avg_dur else "--"

    # Measurement window
    meas_dur = cycle.get("measurement_duration", "60s")
    meas_str = str(meas_dur) if meas_dur else "60s"

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.markdown(
            _metric_card_html("Workload Groups", wg_str, "#8be9fd"),
            unsafe_allow_html=True,
        )
    with c6:
        st.markdown(
            _metric_card_html("Total Wall Time", wall_str, "#8be9fd"),
            unsafe_allow_html=True,
        )
    with c7:
        st.markdown(
            _metric_card_html("Avg Test Duration", avg_dur_str, "#8be9fd"),
            unsafe_allow_html=True,
        )
    with c8:
        st.markdown(
            _metric_card_html("Measurement Window", meas_str, "#8be9fd"),
            unsafe_allow_html=True,
        )

    # Row 3: Workload Timeline
    _render_workload_timeline(cycle, cycle_results)


def _render_workload_timeline(cycle: Dict, cycle_results: List[Dict]) -> None:
    """Render horizontal workload timeline if data available."""
    timeline = _safe_json(cycle.get("workload_timeline", "[]"))

    if isinstance(timeline, list) and timeline:
        # v2 path: render from workload_timeline JSONB
        st.markdown(
            '<div style="margin-top: 12px; padding: 12px; background: rgba(0,0,0,0.3); '
            'border: 1px solid rgba(0,255,65,0.12); border-radius: 6px;">'
            '<div style="color: #555; font-size: 0.72em; text-transform: uppercase; '
            'letter-spacing: 0.05em; margin-bottom: 8px;">Workload Timeline</div>',
            unsafe_allow_html=True,
        )

        # Calculate total span for proportional widths
        total_span = 0
        for entry in timeline:
            tests = entry.get("test_count", entry.get("tests", 1))
            total_span += max(tests, 1)

        colors = {
            "power_state": "#2ecc71",
            "io_scheduler": "#8be9fd",
            "memory_manager": "#bd93f9",
            "forecaster": "#f1c40f",
        }

        segments_html = ""
        for entry in timeline:
            method = entry.get("method", "unknown")
            tests = entry.get("test_count", entry.get("tests", 1))
            width_pct = max(tests, 1) / max(total_span, 1) * 100
            color = colors.get(method, "#555")
            label = METHOD_LABELS.get(method, method)
            segments_html += (
                f'<div class="pt-timeline-segment" style="width: {width_pct}%; '
                f'background: {color};" title="{label}: {tests} tests">'
                f'{str(label)[:6]} ({tests})</div>'
            )

        st.markdown(
            f'<div class="pt-timeline-bar">{segments_html}</div></div>',
            unsafe_allow_html=True,
        )
    else:
        # Fallback: group results by method and show breakdown
        method_groups: Dict[str, List[Dict]] = {}
        for r in cycle_results:
            m = r.get("method", "unknown")
            method_groups.setdefault(m, []).append(r)

        if len(method_groups) > 1:
            st.markdown(
                '<div style="margin-top: 12px; padding: 12px; background: rgba(0,0,0,0.3); '
                'border: 1px solid rgba(0,255,65,0.12); border-radius: 6px;">'
                '<div style="color: #555; font-size: 0.72em; text-transform: uppercase; '
                'letter-spacing: 0.05em; margin-bottom: 8px;">Method Breakdown</div>',
                unsafe_allow_html=True,
            )

            colors = {
                "power_state": "#2ecc71",
                "io_scheduler": "#8be9fd",
                "memory_manager": "#bd93f9",
                "forecaster": "#f1c40f",
            }
            total_tests = max(len(cycle_results), 1)
            segments_html = ""
            for method in sorted(method_groups.keys()):
                tests = method_groups[method]
                width_pct = len(tests) / total_tests * 100
                color = colors.get(method, "#555")
                label = METHOD_LABELS.get(method, method)
                segments_html += (
                    f'<div class="pt-timeline-segment" style="width: {width_pct}%; '
                    f'background: {color};" title="{label}: {len(tests)} tests">'
                    f'{label[:6]} ({len(tests)})</div>'
                )

            st.markdown(
                f'<div class="pt-timeline-bar">{segments_html}</div></div>',
                unsafe_allow_html=True,
            )


# ═══════════════════════════════════════════════════════════════
# Section 4: Post-Cycle Diagnostic Summary + Action Items
# ═══════════════════════════════════════════════════════════════

def _render_diagnostic_summary(cycle: Dict, cycle_results: List[Dict]) -> None:
    """Render diagnostic summary and ranked action items for completed cycles."""
    cycle_status = cycle.get("status", "").lower()
    if cycle_status not in ("completed", "failed"):
        return

    st.markdown(
        '<div class="section-heading">DIAGNOSTIC SUMMARY</div>',
        unsafe_allow_html=True,
    )

    # Diagnostic text (v2)
    diag_text = cycle.get("diagnostic_text")
    if diag_text:
        st.markdown(
            f'<div class="experiment-card" style="border-left: 3px solid #8be9fd;">'
            f'<div style="color: #8be9fd; font-size: 0.8em; font-weight: 600; '
            f'margin-bottom: 8px;">CYCLE ANALYSIS</div>'
            f'<div style="color: var(--color-text); font-size: 0.88em; line-height: 1.7; '
            f'white-space: pre-wrap;">{diag_text}</div></div>',
            unsafe_allow_html=True,
        )

    # Action items
    action_items = _safe_json(cycle.get("action_items", "[]"))
    if isinstance(action_items, list) and action_items:
        _render_action_items_from_db(action_items)
    else:
        _render_generated_action_items(cycle_results)


def _render_action_items_from_db(items: List[Dict]) -> None:
    """Render action items from the v2 action_items JSONB column."""
    sorted_items = sorted(items, key=lambda x: x.get("priority", 99))

    st.markdown(
        '<div style="color: #00ff41; font-size: 0.9em; font-weight: 600; '
        'margin: 16px 0 8px 0;">ACTION ITEMS</div>',
        unsafe_allow_html=True,
    )

    for item in sorted_items:
        severity = str(item.get("severity", "medium")).lower()
        emoji, color = SEVERITY_BADGES.get(severity, ("🟡", "#f1c40f"))
        verb = item.get("action_verb", "REVIEW")
        policy = item.get("policy_name", "unknown")
        method = item.get("method", "")
        reason = item.get("reason", "")
        method_label = METHOD_LABELS.get(method, method)
        css_class = severity if severity in ("critical", "high", "medium", "low") else "medium"

        st.markdown(
            f'<div class="pt-action-card {css_class}">'
            f'<span class="pt-severity-badge" style="background: rgba({_rgb_from_hex(color)}, 0.2); '
            f'color: {color}; border: 1px solid {color};">{emoji} {severity.upper()}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="color: var(--color-text); font-size: 0.9em;">'
            f'<strong style="color: #00ff41;">{verb.upper()}</strong> '
            f'{policy}'
            f'{f" ({method_label})" if method_label else ""}'
            f'{f" — {reason}" if reason else ""}'
            f'</span></div>',
            unsafe_allow_html=True,
        )


def _render_generated_action_items(cycle_results: List[Dict]) -> None:
    """Generate basic diagnostic action items from results data."""
    if not cycle_results:
        return

    items: List[Tuple[int, str, str, str, str]] = []  # (priority, severity, emoji, text, detail)

    # 1. Deploy failures by method
    deploy_fails: Dict[str, int] = {}
    for r in cycle_results:
        if r.get("deploy_success") is False or r.get("status", "").lower() == "deploy_failed":
            m = r.get("method", "unknown")
            deploy_fails[m] = deploy_fails.get(m, 0) + 1
    for method, count in deploy_fails.items():
        label = METHOD_LABELS.get(method, method)
        items.append((
            1, "critical", "🔴",
            f"<strong>FIX</strong> {count} policies in {label} failed to deploy",
            "Check MCP probe connectivity and policy parameter validity",
        ))

    # 2. Wrong direction (harmful)
    harmful: Dict[str, int] = {}
    for r in cycle_results:
        direction = _compute_effect_direction(r)
        if direction == "worse" and r.get("effect_detected"):
            m = r.get("method", "unknown")
            harmful[m] = harmful.get(m, 0) + 1
    for method, count in harmful.items():
        label = METHOD_LABELS.get(method, method)
        items.append((
            2, "high", "🟠",
            f"<strong>REVIEW</strong> {count} policies in {label} degraded performance",
            "Review parameter ranges and consider narrowing bounds",
        ))

    # 3. No effect (dead weight)
    no_effect: Dict[str, int] = {}
    for r in cycle_results:
        if (r.get("status", "").lower() == "no_effect"
                or (r.get("effect_detected") is False and r.get("deploy_success") is not False)):
            m = r.get("method", "unknown")
            no_effect[m] = no_effect.get(m, 0) + 1
    for method, count in no_effect.items():
        label = METHOD_LABELS.get(method, method)
        items.append((
            3, "medium", "🟡",
            f"<strong>EVALUATE</strong> {count} policies in {label} had zero measurable effect",
            "Candidates for removal from policy library",
        ))

    if not items:
        st.markdown(
            '<div class="experiment-card" style="border-left: 3px solid #2ecc71;">'
            '<span style="color: #2ecc71; font-weight: 600;">ALL CLEAR</span>'
            '<span style="color: var(--color-text); font-size: 0.9em;"> — '
            'No critical issues detected in this test cycle.</span></div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        '<div style="color: #00ff41; font-size: 0.9em; font-weight: 600; '
        'margin: 16px 0 8px 0;">ACTION ITEMS</div>',
        unsafe_allow_html=True,
    )

    items.sort(key=lambda x: x[0])
    for _, severity, emoji, text, detail in items:
        color = SEVERITY_BADGES.get(severity, ("🟡", "#f1c40f"))[1]
        css_class = severity if severity in ("critical", "high", "medium", "low") else "medium"
        st.markdown(
            f'<div class="pt-action-card {css_class}">'
            f'<span class="pt-severity-badge" style="background: rgba({_rgb_from_hex(color)}, 0.2); '
            f'color: {color}; border: 1px solid {color};">{emoji} {severity.upper()}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="color: var(--color-text); font-size: 0.9em;">{text}</span>'
            f'<br><span style="color: #555; font-size: 0.8em; margin-left: 70px;">{detail}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════
# Section 5: Policy Health Diagnostic Table
# ═══════════════════════════════════════════════════════════════

def _render_policy_health_table(cycle_results: List[Dict]) -> None:
    """Render full policy health diagnostic table with verdicts."""
    if not cycle_results:
        return

    st.markdown(
        '<div class="section-heading">POLICY HEALTH</div>',
        unsafe_allow_html=True,
    )

    # Build rows with verdict
    rows: List[Dict] = []
    for r in cycle_results:
        verdict_label, verdict_emoji, verdict_color = _compute_verdict(r)
        primary_pct = _compute_primary_pct(r)
        rows.append({
            "policy": _action_label(r),
            "method": r.get("method", "unknown"),
            "deploy": r.get("deploy_success"),
            "effect": r.get("effect_detected"),
            "direction": _compute_effect_direction(r),
            "primary_pct": primary_pct,
            "verdict_label": verdict_label,
            "verdict_emoji": verdict_emoji,
            "verdict_color": verdict_color,
            "verdict_order": VERDICT_ORDER.get(verdict_label, 99),
            "server": (r.get("server_hostname", "") or "").split(".")[0],
        })

    # Sort: by verdict order, then method, then policy name
    rows.sort(key=lambda x: (x["verdict_order"], x["method"], x["policy"]))

    # Group by method for subtotals
    method_groups: Dict[str, List[Dict]] = {}
    for row in rows:
        method_groups.setdefault(row["method"], []).append(row)

    # Build table HTML
    header = (
        '<table class="pt-health-table">'
        '<tr>'
        '<th>Policy Name</th>'
        '<th>Method</th>'
        '<th>Server</th>'
        '<th>Deploy</th>'
        '<th>Effect</th>'
        '<th>Direction</th>'
        '<th>Primary Δ%</th>'
        '<th>Verdict</th>'
        '</tr>'
    )

    body = ""
    for method in sorted(method_groups.keys(), key=lambda m: min(
        r["verdict_order"] for r in method_groups[m]
    )):
        group = method_groups[method]
        group.sort(key=lambda x: (x["verdict_order"], x["policy"]))

        for row in group:
            deploy_icon = "✅" if row["deploy"] else ("❌" if row["deploy"] is False else "⏳")
            effect_icon = "✅" if row["effect"] else ("❌" if row["effect"] is False else "⏳")

            dir_str = row["direction"]
            dir_color = "#2ecc71" if dir_str == "better" else (
                "#ff5555" if dir_str == "worse" else "#555"
            )

            pct_str = _fmt_pct_padded(row["primary_pct"])
            pct_color = _classify_color(row["primary_pct"]) if row["primary_pct"] is not None else "#555"

            body += (
                f'<tr>'
                f'<td style="color: #8be9fd; font-size: 0.85em;">{row["policy"]}</td>'
                f'<td>{METHOD_LABELS.get(row["method"], row["method"])}</td>'
                f'<td style="color: #555;">{row["server"]}</td>'
                f'<td style="text-align: center;">{deploy_icon}</td>'
                f'<td style="text-align: center;">{effect_icon}</td>'
                f'<td style="color: {dir_color}; text-align: center;">{dir_str}</td>'
                f'<td style="color: {pct_color}; text-align: right; font-family: monospace;">'
                f'{pct_str}</td>'
                f'<td style="color: {row["verdict_color"]}; font-weight: 600;">'
                f'{row["verdict_emoji"]} {row["verdict_label"]}</td>'
                f'</tr>'
            )

        # Method subtotal row
        effective = len([r for r in group if r["verdict_label"] == "EFFECTIVE"])
        broken = len([r for r in group if r["verdict_label"] == "BROKEN"])
        harmful = len([r for r in group if r["verdict_label"] == "HARMFUL"])
        dead = len([r for r in group if r["verdict_label"] == "DEAD WEIGHT"])
        method_label = METHOD_LABELS.get(method, method)

        subtotal_parts = []
        if effective:
            subtotal_parts.append(f'<span style="color: #2ecc71;">{effective} effective</span>')
        if broken:
            subtotal_parts.append(f'<span style="color: #ff5555;">{broken} broken</span>')
        if harmful:
            subtotal_parts.append(f'<span style="color: #ff5555;">{harmful} harmful</span>')
        if dead:
            subtotal_parts.append(f'<span style="color: #555;">{dead} dead weight</span>')

        body += (
            f'<tr class="pt-method-subtotal">'
            f'<td colspan="3">{method_label} — {len(group)} policies</td>'
            f'<td colspan="5">{" · ".join(subtotal_parts)}</td>'
            f'</tr>'
        )

    st.markdown(
        f'<div style="overflow-x: auto;">{header}{body}</table></div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════
# Section 6: Effect Heatmap (v2 — proper format)
# ═══════════════════════════════════════════════════════════════

def _render_effect_heatmap(results: List[Dict], servers: List[str]) -> None:
    """Render effect heatmap with properly formatted percentages and multi-column layout."""
    st.markdown(
        '<div class="section-heading">EFFECT HEATMAP</div>',
        unsafe_allow_html=True,
    )

    if not results:
        st.markdown(
            '<div style="color: var(--color-muted); padding: 20px; text-align: center;">'
            "Not enough data for heatmap yet.</div>",
            unsafe_allow_html=True,
        )
        return

    # Build data: rows = action labels, columns = metric columns
    # If multiple servers, group by server with sub-columns
    multi_server = len(servers) > 1

    # Collect per-action data
    action_data: Dict[str, Dict[str, Any]] = {}
    for r in results:
        label = _action_label(r)
        server = (r.get("server_hostname", "") or "").split(".")[0]
        primary_pct = _compute_primary_pct(r)
        total_pct = _compute_total_effect_pct(r)
        direction = _compute_effect_direction(r)
        deploy_ok = r.get("deploy_success")

        key = f"{label}|{server}" if multi_server else label
        action_data[key] = {
            "label": label,
            "server": server,
            "primary_pct": primary_pct,
            "total_pct": total_pct,
            "direction": direction,
            "deploy_ok": deploy_ok,
        }

    if not action_data:
        st.markdown(
            '<div style="color: var(--color-muted); padding: 20px; text-align: center;">'
            "No effect data available yet.</div>",
            unsafe_allow_html=True,
        )
        return

    # Build as HTML table for precise formatting
    header_cols = ["Policy"]
    if multi_server:
        header_cols.append("Server")
    header_cols.extend(["Primary Δ%", "Total Δ%", "Direction", "Deploy"])

    header_html = "<tr>"
    for col in header_cols:
        align = "left" if col in ("Policy", "Server") else "center"
        header_html += f'<th style="text-align: {align};">{col}</th>'
    header_html += "</tr>"

    # Sort by action label
    sorted_keys = sorted(action_data.keys())
    body_html = ""
    for key in sorted_keys:
        d = action_data[key]
        primary_str = _fmt_pct_padded(d["primary_pct"])
        total_str = _fmt_pct_padded(d["total_pct"])
        primary_color = _classify_color(d["primary_pct"]) if d["primary_pct"] is not None else "#555"
        total_color = _classify_color(d["total_pct"]) if d["total_pct"] is not None else "#555"

        dir_str = d["direction"]
        dir_color = "#2ecc71" if dir_str == "better" else (
            "#ff5555" if dir_str == "worse" else "#555"
        )
        dir_icon = "▲" if dir_str == "better" else ("▼" if dir_str == "worse" else "—")

        deploy_icon = "✅" if d["deploy_ok"] else ("❌" if d["deploy_ok"] is False else "⏳")

        body_html += "<tr>"
        body_html += f'<td style="color: #8be9fd; text-align: left;">{d["label"]}</td>'
        if multi_server:
            body_html += f'<td style="color: #555; text-align: left;">{d["server"]}</td>'
        body_html += (
            f'<td style="color: {primary_color}; text-align: right; font-family: monospace;">'
            f'{primary_str}</td>'
        )
        body_html += (
            f'<td style="color: {total_color}; text-align: right; font-family: monospace;">'
            f'{total_str}</td>'
        )
        body_html += (
            f'<td style="color: {dir_color}; text-align: center;">'
            f'{dir_icon} {dir_str}</td>'
        )
        body_html += f'<td style="text-align: center;">{deploy_icon}</td>'
        body_html += "</tr>"

    st.markdown(
        f'<div style="overflow-x: auto;">'
        f'<table class="wiki-table" style="margin: 10px 0;">'
        f'{header_html}{body_html}</table></div>',
        unsafe_allow_html=True,
    )

    # Also render the Plotly heatmap for visual impact (primary metric only)
    _render_heatmap_chart(results, servers)


def _render_heatmap_chart(results: List[Dict], servers: List[str]) -> None:
    """Plotly heatmap of primary metric Δ%: rows=action, columns=servers."""
    if not servers:
        return

    action_map: Dict[str, Dict[str, Optional[float]]] = {}
    for r in results:
        label = _action_label(r)
        server = (r.get("server_hostname", "") or "").split(".")[0]
        pct = _compute_primary_pct(r)
        if server:
            action_map.setdefault(label, {})[server] = pct

    if not action_map:
        return

    actions = sorted(action_map.keys())
    z_vals = []
    text_vals = []
    for action in actions:
        row = []
        text_row = []
        for server in servers:
            val = action_map.get(action, {}).get(server)
            row.append(val if val is not None else 0)
            text_row.append(_fmt_pct_padded(val) if val is not None else "--")
        z_vals.append(row)
        text_vals.append(text_row)

    fig = go.Figure(
        go.Heatmap(
            z=z_vals,
            x=servers,
            y=actions,
            text=text_vals,
            texttemplate="%{text}",
            textfont={"size": 11, "color": "white"},
            colorscale=[
                [0, "#ff5555"],
                [0.35, "#331100"],
                [0.5, "#333"],
                [0.65, "#003300"],
                [1, "#00ff41"],
            ],
            zmid=0,
            showscale=True,
            colorbar=dict(
                title=dict(text="Δ%", font=dict(color="#888")),
                tickfont=dict(color="#888"),
            ),
        )
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0.2)",
        margin=dict(l=200, r=30, t=10, b=50),
        height=max(200, len(actions) * 35 + 60),
        xaxis=dict(side="bottom", tickfont=dict(color="#00ff41")),
        yaxis=dict(tickfont=dict(color="#8be9fd", size=10), autorange="reversed"),
        font=dict(family="JetBrains Mono, monospace"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                    key="heatmap-chart")


# ═══════════════════════════════════════════════════════════════
# Section 7: Test Result Expanders (with Before/During/After)
# ═══════════════════════════════════════════════════════════════

def _render_test_detail(test: Dict) -> None:
    """Single test expander with 3-phase Before/During/After visualization."""
    label = _action_label(test)
    server = (test.get("server_hostname", "unknown") or "unknown").split(".")[0]
    effect = test.get("effect_detected")
    pct = _compute_primary_pct(test)

    deploy_ok_check = test.get("deploy_success")
    if deploy_ok_check is False:
        tag, tag_color = "DEPLOY FAILED", "#ff5555"
    elif effect:
        tag, tag_color = "EFFECT", "#2ecc71"
    elif effect is False:
        tag, tag_color = "NO EFFECT", "#555"
    else:
        tag, tag_color = "PENDING", "#f1c40f"

    with st.expander(f"{label} on {server}", expanded=False):
        deploy_ok = test.get("deploy_success")
        revert_ok = test.get("revert_success")
        deploy_icon = "✅" if deploy_ok else ("❌" if deploy_ok is False else "⏳")
        revert_icon = "✅" if revert_ok else ("❌" if revert_ok is False else "⏳")

        mag_str = _fmt_pct(pct) + " primary metric" if pct is not None else "--"

        # v2 metadata
        workload_mode = test.get("workload_mode", "")
        primary_name = test.get("primary_metric_name", "")
        wall_time = test.get("wall_time_seconds")

        meta_parts = [f"Deploy: {deploy_icon}", f"Revert: {revert_icon}"]
        if workload_mode:
            meta_parts.append(f"Workload: {workload_mode}")
        if wall_time:
            meta_parts.append(f"Duration: {_fmt_duration(wall_time)}")

        st.markdown(
            f'<div class="experiment-card">'
            f'<div style="display: flex; gap: 16px; align-items: center; '
            f'margin-bottom: 12px; flex-wrap: wrap;">'
            f'<span style="color: var(--color-text); font-size: 0.88em;">'
            f'{" &nbsp;·&nbsp; ".join(meta_parts)}</span>'
            f'<span class="status-badge" style="background: rgba({_rgb_from_hex(tag_color)}, 0.2); '
            f'color: {tag_color}; border: 1px solid {tag_color};">{tag}</span>'
            f'<span style="color: var(--color-text); font-size: 0.88em;">'
            f"Magnitude: {mag_str}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # 3-phase Before/During/After visualization
        _render_phase_metrics(test)

        # Intelligence brief
        brief = test.get("intelligence_brief", test.get("analysis_summary", ""))
        if brief:
            st.markdown(
                f'<div style="background: rgba(0, 255, 65, 0.05); border: 1px solid var(--nexus-border); '
                f'border-radius: 6px; padding: 12px; margin-top: 10px;">'
                f'<span style="color: var(--nexus-primary); font-size: 0.8em; font-weight: 600;">'
                f"INTELLIGENCE BRIEF</span><br>"
                f'<span style="color: var(--color-text); font-size: 0.88em; line-height: 1.6;">'
                f"{brief}</span></div>",
                unsafe_allow_html=True,
            )

        # Recommendations
        recommendations = test.get("recommendations", test.get("recommendation", ""))
        if recommendations:
            if isinstance(recommendations, list):
                rec_text = " · ".join(str(r) for r in recommendations)
            else:
                rec_text = str(recommendations)
            rec_color = "#2ecc71" if any(
                w in rec_text.lower() for w in ("keep", "active", "effective")
            ) else (
                "#ff5555" if any(
                    w in rec_text.lower() for w in ("remove", "disable", "harmful")
                ) else "#8be9fd"
            )
            st.markdown(
                f'<div style="margin-top: 8px;">'
                f'<span style="color: var(--color-muted); font-size: 0.8em;">RECOMMENDATION: </span>'
                f'<span class="status-badge" style="background: rgba({_rgb_from_hex(rec_color)}, 0.15); '
                f'color: {rec_color}; border: 1px solid {rec_color};">{rec_text}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)


def _render_phase_metrics(test: Dict) -> None:
    """Render Before/During/After 3-phase metric table with delta arrows."""
    baseline = _extract_metric_means(test.get("baseline_metrics"))
    treatment = _extract_metric_means(test.get("treatment_metrics"))

    if not baseline and not treatment:
        return

    # Check if we have post-revert data (v2)
    has_after = test.get("post_revert_timestamp") is not None

    all_keys = sorted(set(list(baseline.keys()) + list(treatment.keys())))
    if not all_keys:
        return

    # Build phase table
    after_header = '<th>AFTER</th><th>Δ% During→After</th>' if has_after else ''
    header = (
        f'<table class="pt-phase-table">'
        f'<tr>'
        f'<th style="text-align: left;">Metric</th>'
        f'<th>BEFORE</th>'
        f'<th>DURING</th>'
        f'<th>Δ% Before→During</th>'
        f'{after_header}'
        f'</tr>'
    )

    rows = ""
    for key in all_keys:
        bv = baseline.get(key)
        tv = treatment.get(key)
        if bv is None and tv is None:
            continue

        bv_str = _fmt_metric_val(key, bv) if bv is not None else "--"
        tv_str = _fmt_metric_val(key, tv) if tv is not None else "--"

        # Before → During delta
        if bv is not None and tv is not None and bv != 0:
            delta_bd = ((tv - bv) / abs(bv)) * 100
            arrow, arrow_color = _delta_arrow_color(delta_bd)
            delta_bd_str = (
                f'<span style="color: {arrow_color};">{arrow} {_fmt_pct_padded(delta_bd)}</span>'
            )
        else:
            delta_bd_str = '<span style="color: #555;">--</span>'

        after_cells = ""
        if has_after:
            # We don't have separate "after" metrics in the schema,
            # but we note the post-revert timestamp exists
            after_cells = (
                f'<td style="color: #555;">--</td>'
                f'<td style="color: #555;">--</td>'
            )

        rows += (
            f'<tr>'
            f'<td>{key}</td>'
            f'<td style="color: var(--color-text);">{bv_str}</td>'
            f'<td style="color: var(--color-text);">{tv_str}</td>'
            f'<td>{delta_bd_str}</td>'
            f'{after_cells}'
            f'</tr>'
        )

    if rows:
        st.markdown(f'{header}{rows}</table>', unsafe_allow_html=True)

        # If post_revert_timestamp exists, note it
        if has_after:
            post_ts = test.get("post_revert_timestamp", "")
            st.markdown(
                f'<div style="color: #555; font-size: 0.78em; margin-top: 4px;">'
                f'Post-revert snapshot taken at {post_ts[:19] if post_ts else "unknown"} '
                f'— AFTER metrics will populate when post-revert collection is implemented.'
                f'</div>',
                unsafe_allow_html=True,
            )

    # Small Plotly bar chart for visual comparison
    _render_phase_chart(all_keys, baseline, treatment, chart_key=test.get("id", ""))


def _render_phase_chart(keys: List[str], baseline: Dict[str, float],
                        treatment: Dict[str, float], chart_key: str = "") -> None:
    """Small grouped bar chart: Before vs During for each metric."""
    # Only show chart if we have enough data points
    valid_keys = [k for k in keys if k in baseline and k in treatment]
    if len(valid_keys) < 2:
        return

    # Normalize values for chart (show pct change from baseline)
    chart_keys = []
    before_vals = []
    during_vals = []
    for k in valid_keys[:8]:  # Limit to 8 metrics for readability
        bv = baseline[k]
        tv = treatment[k]
        if bv == 0:
            continue
        chart_keys.append(k[:20])  # Truncate long names
        before_vals.append(0)  # Baseline is reference (0%)
        during_vals.append(((tv - bv) / abs(bv)) * 100)

    if not chart_keys:
        return

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Before (baseline)",
        x=chart_keys,
        y=before_vals,
        marker_color="rgba(139, 233, 253, 0.4)",
        marker_line=dict(color="#8be9fd", width=1),
    ))
    fig.add_trace(go.Bar(
        name="During (treatment)",
        x=chart_keys,
        y=during_vals,
        marker_color=[
            "rgba(46, 204, 113, 0.6)" if v > 0 else "rgba(255, 85, 85, 0.6)"
            for v in during_vals
        ],
        marker_line=dict(
            color=["#2ecc71" if v > 0 else "#ff5555" for v in during_vals],
            width=1,
        ),
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0.15)",
        margin=dict(l=40, r=10, t=10, b=40),
        height=180,
        barmode="group",
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(size=9, color="#555"),
        ),
        yaxis=dict(
            title=dict(text="Δ% from baseline", font=dict(size=9, color="#555")),
            tickfont=dict(size=9, color="#555"),
            gridcolor="rgba(255,255,255,0.05)",
            zeroline=True,
            zerolinecolor="rgba(0, 255, 65, 0.3)",
        ),
        xaxis=dict(tickfont=dict(size=8, color="#8be9fd")),
        font=dict(family="JetBrains Mono, monospace"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                    key=f"phase-chart-{chart_key}" if chart_key else None)


# ═══════════════════════════════════════════════════════════════
# Section 8: Cycle History
# ═══════════════════════════════════════════════════════════════

def _render_cycle_history(cycles: List[Dict], results: List[Dict]) -> None:
    """Small table of all cycles at the bottom."""
    if len(cycles) <= 1:
        return

    st.markdown(
        '<div class="section-heading">CYCLE HISTORY</div>',
        unsafe_allow_html=True,
    )

    header = (
        '<div style="display: grid; grid-template-columns: 60px 100px 80px 100px 80px 80px; gap: 4px; '
        'padding: 8px 12px; border-bottom: 1px solid var(--nexus-border); font-size: 0.75em; '
        'color: var(--color-muted); text-transform: uppercase;">'
        "<span>Cycle</span><span>Date</span><span>Status</span>"
        "<span>Tests</span><span>Effects</span><span>Duration</span></div>"
    )

    rows = ""
    for c in cycles:
        cid = c.get("id")
        cycle_results = [r for r in results if r.get("cycle_id") == cid]
        effects = len([r for r in cycle_results if r.get("effect_detected")])
        date_str = (c.get("started_at", "") or "")[:10]
        total = c.get("total_tests", len(cycle_results))

        # Duration: prefer v2, else compute
        dur_s = c.get("total_wall_time_seconds")
        if dur_s is None:
            started = _parse_iso(c.get("started_at"))
            ended = _parse_iso(c.get("completed_at"))
            if started and ended:
                dur_s = (ended - started).total_seconds()
            else:
                dur_s = c.get("duration_seconds")
        dur_str = _fmt_duration(dur_s)

        status = c.get("status", "?").upper()
        status_color = {
            "COMPLETED": "#8be9fd",
            "RUNNING": "#2ecc71",
            "FAILED": "#ff5555",
        }.get(status, "#555")

        rows += (
            f'<div style="display: grid; grid-template-columns: 60px 100px 80px 100px 80px 80px; '
            f'gap: 4px; padding: 6px 12px; border-bottom: 1px solid #111; font-size: 0.82em; '
            f'align-items: center;">'
            f'<span style="color: var(--nexus-primary); font-weight: 600;">'
            f'#{c.get("cycle_number", "?")}</span>'
            f'<span style="color: var(--color-muted);">{date_str}</span>'
            f'<span style="color: {status_color}; font-weight: 600;">{status}</span>'
            f'<span style="color: var(--color-text);">{total}</span>'
            f'<span style="color: var(--color-ok);">{effects}</span>'
            f'<span style="color: var(--color-text);">{dur_str}</span>'
            f"</div>"
        )

    st.markdown(
        f'<div style="background: rgba(0,0,0,0.3); border: 1px solid var(--nexus-border); '
        f'border-radius: 6px; overflow: hidden;">{header}{rows}</div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════

def render_policy_tester_tab(data: Dict) -> None:
    """Main render function called from app.py."""
    # Inject v2 CSS once
    st.markdown(_PT_CSS, unsafe_allow_html=True)

    pt_data = _load_policy_test_data()
    cycles: List[Dict] = pt_data.get("cycles", [])
    results: List[Dict] = pt_data.get("results", [])

    # Feature 1: Global progress bar for running cycles (before everything)
    _render_global_progress(cycles, results)

    # Cycle selector + status
    cycle = _render_cycle_status(cycles, results)
    if not cycle:
        return

    cycle_id = cycle.get("id")
    cycle_results = [r for r in results if r.get("cycle_id") == cycle_id]

    if not cycle_results:
        st.markdown(
            '<div style="color: var(--color-muted); padding: 30px; text-align: center;">'
            "No test results for this cycle yet.</div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown("<br>", unsafe_allow_html=True)

    # Feature 4: Expanded summary metrics (3 rows + timeline)
    _render_summary_metrics(cycle, cycle_results)

    st.markdown("<br>", unsafe_allow_html=True)

    # Feature 5: Post-cycle diagnostic summary + action items
    _render_diagnostic_summary(cycle, cycle_results)

    st.markdown("<br>", unsafe_allow_html=True)

    # Feature 6: Policy health diagnostic table
    _render_policy_health_table(cycle_results)

    st.markdown("<br>", unsafe_allow_html=True)

    # Feature 3: Effect heatmap (proper format)
    servers = sorted({
        (r.get("server_hostname", "") or "").split(".")[0]
        for r in cycle_results
        if r.get("server_hostname")
    })
    _render_effect_heatmap(cycle_results, servers)

    st.markdown("<br>", unsafe_allow_html=True)

    # Feature 2/7: Test results with method filter + Before/During/After
    st.markdown(
        '<div class="section-heading">TEST RESULTS</div>',
        unsafe_allow_html=True,
    )

    methods_in_data = sorted({r.get("method", "unknown") for r in cycle_results})
    filter_options = ["All"] + methods_in_data
    method_filter = st.radio(
        "Filter by method",
        filter_options,
        horizontal=True,
        label_visibility="collapsed",
    )

    filtered = cycle_results
    if method_filter != "All":
        filtered = [r for r in filtered if r.get("method") == method_filter]

    st.markdown(
        f'<div style="color: var(--color-muted); font-size: 0.85em; margin-bottom: 10px;">'
        f"Showing {len(filtered)} of {len(cycle_results)} tests</div>",
        unsafe_allow_html=True,
    )

    for test in filtered:
        _render_test_detail(test)

    st.markdown("<br>", unsafe_allow_html=True)

    # Cycle history
    _render_cycle_history(cycles, results)
