"""
policy_tester_page.py — Policy Tester Dashboard Page

Reads from erad.policy_test_cycles and erad.policy_test_results to show
whether each policy actually affects server metrics.

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
from typing import Any, Dict, List, Optional

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


def _fmt_duration(seconds: Optional[float]) -> str:
    """Format seconds into human-readable duration."""
    if not seconds:
        return "--"
    hours = seconds / 3600
    if hours >= 1:
        return f"{hours:.1f}h"
    minutes = seconds / 60
    return f"{minutes:.0f}m"


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
    action = test.get("action_name", test.get("action", "unknown"))
    params = _safe_json(test.get("action_params", test.get("params", {})))
    if isinstance(params, dict) and params:
        param_str = ", ".join(f"{k}={v}" for k, v in list(params.items())[:3])
        return f"{action}({param_str})"
    return action


# ═══════════════════════════════════════════════════════════════
# Section 1: Cycle Status Bar
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
            f"Cycle #{c.get('cycle_number', i+1)} — {c.get('status', '?').upper()} — "
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
    duration_s = cycle.get("duration_seconds", 0)
    duration_str = _fmt_duration(duration_s)

    cycle_results = [r for r in results if r.get("cycle_id") == cycle_id]
    total_tests = cycle.get("total_tests", len(cycle_results))
    completed_tests = len([r for r in cycle_results if r.get("status", "").lower() in ("completed", "effect_detected", "no_effect", "deploy_failed")])
    servers = list({r.get("server_hostname", "").split(".")[0] for r in cycle_results if r.get("server_hostname")})
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
# Section 2: Summary Metrics
# ═══════════════════════════════════════════════════════════════

def _render_summary_metrics(cycle_results: List[Dict]) -> None:
    """Render 4-column summary metrics."""
    st.markdown(
        '<div class="section-heading">SUMMARY</div>',
        unsafe_allow_html=True,
    )

    total = len(cycle_results)
    effect_detected = len([r for r in cycle_results if r.get("effect_detected") or r.get("status", "").lower() == "effect_detected"])
    no_effect = len([r for r in cycle_results if r.get("status", "").lower() == "no_effect" or (r.get("effect_detected") is False and r.get("deploy_success") is not False)])
    deploy_failed = len([r for r in cycle_results if r.get("deploy_success") is False or r.get("status", "").lower() == "deploy_failed"])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">Tests Run</div>'
            f'<div class="metric-value">{total}</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">Effect Detected</div>'
            f'<div class="metric-value text-ok">{effect_detected}</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">No Effect</div>'
            f'<div class="metric-value" style="color: var(--color-muted);">{no_effect}</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">Deploy Failed</div>'
            f'<div class="metric-value text-error">{deploy_failed}</div></div>',
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════
# Section 3: Effect Heatmap
# ═══════════════════════════════════════════════════════════════

def _render_effect_heatmap(results: List[Dict], servers: List[str]) -> None:
    """Plotly heatmap of effect magnitudes: rows=action+param, columns=servers."""
    st.markdown(
        '<div class="section-heading">EFFECT HEATMAP</div>',
        unsafe_allow_html=True,
    )

    if not results or not servers:
        st.markdown(
            '<div style="color: var(--color-muted); padding: 20px; text-align: center;">'
            "Not enough data for heatmap yet.</div>",
            unsafe_allow_html=True,
        )
        return

    action_map: Dict[str, Dict[str, float]] = {}
    for r in results:
        label = _action_label(r)
        server = (r.get("server_hostname", "") or "").split(".")[0]
        # Parse metric_deltas to get max absolute pct_change
        deltas = _safe_json(r.get("metric_deltas", "[]"))
        if isinstance(deltas, list) and deltas:
            max_delta = max(deltas, key=lambda d: abs(d.get("pct_change", 0)))
            pct = max_delta.get("pct_change", 0)
        else:
            pct = 0.0
        if server:
            action_map.setdefault(label, {})[server] = float(pct)

    if not action_map:
        st.markdown(
            '<div style="color: var(--color-muted); padding: 20px; text-align: center;">'
            "No effect data available yet.</div>",
            unsafe_allow_html=True,
        )
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
            text_row.append(f"{val:+.1f}%" if val is not None else "--")
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
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ═══════════════════════════════════════════════════════════════
# Section 5: Detailed Test Log
# ═══════════════════════════════════════════════════════════════

def _render_test_detail(test: Dict) -> None:
    """Single test expander with metrics table + intelligence brief."""
    label = _action_label(test)
    server = (test.get("server_hostname", "unknown") or "unknown").split(".")[0]
    effect = test.get("effect_detected")
    # Parse the largest pct_change from metric_deltas
    deltas = _safe_json(test.get("metric_deltas", "[]"))
    if isinstance(deltas, list) and deltas:
        max_d = max(deltas, key=lambda d: abs(d.get("pct_change", 0)))
        pct = max_d.get("pct_change")
    else:
        pct = None

    deploy_ok_check = test.get("deploy_success")
    tag = "EFFECT" if effect else ("DEPLOY FAILED" if deploy_ok_check is False else ("NO EFFECT" if effect is False else "PENDING"))
    tag_color = "#2ecc71" if effect else ("#ff5555" if deploy_ok_check is False else ("#555" if effect is False else "#f1c40f"))

    with st.expander(f"{label} on {server}", expanded=False):
        deploy_ok = test.get("deploy_success")
        revert_ok = test.get("revert_success")
        deploy_icon = "✅" if deploy_ok else ("❌" if deploy_ok is False else "⏳")
        revert_icon = "✅" if revert_ok else ("❌" if revert_ok is False else "⏳")

        mag_str = _fmt_pct(pct) + " primary metric" if pct is not None else "--"

        st.markdown(
            f'<div class="experiment-card">'
            f'<div style="display: flex; gap: 20px; align-items: center; margin-bottom: 12px;">'
            f'<span style="color: var(--color-text); font-size: 0.9em;">'
            f"Deploy: {deploy_icon} &nbsp; Revert: {revert_icon}</span>"
            f'<span class="status-badge" style="background: rgba({_rgb_from_hex(tag_color)}, 0.2); '
            f'color: {tag_color}; border: 1px solid {tag_color};">{tag}</span>'
            f'<span style="color: var(--color-text); font-size: 0.9em;">'
            f"Magnitude: {mag_str}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        metrics_baseline_raw = _safe_json(test.get("baseline_metrics", {}))
        metrics_treatment_raw = _safe_json(test.get("treatment_metrics", {}))
        # Extract measurement means from the nested structure
        metrics_baseline = {}
        metrics_treatment = {}
        for mkey, mdata in (metrics_baseline_raw.get("measurements", metrics_baseline_raw) if isinstance(metrics_baseline_raw, dict) else {}).items():
            if isinstance(mdata, dict) and "mean" in mdata:
                metrics_baseline[mkey] = mdata["mean"]
            elif isinstance(mdata, (int, float)):
                metrics_baseline[mkey] = mdata
        for mkey, mdata in (metrics_treatment_raw.get("measurements", metrics_treatment_raw) if isinstance(metrics_treatment_raw, dict) else {}).items():
            if isinstance(mdata, dict) and "mean" in mdata:
                metrics_treatment[mkey] = mdata["mean"]
            elif isinstance(mdata, (int, float)):
                metrics_treatment[mkey] = mdata

        if metrics_baseline and metrics_treatment:
            rows_html = ""
            all_keys = sorted(set(list(metrics_baseline.keys()) + list(metrics_treatment.keys())))
            for key in all_keys:
                bv = metrics_baseline.get(key)
                tv = metrics_treatment.get(key)
                if bv is None or tv is None:
                    continue
                try:
                    bv_f = float(bv)
                    tv_f = float(tv)
                    delta = ((tv_f - bv_f) / bv_f * 100) if bv_f != 0 else 0
                    delta_color = _classify_color(delta)
                    bv_str = _fmt_metric_val(key, bv_f)
                    tv_str = _fmt_metric_val(key, tv_f)
                    delta_str = f"{delta:+.1f}%"
                except (ValueError, TypeError):
                    continue

                rows_html += (
                    f"<tr>"
                    f'<td style="color: var(--color-cyan);">{key}</td>'
                    f'<td style="color: var(--color-text); text-align: right;">{bv_str}</td>'
                    f'<td style="color: var(--color-text); text-align: right;">{tv_str}</td>'
                    f'<td style="color: {delta_color}; text-align: right; font-weight: 600;">{delta_str}</td>'
                    f"</tr>"
                )

            if rows_html:
                st.markdown(
                    f'<table class="wiki-table" style="margin: 10px 0;">'
                    f"<tr>"
                    f'<th style="text-align: left;">Metric</th>'
                    f'<th style="text-align: right;">Baseline</th>'
                    f'<th style="text-align: right;">Treatment</th>'
                    f'<th style="text-align: right;">Δ%</th>'
                    f"</tr>"
                    f"{rows_html}</table>",
                    unsafe_allow_html=True,
                )

        brief = test.get("intelligence_brief", test.get("analysis_summary", ""))
        if brief:
            st.markdown(
                f'<div style="background: rgba(0, 255, 65, 0.05); border: 1px solid var(--nexus-border); '
                f'border-radius: 6px; padding: 12px; margin-top: 10px;">'
                f'<span style="color: var(--nexus-primary); font-size: 0.8em; font-weight: 600;">'
                f"INTELLIGENCE BRIEF</span><br>"
                f'<span style="color: var(--color-text); font-size: 0.9em; line-height: 1.6;">'
                f"{brief}</span></div>",
                unsafe_allow_html=True,
            )

        recommendation = test.get("recommendation", "")
        if recommendation:
            rec_color = "#2ecc71" if "keep" in recommendation.lower() or "active" in recommendation.lower() else (
                "#ff5555" if "remove" in recommendation.lower() or "disable" in recommendation.lower() else "#8be9fd"
            )
            st.markdown(
                f'<div style="margin-top: 8px;">'
                f'<span style="color: var(--color-muted); font-size: 0.8em;">RECOMMENDATION: </span>'
                f'<span class="status-badge" style="background: rgba({_rgb_from_hex(rec_color)}, 0.15); '
                f'color: {rec_color}; border: 1px solid {rec_color};">{recommendation}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)


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


def _rgb_from_hex(hex_color: str) -> str:
    """Convert #RRGGBB or #RGB to 'R, G, B' string for rgba()."""
    h = hex_color.lstrip("#") if hex_color else ""
    if len(h) == 3:
        h = h[0]*2 + h[1]*2 + h[2]*2
    if len(h) < 6:
        return "85, 85, 85"  # safe fallback grey
    try:
        return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"
    except ValueError:
        return "85, 85, 85"


# ═══════════════════════════════════════════════════════════════
# Section 6: Cycle History
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
        '<div style="display: grid; grid-template-columns: 60px 100px 80px 100px 80px; gap: 4px; '
        'padding: 8px 12px; border-bottom: 1px solid var(--nexus-border); font-size: 0.75em; '
        'color: var(--color-muted); text-transform: uppercase;">'
        "<span>Cycle</span><span>Date</span><span>Tests</span>"
        "<span>Effects Found</span><span>Duration</span></div>"
    )

    rows = ""
    for c in cycles:
        cid = c.get("id")
        cycle_results = [r for r in results if r.get("cycle_id") == cid]
        effects = len([r for r in cycle_results if r.get("effect_detected")])
        date_str = (c.get("started_at", "") or "")[:10]
        dur = _fmt_duration(c.get("duration_seconds"))
        total = c.get("total_tests", len(cycle_results))

        rows += (
            f'<div style="display: grid; grid-template-columns: 60px 100px 80px 100px 80px; gap: 4px; '
            f'padding: 6px 12px; border-bottom: 1px solid #111; font-size: 0.82em; align-items: center;">'
            f'<span style="color: var(--nexus-primary); font-weight: 600;">#{c.get("cycle_number", "?")}</span>'
            f'<span style="color: var(--color-muted);">{date_str}</span>'
            f'<span style="color: var(--color-text);">{total}</span>'
            f'<span style="color: var(--color-ok);">{effects}</span>'
            f'<span style="color: var(--color-text);">{dur}</span>'
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
    pt_data = _load_policy_test_data()
    cycles: List[Dict] = pt_data.get("cycles", [])
    results: List[Dict] = pt_data.get("results", [])

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

    # Section 2: Summary Metrics
    _render_summary_metrics(cycle_results)

    st.markdown("<br>", unsafe_allow_html=True)

    # Section 3: Effect Heatmap
    servers = sorted({
        (r.get("server_hostname", "") or "").split(".")[0]
        for r in cycle_results
        if r.get("server_hostname")
    })
    _render_effect_heatmap(cycle_results, servers)

    st.markdown("<br>", unsafe_allow_html=True)

    # Section 4: Method Filter
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

    # Section 5: Detailed Test Log
    for test in filtered:
        _render_test_detail(test)

    st.markdown("<br>", unsafe_allow_html=True)

    # Section 6: Cycle History
    _render_cycle_history(cycles, results)
