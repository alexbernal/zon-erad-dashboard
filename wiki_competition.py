"""
wiki_competition.py — ERAD Wiki (For Dummies), Competition Tab, and Analysis Box Plots

Integration into app.py:
───────────────────────
1. Add import at top of app.py:
       from wiki_competition import render_wiki_tab, render_competition_tab, render_improvement_box_plots

2. Replace the existing render_wiki_tab() function (lines 1383-1548) with:
       # Imported from wiki_competition.py

3. In main(), update the sidebar nav list to include Competition:
       tab = st.radio("Navigation", [
           "🏠 Overview",
           "📊 Experiments",
           "📈 Analysis",
           "🖥️ Servers",
           "📋 Activity Log",
           "🏆 Competition",
           "📚 Wiki",
       ], label_visibility="collapsed")

4. Add routing elif in main() (between Activity Log and Wiki):
       elif tab == "🏆 Competition":
           render_competition_tab(data)

5. In render_analysis_tab(), after the Strategy×Method bar chart block
   (after line ~1141, before the "<br>" and Duration section), insert:
       render_improvement_box_plots(results)

   Where `results` is the same `data.get("results") or []` already in that function.
   Or more precisely, pass `completed` (the filtered list) for better results:
       render_improvement_box_plots(completed)
"""

import streamlit as st
import pandas as pd
import json
from typing import Any, Dict, List
import plotly.graph_objects as go


# ═══════════════════════════════════════════════════════════════
# SHARED CONSTANTS (imported or duplicated from app.py)
# ═══════════════════════════════════════════════════════════════

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


def _parse_conclusion(r: dict) -> dict:
    """Extract conclusion_json from experiment result."""
    conc = r.get("conclusion_json") or {}
    if isinstance(conc, str):
        try:
            conc = json.loads(conc)
        except Exception:
            conc = {}
    return conc


def _plotly_layout(**overrides) -> dict:
    """Standard Construct-theme Plotly layout."""
    base = dict(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0.2)",
        margin=dict(l=50, r=20, t=30, b=50),
        font=dict(family="JetBrains Mono, monospace"),
    )
    base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════
# TAB: WIKI (For Dummies Edition)
# ═══════════════════════════════════════════════════════════════

def render_wiki_tab():
    st.markdown('<div class="dashboard-title">ERAD WIKI</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="dashboard-subtitle">'
        'For Humans &bull; Plain English &bull; No PhD Required'
        '</div>',
        unsafe_allow_html=True,
    )

    wiki_nav = st.radio(
        "Navigate:",
        [
            "\U0001f4d6 What is ERAD?",
            "\U0001f3af Strategies (How We Test)",
            "\U0001f527 Methods (What We Tune)",
            "\U0001f9e0 SCBO (The Brain)",
            "\U0001f52c Policy Tester",
            "\u2699\ufe0f How It All Works",
            "\U0001f4dd Glossary",
        ],
        horizontal=True,
        label_visibility="collapsed",
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # ─── TAB 1: What is ERAD? ───────────────────────────────────
    if wiki_nav == "\U0001f4d6 What is ERAD?":
        _wiki_what_is_erad()
    elif wiki_nav == "\U0001f3af Strategies (How We Test)":
        _wiki_strategies()
    elif wiki_nav == "\U0001f527 Methods (What We Tune)":
        _wiki_methods()
    elif wiki_nav == "\U0001f9e0 SCBO (The Brain)":
        _wiki_scbo()
    elif wiki_nav == "\U0001f52c Policy Tester":
        _wiki_policy_tester()
    elif wiki_nav == "\u2699\ufe0f How It All Works":
        _wiki_how_it_works()
    elif wiki_nav == "\U0001f4dd Glossary":
        _wiki_glossary()


# ── Wiki Sub-Sections ────────────────────────────────────────

def _wiki_what_is_erad():
    # Overview with car analogy
    st.markdown('''<div class="wiki-section"><h3>What is ERAD?</h3>
<p style="color: var(--color-text); line-height: 1.8; font-size: 1em;">
    Imagine you just bought a car. It runs fine out of the box, but you <em>know</em> it could run better.
    Maybe a different tire pressure, a slightly different idle speed, a better gear-shift schedule...
</p>
<p style="color: var(--color-text); line-height: 1.8; font-size: 1em; margin-top: 10px;">
    <strong>ERAD</strong> is an <span class="glossary-term">automatic mechanic</span> for servers.
    It watches how your server performs, tries small adjustments, measures whether they helped,
    and remembers what works &mdash; getting smarter over time.
</p>
<p style="color: var(--nexus-primary); font-style: italic; padding: 12px; background: rgba(0,255,65,0.05); border-radius: 4px; margin-top: 15px;">
    "ERAD is like having a tireless, patient mechanic who tries thousands of tiny adjustments
    to your engine &mdash; scientifically measuring each one &mdash; and only keeps the ones that
    actually make it run better."
</p></div>''', unsafe_allow_html=True)

    # The 4-step cycle
    st.markdown('''<div class="wiki-section"><h3>The 4-Step Cycle: E-R-A-D</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    Every optimization follows the same loop, over and over:
</p>
<table class="wiki-table" style="margin: 15px 0;">
    <tr><th>Step</th><th>Name</th><th>What Happens</th><th>Car Analogy</th></tr>
    <tr><td style="color: var(--nexus-primary); font-weight: 700; font-size: 1.2em;">E</td>
        <td><span class="glossary-term">Evaluate</span></td>
        <td>Look at the server right now. Is it busy? Idle? Overheating?</td>
        <td>Check the dashboard &mdash; RPM, temperature, fuel economy</td></tr>
    <tr><td style="color: var(--nexus-primary); font-weight: 700; font-size: 1.2em;">R</td>
        <td><span class="glossary-term">Recommend</span></td>
        <td>Based on what we know, pick a setting to try next.</td>
        <td>Mechanic says "Let's try adjusting the idle speed"</td></tr>
    <tr><td style="color: var(--nexus-primary); font-weight: 700; font-size: 1.2em;">A</td>
        <td><span class="glossary-term">Adapt</span></td>
        <td>Apply the change, measure the result. Did it help?</td>
        <td>Adjust idle speed, drive for 10 minutes, check fuel economy</td></tr>
    <tr><td style="color: var(--nexus-primary); font-weight: 700; font-size: 1.2em;">D</td>
        <td><span class="glossary-term">Discover</span></td>
        <td>Save the result. Share with other similar servers.</td>
        <td>Write in the maintenance log: "Idle speed X works best for this engine"</td></tr>
</table></div>''', unsafe_allow_html=True)

    # ASCII cycle diagram
    st.markdown('''<div class="wiki-section"><h3>The Cycle Visualized</h3>
<div class="code-block" style="font-size: 0.9em; line-height: 1.6;">
                    ┌─────────────────────┐
                    │     E V A L U A T E  │  &lt;── "How is the server doing right now?"
                    │  (measure everything)│
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   R E C O M M E N D  │  &lt;── "What should we try next?"
                    │   (pick a setting)   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      A D A P T       │  &lt;── "Apply it and see what happens"
                    │  (run experiment)    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    D I S C O V E R   │  &lt;── "Save what we learned"
                    │  (record &amp; share)    │
                    └──────────┬──────────┘
                               │
                               └────────────────────── back to EVALUATE ──►
</div></div>''', unsafe_allow_html=True)

    # How big is one cycle?
    st.markdown('''<div class="wiki-section"><h3>How Big is One Cycle?</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    Each cycle tests <strong>every combination</strong> of strategies and methods on every server:
</p>
<div class="code-block" style="font-size: 0.9em; line-height: 1.8;">
  4 Strategies     ×    4 Methods     ×    2 Servers    =   <span style="color: #00ff41; font-weight: 700;">32 experiments per cycle</span>
  ─────────────         ──────────         ──────────
  Shadow Mode           Power State        metal-erad-001
  A/B Tester            I/O Scheduler      metal-erad-002
  Thompson Bandit       Memory Manager
  Bayesian Opt          Forecaster

  Each experiment runs 8-14 iterations inside it.
  So one cycle = roughly 250-450 individual measurements.
</div>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 12px;">
    Think of it like a school test: 32 questions per exam, and the system takes one exam after another,
    getting smarter each time.
</p></div>''', unsafe_allow_html=True)


def _wiki_strategies():
    st.markdown('''<div class="wiki-section"><h3>Strategies &mdash; How We Test Things</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    A <span class="glossary-term">strategy</span> is the <em>method of experimentation</em> &mdash; 
    it decides HOW to try different settings. Think of it as the scientist's approach.
    We use 4 different strategies, from cautious to aggressive:
</p></div>''', unsafe_allow_html=True)

    # Shadow Mode
    st.markdown('''<div class="wiki-section"><h3>1. Shadow Mode &mdash; "Look But Don't Touch"</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    Shadow Mode watches what's happening on the server and <strong>predicts</strong> what would happen
    if you made a change &mdash; without actually making any changes. Like window shopping.
</p>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 10px;">
    <strong>Real-world analogy:</strong> You're thinking about rearranging a restaurant kitchen.
    Before you move a single pan, you stand in the corner for a week and <em>observe</em>.
    Where do the chefs walk? What do they reach for most? Where are the bottlenecks?
    Only after watching do you propose changes.
</p>
<div class="code-block" style="margin-top: 12px;">
  SHADOW MODE:

  Server: "I'm running at 200W, CPU at 60%, latency 2ms"

  Shadow:  🔍 Watching...
           🔍 Watching...
           🔍 Watching...
           📝 "If we lowered CPU frequency, I predict we'd save 15W
                with only +0.3ms latency. But I'm NOT touching anything."

  Result:  Pure data. Zero risk. Perfect for first contact with a new server.
</div>
<p style="color: var(--color-muted); margin-top: 8px; font-style: italic;">
    Best for: First time on a new server, safety verification, establishing baselines.
</p></div>''', unsafe_allow_html=True)

    # A/B Tester
    st.markdown('''<div class="wiki-section"><h3>2. A/B Tester &mdash; "The Taste Test"</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    Like a taste test. You give half the people Pepsi and the other half Coke, then count who liked what.
    Simple, fair, and hard to argue with the results.
</p>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 10px;">
    <strong>Real-world analogy &mdash; the pizza shop:</strong>
</p>
<div class="code-block" style="margin-top: 8px;">
  THE PIZZA EXPERIMENT:

  Monday  → Bake at 375°F → Customers rate it: 7.2/10 average
  Tuesday → Bake at 425°F → Customers rate it: 8.1/10 average

  Is 8.1 really better than 7.2?  Or did we just get lucky on Tuesday?

  A/B Tester runs a statistical test:
  "What are the odds this 0.9-point difference happened by pure chance?"

  Answer: 2.3% chance it's random → That's less than 5% → DECLARE WINNER! 🏆
  425°F wins with statistical confidence.
</div>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 10px;">
    The 5% threshold is called <span class="glossary-term">statistical significance</span>.
    If there's less than a 5% chance the result is random luck, we trust it.
</p>
<p style="color: var(--color-muted); margin-top: 8px; font-style: italic;">
    Best for: When you want ironclad proof. Courtroom-grade evidence that one setting beats another.
</p></div>''', unsafe_allow_html=True)

    # Thompson Sampling
    st.markdown('''<div class="wiki-section"><h3>3. Thompson Sampling &mdash; "The Smart Slot Machine Player"</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    Imagine you're in a casino with 5 slot machines. You don't know which one pays best.
    A dumb strategy: try each one 100 times (500 pulls total). A <em>smart</em> strategy:
    try each one a few times, then gradually shift your attention toward the winners &mdash;
    while occasionally trying the others just in case.
</p>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 10px;">
    <strong>Real-world analogy &mdash; the coffee shop:</strong>
</p>
<div class="code-block" style="margin-top: 8px;">
  FINDING YOUR FAVORITE COFFEE SHOP (4 options):

  Week 1:  Try all 4 roughly equally
           Shop A: ★★★☆☆  Shop B: ★★★★☆  Shop C: ★★☆☆☆  Shop D: ★★★★★

  Week 2:  Mostly go to B and D (the good ones), but try A once more
           Shop B: ★★★★☆  Shop D: ★★★★★  Shop A: ★★★☆☆

  Week 3:  Almost always at D, occasional check on B
           Shop D: ★★★★★  Shop D: ★★★★★  Shop B: ★★★★☆

  Result:  Found the winner in ~12 visits instead of 100!
</div>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 10px;">
    <strong>Key insight:</strong> You don't need to try every option the same number of times.
    Spend more time on what looks promising, less on what looks bad &mdash; but never completely ignore anything.
    This is called the <span class="glossary-term">explore vs. exploit</span> tradeoff.
</p>
<p style="color: var(--color-muted); margin-top: 8px; font-style: italic;">
    Best for: When you have many options and want to find the winner fast without wasting time on losers.
</p></div>''', unsafe_allow_html=True)

    # Bayesian Optimizer
    st.markdown('''<div class="wiki-section"><h3>4. Bayesian Optimizer &mdash; "The Mind Reader"</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    Instead of blindly trying options, the Bayesian Optimizer builds a <strong>mental model</strong>
    of how settings relate to results. Then it makes smart guesses about what to try next.
</p>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 10px;">
    <strong>Real-world analogy &mdash; brewing the perfect tea:</strong>
</p>
<div class="code-block" style="margin-top: 8px;">
  FINDING THE PERFECT TEA TEMPERATURE (range: 150°F to 212°F):

  Dumb approach: Try every degree. That's 62 experiments.

  Bayesian approach:
    Try 1: 170°F → Taste: 3/10   (too cold)
    Try 2: 200°F → Taste: 5/10   (too hot)
    Try 3: 185°F → Taste: 8/10!  (optimizer said "try the middle-ish")
    Try 4: 190°F → Taste: 9/10!  (optimizer said "a bit hotter than 185")
    Try 5: 191°F → Taste: 9.2/10! (fine-tuning)

  Result:  5 tries instead of 62.  That's 91% fewer experiments!

  HOW? After each try, the optimizer updates its model:
  ┌──────────────────────────────────────────┐
  │  Temperature →   150   170   185   200   │
  │  Predicted   →   ???   3.0   8.0   5.0   │
  │  Uncertainty →   HIGH  low   low   low   │
  │                         ↑                 │
  │                    "Try HERE next"        │
  │                  (high predicted value    │
  │                   OR high uncertainty)    │
  └──────────────────────────────────────────┘
</div>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 10px;">
    It's like playing 20 Questions really well. Each answer narrows down where the best answer is.
</p>
<p style="color: var(--color-muted); margin-top: 8px; font-style: italic;">
    Best for: Continuous settings with huge search spaces. Finding the needle in the haystack efficiently.
</p></div>''', unsafe_allow_html=True)

    # Strategy comparison
    st.markdown('''<div class="wiki-section"><h3>Strategy Comparison At a Glance</h3>
<div class="code-block" style="font-size: 0.85em; line-height: 1.6;">
  RISK LEVEL:    None ───────────────────────────────────────── High
                  │                                              │
                  Shadow          A/B          Thompson      Bayesian
                  (watch only)    (fair test)  (smart gamble) (smart guess)

  SPEED:         Slow ───────────────────────────────────────── Fast
                  │                                              │
                  A/B             Shadow       Thompson      Bayesian
                  (needs many     (just        (adapts       (learns from
                   samples)       watches)      quickly)      every try)

  CONFIDENCE:    Low ────────────────────────────────────────── High
                  │                                              │
                  Shadow          Thompson     Bayesian      A/B
                  (predictions    (probabilistic) (modeled)   (statistical
                   only)                                       proof)
</div></div>''', unsafe_allow_html=True)


def _wiki_methods():
    st.markdown('''<div class="wiki-section"><h3>Methods &mdash; What We Actually Tune</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    If strategies are <em>how</em> we test, methods are <em>what</em> we test.
    Each method controls a different part of the server hardware.
    Think of them as different knobs on a mixing board.
</p></div>''', unsafe_allow_html=True)

    # PowerState
    st.markdown('''<div class="wiki-section"><h3>1. Power State &mdash; "The Gas Pedal"</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    Controls how fast the CPU runs and how deeply it sleeps when idle &mdash;
    like switching your car between <strong>Eco</strong>, <strong>Normal</strong>, and <strong>Sport</strong> mode.
</p>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 10px;">
    Turn it down to save electricity. Turn it up when you need performance.
    We have <strong>1,305 preset configurations</strong> for this across all our server types.
</p>
<div class="code-block" style="margin-top: 8px;">
  POWER STATE KNOBS:

  ┌──────────────────┬──────────────────────────────────────────┐
  │  CPU Governor     │  "performance" / "powersave" / "ondemand"│
  │  Frequency Limit  │  800 MHz  ───────────────  3800 MHz      │
  │  Power Cap (RAPL) │  45W  ────────────────────  250W         │
  │  Sleep Depth      │  C1 (light nap) ── C6 (deep sleep)      │
  │  PCIe Power       │  Full speed  ──  Low power mode          │
  └──────────────────┴──────────────────────────────────────────┘

  ECO MODE:     Low frequency, deep sleep, aggressive power saving
  SPORT MODE:   Max frequency, no sleeping, all power available
  SWEET SPOT:   Somewhere in between — that's what ERAD finds!
</div>
<table class="wiki-table" style="margin-top: 12px;">
    <tr><th>Metric We Watch</th><th>Weight</th><th>Goal</th></tr>
    <tr><td><code>power_watts</code> &mdash; How much electricity</td><td>50%</td><td>Lower is better</td></tr>
    <tr><td><code>cpu_percent</code> &mdash; CPU utilization</td><td>20%</td><td>Lower is better</td></tr>
    <tr><td><code>context_switches_per_sec</code> &mdash; How often CPU switches tasks</td><td>15%</td><td>Lower is better</td></tr>
    <tr><td><code>cpu_pressure_psi_avg10</code> &mdash; CPU bottleneck pressure</td><td>15%</td><td>Lower is better</td></tr>
</table></div>''', unsafe_allow_html=True)

    # Forecaster
    st.markdown('''<div class="wiki-section"><h3>2. Forecaster &mdash; "The Crystal Ball"</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    The Forecaster doesn't touch any hardware knob &mdash; it <strong>predicts the future</strong>.
    It looks at the last 7 days of data and spots patterns like
    "busy at 9 AM, quiet at midnight."
</p>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 10px;">
    Then it tells PowerState to switch <strong>5 minutes before</strong> the rush hits.
</p>
<div class="code-block" style="margin-top: 8px;">
  WITHOUT FORECASTER:                    WITH FORECASTER:

  8:55 AM  Server idle, Eco mode         8:55 AM  "Rush coming in 5 min!"
  9:00 AM  RUSH! 100 users arrive!       8:56 AM  Switch to Sport mode
  9:00 AM  Scramble to switch to Sport   9:00 AM  RUSH! Already ready. ✓
  9:02 AM  Finally at full speed         9:00 AM  Full speed from second 1
           (2 min of slow responses)                (zero slow responses)
</div>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 10px;">
    It's the <strong>Nest thermostat</strong> that pre-heats your house before your alarm goes off.
    It doesn't control the temperature directly &mdash; it just knows <em>when</em> to tell
    the heater to turn on.
</p>
<table class="wiki-table" style="margin-top: 12px;">
    <tr><th>Metric We Watch</th><th>Weight</th><th>Goal</th></tr>
    <tr><td><code>cpu_percent</code> &mdash; Were we ready in time?</td><td>35%</td><td>Lower is better</td></tr>
    <tr><td><code>power_watts</code> &mdash; Power saved by prediction</td><td>25%</td><td>Lower is better</td></tr>
    <tr><td><code>context_switches_per_sec</code> &mdash; Transition smoothness</td><td>20%</td><td>Lower is better</td></tr>
    <tr><td><code>cpu_pressure_psi_avg10</code> &mdash; Avoided pressure spikes</td><td>20%</td><td>Lower is better</td></tr>
</table></div>''', unsafe_allow_html=True)

    # I/O Scheduler
    st.markdown('''<div class="wiki-section"><h3>3. I/O Scheduler &mdash; "The Traffic Cop"</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    Controls who gets to use the hard disk. When multiple programs compete to read/write data,
    the I/O Scheduler decides who goes first.
</p>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 10px;">
    Critical apps get the fast lane. Background tasks wait their turn.
    Like a traffic cop at a busy intersection.
</p>
<div class="code-block" style="margin-top: 8px;">
  THE INTERSECTION:

  ┌─────────────────────────────────────────────────────────┐
  │                    DISK ACCESS                          │
  │                       ║                                 │
  │   Database ═══════════╬══════════► FAST LANE (priority) │
  │                       ║                                 │
  │   Log writer ─────────╬──────────► Normal lane          │
  │                       ║                                 │
  │   Backup job ·········╬··········► Wait lane (low prio) │
  │                       ║                                 │
  │               🚦 I/O SCHEDULER                          │
  │              decides who goes                           │
  └─────────────────────────────────────────────────────────┘

  SCHEDULER OPTIONS:
    mq-deadline  →  "Everyone gets a deadline, no one waits forever"
    kyber        →  "Fast lane / slow lane separation"
    bfq          →  "Fair sharing with priority support"
    none         →  "First come first served (fastest, no fairness)"
</div>
<table class="wiki-table" style="margin-top: 12px;">
    <tr><th>Metric We Watch</th><th>Weight</th><th>Goal</th></tr>
    <tr><td><code>iops_total</code> &mdash; Disk operations per second</td><td>40%</td><td>Higher is better</td></tr>
    <tr><td><code>avg_read_latency_ms</code> &mdash; How long a read takes</td><td>35%</td><td>Lower is better</td></tr>
    <tr><td><code>throughput_read_mbps</code> &mdash; Data transfer speed</td><td>15%</td><td>Higher is better</td></tr>
    <tr><td><code>power_watts</code> &mdash; Electricity cost</td><td>10%</td><td>Lower is better</td></tr>
</table></div>''', unsafe_allow_html=True)

    # Memory Manager
    st.markdown('''<div class="wiki-section"><h3>4. Memory Manager &mdash; "The Warehouse Organizer"</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    Controls how RAM is organized. Servers have multiple memory banks &mdash;
    accessing the closest one is fast, accessing a far one is slow.
    The Memory Manager puts data close to the CPU that needs it.
</p>
<div class="code-block" style="margin-top: 8px;">
  THE WAREHOUSE:

  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │  CPU 1 ←──── Bank A (FAST)    CPU 2 ←──── Bank B (FAST)│
  │         ╲                           ╲                   │
  │          ╲── Bank B (SLOW)           ╲── Bank A (SLOW)  │
  │                                                         │
  │  Popular items → Near the front (closest memory bank)   │
  │  Bulk storage  → Reserved pallets (hugepages)           │
  │  Rarely used   → Back of warehouse (can be swapped out) │
  │                                                         │
  └─────────────────────────────────────────────────────────┘

  KNOBS WE TURN:
    Hugepages    →  Reserve big memory blocks (less overhead)
    Swappiness   →  How eager to move stuff to disk (0-100)
    NUMA Policy  →  "Always use local memory" vs "use any available"
    Cache Pressure → How aggressively to reclaim cached data
</div>
<table class="wiki-table" style="margin-top: 12px;">
    <tr><th>Metric We Watch</th><th>Weight</th><th>Goal</th></tr>
    <tr><td><code>pgmajfault_per_sec</code> &mdash; Times data wasn't in RAM</td><td>30%</td><td>Lower is better</td></tr>
    <tr><td><code>numa_hit_ratio</code> &mdash; Got data from closest bank</td><td>25%</td><td>Higher is better</td></tr>
    <tr><td><code>memory_pressure_psi_avg10</code> &mdash; Memory bottleneck</td><td>20%</td><td>Lower is better</td></tr>
    <tr><td><code>swap_used_mb</code> &mdash; Data shoved to disk (bad)</td><td>15%</td><td>Lower is better</td></tr>
    <tr><td><code>power_watts</code> &mdash; Electricity cost</td><td>10%</td><td>Lower is better</td></tr>
</table></div>''', unsafe_allow_html=True)

    # Thermal Controller (Coming Soon)
    st.markdown('''<div class="wiki-section"><h3>5. Thermal Controller &mdash; "The AC Technician" (Coming Soon)</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    Manages heat and cooling &mdash; fan speed, temperature limits.
</p>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 10px;">
    <strong>Why this matters:</strong> Datacenter cooling is <strong>30-40% of total power cost</strong>.
    Most servers run fans way harder than they need to. It's like running your car's
    AC on maximum blast when it's only mildly warm outside.
</p>
<div class="code-block" style="margin-top: 8px;">
  THE OPPORTUNITY:

  Typical datacenter power breakdown:
  ┌────────────────────────────────────────────┐
  │  Servers (computing)    ████████████  60%   │
  │  Cooling (fans + HVAC)  ██████       35%   │
  │  Other (networking etc) █            5%    │
  └────────────────────────────────────────────┘

  Google DeepMind applied AI to cooling → saved 40% on cooling costs.
  That's a 14% reduction in TOTAL datacenter power.

  We plan to do the same thing, server by server.
</div>
<p style="color: var(--color-warn); margin-top: 8px; font-style: italic;">
    Status: In development. Not yet included in experiment cycles.
</p></div>''', unsafe_allow_html=True)


def _wiki_scbo():
    st.markdown('''<div class="wiki-section"><h3>SCBO &mdash; The Brain Behind ERAD</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    <strong>SCBO</strong> stands for <span class="glossary-term">Safe Contextual Bayesian Optimization</span>.
    It's the smartest strategy in ERAD's toolkit &mdash; the one that actually <em>thinks</em>
    before it acts.
</p>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 10px;">
    Think of it as upgrading from "trying random things" to "having a brilliant assistant
    who studies the situation, predicts what will work, checks if it's safe, and learns from every attempt."
</p></div>''', unsafe_allow_html=True)

    # 6 Superpowers
    st.markdown('''<div class="wiki-section"><h3>SCBO's 6 Superpowers</h3></div>''', unsafe_allow_html=True)

    superpowers = [
        (
            "1. Context Vectors &mdash; \"Knows the Situation\"",
            "SCBO doesn't just know WHAT to optimize &mdash; it knows WHEN and WHERE.",
            '''  Regular optimizer:  "Lower CPU frequency saves power" (always)

  SCBO:  "Lower CPU frequency saves power... but ONLY when:
          - It's 3 AM on a Sunday (low traffic)
          - CPU is below 30% utilization
          - No batch jobs are scheduled

          At 3 PM on Wednesday with 80% CPU? Keep it HIGH."

  The 5 context dimensions:
  ┌─────────────────────────────────────────┐
  │  1. CPU pressure    (how busy)          │
  │  2. Memory pressure (how full)          │
  │  3. I/O pressure    (how much disk use) │
  │  4. Time of day     (morning vs night)  │
  │  5. Workload volatility (stable vs spiky)│
  └─────────────────────────────────────────┘''',
        ),
        (
            "2. Epistemic Tracking &mdash; \"Knows What It Doesn't Know\"",
            "Most systems are overconfident. SCBO tracks its own uncertainty.",
            '''  Scenario: SCBO has tried CPU frequencies 2.0-3.0 GHz many times,
  but never tried 1.5 GHz.

  Dumb optimizer: "1.5 GHz is probably bad" (guessing!)
  SCBO:           "I have NO DATA about 1.5 GHz. Uncertainty is HIGH.
                   I should try it at least once before ruling it out."

  This prevents the system from getting stuck in a local optimum
  (thinking it found the best when it actually just never tried
  something potentially better).''',
        ),
        (
            "3. Proactive Safety &mdash; \"Checks Before Acting\"",
            "SCBO predicts whether an action will violate safety limits BEFORE applying it.",
            '''  Regular optimizer:
    1. Apply action
    2. Measure result
    3. OH NO, server overheated! → Emergency rollback

  SCBO:
    1. PREDICT what will happen if we apply action
    2. "This would push temperature to 95°C... that's above our 90°C limit"
    3. SKIP this action, try something safer
    4. Server never even noticed

  Like a chess player thinking 3 moves ahead instead of just reacting.''',
        ),
        (
            "4. Adaptive Loop &mdash; \"Shifts Strategy Automatically\"",
            "Early on, SCBO explores widely. As it learns, it narrows down to fine-tuning.",
            '''  Cycle 1:  "I know nothing" → TRY EVERYTHING (wide exploration)
             ▓▓▓▓▓▓▓▓▓▓░░░░  (90% explore, 10% exploit)

  Cycle 5:  "I have some ideas" → MIX OF BOTH
             ▓▓▓▓▓░░░░░░░░░  (50% explore, 50% exploit)

  Cycle 10: "I'm pretty confident" → MOSTLY FINE-TUNE
             ▓▓░░░░░░░░░░░░  (20% explore, 80% exploit)

  Cycle 20: "I know this server well" → POLISH
             ▓░░░░░░░░░░░░░  (5% explore, 95% exploit)

  No human has to tell it when to switch. It does it automatically.''',
        ),
        (
            "5. Multi-Objective &mdash; \"Juggles Multiple Goals\"",
            "Real servers need MULTIPLE things to be good simultaneously.",
            '''  The challenge:
    Goal 1: Save power        (lower is better)
    Goal 2: Keep performance  (higher is better)
    Goal 3: Stay cool         (lower is better)

  These CONFLICT! Saving power usually hurts performance.

  SCBO uses weighted scalarization:
    Score = 0.50 × power_saved + 0.30 × performance_kept + 0.20 × temp_reduced

  It finds the BEST TRADEOFF, not just the best at one thing.

  Like a chef balancing salt, sweet, and sour — not just maximizing one.''',
        ),
        (
            "6. Transfer Learning &mdash; \"Shares Knowledge\"",
            "What works on one server often works on similar servers.",
            '''  Server A (Dell PowerEdge R750):
    "I learned that kyber I/O scheduler + 2GHz CPU cap saves 18% power"

  Server B (Dell PowerEdge R750 — same model, different datacenter):
    "I've never been optimized... but Server A is just like me!"

  SCBO: "Let me start Server B's optimization with Server A's best
         settings as a starting point instead of starting from zero."

  Result: Server B reaches optimal in 3 cycles instead of 10.
          Like a new employee learning from a veteran's notes.''',
        ),
    ]

    for title, subtitle, ascii_art in superpowers:
        st.markdown(f'''<div class="wiki-section"><h3>{title}</h3>
<p style="color: var(--color-text); line-height: 1.8;">{subtitle}</p>
<div class="code-block" style="margin-top: 8px; font-size: 0.85em; line-height: 1.5;">
{ascii_art}
</div></div>''', unsafe_allow_html=True)


def _wiki_how_it_works():
    # Step-by-step lifecycle
    st.markdown('''<div class="wiki-section"><h3>Step-by-Step: What Happens in One Experiment</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    Let's walk through exactly what happens when ERAD runs a single experiment.
    Say it's testing <span class="glossary-term">Bayesian Opt</span> +
    <span class="glossary-term">I/O Scheduler</span> on server <code>metal-erad-001</code>.
</p>
<div class="code-block" style="margin-top: 12px; font-size: 0.85em; line-height: 1.6;">
  STEP 1: CONNECT
  ════════════════
  ERAD → metal-erad-001: "Hello! I'm going to test I/O settings on you."
  Server → ERAD: "Ready. Current scheduler: mq-deadline, queue depth: 128"

  STEP 2: BASELINE (measure "before")
  ════════════════════════════════════
  ERAD measures for 30 seconds WITHOUT changing anything:
    iops_total:          45,000
    avg_read_latency_ms: 0.82
    throughput_read_mbps: 1,200
    power_watts:         185

  STEP 3: STRATEGY PICKS AN ACTION
  ════════════════════════════════════
  Bayesian Opt checks its model: "Based on what I know...
    - kyber scheduler looks promising (high predicted improvement)
    - queue_depth=256 has high uncertainty (worth exploring)"
  → Decision: set_io_scheduler(scheduler=kyber, queue_depth=256)

  STEP 4: SAFETY CHECK
  ════════════════════════════════════
  SCBO predicts: "This change will likely:
    - Increase IOPS by ~12% ✓
    - Decrease latency by ~8% ✓
    - Power impact: negligible ✓
    - No guardrail violations predicted ✓"
  → APPROVED. Apply the change.

  STEP 5: APPLY & STABILIZE
  ════════════════════════════════════
  ERAD → Server: "Switch to kyber, set queue_depth=256"
  Server: "Done."
  ERAD: Waits 30 seconds for the change to settle...

  STEP 6: TREATMENT (measure "after")
  ════════════════════════════════════
  ERAD measures for 30 seconds WITH the change:
    iops_total:          50,200  (+11.6%)
    avg_read_latency_ms: 0.71   (-13.4%)
    throughput_read_mbps: 1,340  (+11.7%)
    power_watts:         186     (+0.5%)

  STEP 7: SCORE & RECORD
  ════════════════════════════════════
  Composite score = 0.40×(+11.6%) + 0.35×(+13.4%) + 0.15×(+11.7%) + 0.10×(-0.5%)
                  = +10.99% improvement!

  STEP 8: REPEAT (iterations 2-14)
  ════════════════════════════════════
  Strategy tries more settings, each time learning from the last.
  After 10-14 iterations, it has a clear winner.

  STEP 9: CONCLUDE
  ════════════════════════════════════
  "Winner: kyber scheduler with queue_depth=256
   Improvement: +10.99% composite
   Confidence: 97.3%
   Status: DEPLOYED as permanent policy on metal-erad-001"
</div></div>''', unsafe_allow_html=True)

    # Reading the Dashboard
    st.markdown('''<div class="wiki-section"><h3>How to Read This Dashboard</h3>
<table class="wiki-table">
    <tr><th>Tab</th><th>What It Shows</th><th>What to Look For</th></tr>
    <tr><td><span class="glossary-term">Overview</span></td>
        <td>The big picture — is the engine running? What cycle are we on?</td>
        <td>Green = healthy. Look at the heatmap to see which combos have been tested.</td></tr>
    <tr><td><span class="glossary-term">Experiments</span></td>
        <td>Every experiment ever run, with full details</td>
        <td>Click any experiment to see what policies were tested and which won.</td></tr>
    <tr><td><span class="glossary-term">Analysis</span></td>
        <td>Trends over time — is the system getting smarter?</td>
        <td>Improvement line should trend upward. Bar chart shows which combos work best.</td></tr>
    <tr><td><span class="glossary-term">Servers</span></td>
        <td>Per-server breakdown</td>
        <td>Does one server respond better to certain methods than the other?</td></tr>
    <tr><td><span class="glossary-term">Activity Log</span></td>
        <td>Raw Temporal workflow events and timeline</td>
        <td>Useful for debugging. You can export data as CSV here.</td></tr>
    <tr><td><span class="glossary-term">Competition</span></td>
        <td>Rankings — best experiments and best individual policies</td>
        <td>Which specific settings have the biggest impact across all experiments?</td></tr>
</table></div>''', unsafe_allow_html=True)

    # Safety Guarantees
    st.markdown('''<div class="wiki-section"><h3>Safety Guarantees &mdash; "What Could Go Wrong?"</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    Tuning live production servers sounds scary. Here's why it's safe:
</p>
<div class="code-block" style="margin-top: 8px; font-size: 0.85em; line-height: 1.6;">
  SAFETY LAYER 1: SHADOW MODE FIRST
  ══════════════════════════════════
  Every cycle starts with Shadow Mode — pure observation, zero changes.
  We always know the baseline before touching anything.

  SAFETY LAYER 2: GUARDRAILS
  ══════════════════════════════════
  Every metric has a hard limit. Example:
    - CPU temperature must stay below 90°C
    - Power must stay below 250W
    - Latency must stay below 5ms
  If ANY guardrail is breached → INSTANT automatic rollback.

  SAFETY LAYER 3: PROACTIVE PREDICTION
  ══════════════════════════════════
  SCBO predicts violations BEFORE they happen.
  If a proposed action WOULD breach a guardrail → it's never applied.

  SAFETY LAYER 4: TEMPORAL DURABILITY
  ══════════════════════════════════
  If the optimization engine crashes mid-experiment:
    - Temporal remembers exactly where we were
    - Worker restarts → picks up from last checkpoint
    - No orphaned changes left on servers

  SAFETY LAYER 5: RATE LIMITING
  ══════════════════════════════════
  Hard limits prevent runaway:
    - Max 10 concurrent experiments
    - Max 5 child workflows
    - Max 10 requests/minute
  These exist because of a real $13,728 cloud cost incident.

  SAFETY LAYER 6: AUTOMATIC ROLLBACK
  ══════════════════════════════════
  If any experiment fails for ANY reason → all changes are reverted.
  The server goes back to exactly how it was before we touched it.
</div></div>''', unsafe_allow_html=True)


def _wiki_policy_tester():
    # Overview
    st.markdown('''<div class="wiki-section"><h3>What is the Policy Tester?</h3>
<p style="color: var(--color-text); line-height: 1.8; font-size: 1em;">
    ERAD is smart &mdash; it picks which settings to try, measures the results, and learns.
    But there's a question it can't answer on its own:
    <strong>"Does each policy actually DO anything to the server?"</strong>
</p>
<p style="color: var(--color-text); line-height: 1.8; font-size: 1em; margin-top: 10px;">
    The <strong>Policy Tester</strong> is like a factory quality inspector.
    Before you trust any experiment result, you need to know that the lever you're pulling
    is actually connected to the machine.
    In <strong>v2</strong>, the tester goes further &mdash; it deploys a <strong>matching workload</strong>
    for each method group so that policies are tested under realistic load, not on idle servers.
    This means "no effect" actually means no effect, not "we forgot to turn the machine on."
</p>
<p style="color: var(--nexus-primary); font-style: italic; padding: 12px; background: rgba(0,255,65,0.05); border-radius: 4px; margin-top: 15px;">
    "Imagine a scientist who discovers that flipping a light switch doesn't actually turn on the light.
    All their experiments measuring 'the effect of light' are meaningless.
    Now imagine the scientist also makes sure the room is occupied before testing &mdash;
    because a light switch in an empty room looks like it does nothing.
    v2 of the Policy Tester does both: checks the wiring AND fills the room."
</p></div>''', unsafe_allow_html=True)

    # How it works - workload-aware v2 flow
    st.markdown('''<div class="wiki-section"><h3>The Workload-Aware Test Cycle &mdash; How v2 Verifies Policies</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    v2 groups policies by <strong>method</strong> (io_scheduler, memory_manager, power_state, forecaster)
    and deploys a <strong>matching workload simulation</strong> before testing each group.
    This ensures metrics are measured under realistic load, not idle servers.
</p>
<div class="code-block" style="font-size: 0.9em; line-height: 1.8;">
  FOR EACH METHOD GROUP (io_scheduler, memory_manager, power_state, forecaster):

  STEP  1:  Deploy a workload that exercises this method type
  STEP  2:  PRIMING &mdash; 60 seconds of workload only (no policy)
            This establishes a clean baseline under load.

    FOR EACH POLICY in this method group:

      STEP  3:  BASELINE &mdash; Measure everything for 60 seconds ("how is it NOW under load?")
      STEP  4:  DEPLOY &mdash; Apply the policy to the server
      STEP  5:  TREATMENT &mdash; Measure everything for 60 seconds ("how is it AFTER?")
      STEP  6:  REVERT &mdash; Undo the change. Put everything back.
      STEP  7:  COOLDOWN &mdash; 60 seconds between policies (let the server settle)
      STEP  8:  Classify: EFFECT / NO EFFECT / DEPLOY FAILED
      STEP  9:  Write an Intelligence Brief explaining what happened.

  STEP 10:  Stop the workload for this method group
  STEP 11:  BUFFER &mdash; 120 seconds before the next workload group starts
</div>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 12px;">
    This runs for <strong>every</strong> policy &times; <strong>every</strong> server, grouped by method.
    With 74 unique policies and 2 servers, that's <strong>148 tests per cycle</strong>,
    organized into <strong>4 workload groups</strong>.
</p>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 8px;">
    <strong>Why the priming and cooldowns?</strong> Without them, the first policy in a group
    gets tested on a cold server and the last one on a warm server &mdash; apples to oranges.
    The 60-second priming ensures every policy starts from the same loaded baseline,
    and the 60-second cooldown prevents one policy's residual effects from bleeding into the next.
</p></div>''', unsafe_allow_html=True)

    # Why it matters
    st.markdown('''<div class="wiki-section"><h3>Why This Matters &mdash; The Light Switch Problem</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    Imagine you have 74 light switches on a wall, but some of them aren't connected to anything.
    If you run experiments with a disconnected switch, you'll conclude "this setting has no effect"
    &mdash; but the truth is <strong>you never actually changed anything</strong>.
</p>
<div class="code-block" style="font-size: 0.9em; line-height: 1.8; margin-top: 10px;">
  WITHOUT POLICY TESTER:              WITH POLICY TESTER:

  Run 500 experiments                  First: test all 74 policies
  20 policies silently fail            Find 36 that fail to deploy
  to deploy (no error!)                Flag them BEFORE experiments

  "No effect found" for 20%            Fix the 36, then experiment
  of experiments                       with confidence

  Wrong conclusion:                    Right conclusion:
  "These policies don't work"          "These policies work, here's proof"
</div>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 12px;">
    In our first real test cycle, we found that <strong>36 out of 148 tests</strong> had deploy failures &mdash;
    all from the <code>power_state</code> method. Without the Policy Tester, those would have been
    silent failures inside experiments, giving us bad data.
</p></div>''', unsafe_allow_html=True)

    # The dashboard
    st.markdown('''<div class="wiki-section"><h3>Reading the Policy Tester Dashboard</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    The Policy Tester tab has 8 sections. Here's what each one tells you:
</p>
<table class="wiki-table" style="margin: 15px 0;">
    <tr><th>Section</th><th>What You See</th><th>What It Means</th></tr>
    <tr><td style="color: var(--nexus-primary); font-weight: 600;">Global Progress Bar</td>
        <td>Animated pulsing bar at the very top: tests completed/total, current workload group &amp; number (e.g. "Group 2/4 &mdash; memory_manager"), target servers, % bar, elapsed time</td>
        <td>Live status of the running cycle. Shows which method group is active and how far along you are.</td></tr>
    <tr><td style="color: var(--nexus-primary); font-weight: 600;">Summary Metrics (Row 1)</td>
        <td>4 big numbers: Tests Run, Effect Detected, No Effect, Deploy Failed</td>
        <td>The scoreboard. "Deploy Failed" is the most important &mdash; those policies are broken.</td></tr>
    <tr><td style="color: var(--nexus-primary); font-weight: 600;">Summary Metrics (Row 2)</td>
        <td>Workload Groups, Total Wall Time, Avg Test Duration, Measurement Window</td>
        <td>Operational stats. How long the cycle took, how many groups were tested, and the measurement window per test.</td></tr>
    <tr><td style="color: var(--nexus-primary); font-weight: 600;">Summary Metrics (Row 3)</td>
        <td>Method Breakdown &mdash; color-coded bars per method (Forecaster, I/O Scheduler, Memory Manager, Power State)</td>
        <td>At a glance: how many tests per method, color-coded by type. Spot imbalances instantly.</td></tr>
    <tr><td style="color: var(--nexus-primary); font-weight: 600;">Effect Heatmap</td>
        <td>Table with columns: Policy | Server | Primary &Delta;% | Total &Delta;% | Direction | Deploy. Values in <code>+07.08%</code> zero-padded format.</td>
        <td>Green = positive effect, red = negative, gray = neutral. Deploy column shows &#x2705;/&#x274C;. Quick visual scan of every policy.</td></tr>
    <tr><td style="color: var(--nexus-primary); font-weight: 600;">Test Results</td>
        <td>Expandable cards showing Before/During/After metrics, delta arrows (&#x25B2; green / &#x25BC; red / &mdash; gray), and a Plotly grouped bar chart of % change from baseline</td>
        <td>Click any test to see the 3-phase comparison: BEFORE (baseline), DURING (policy active), AFTER (reverted). The chart shows % change per metric.</td></tr>
    <tr><td style="color: var(--nexus-primary); font-weight: 600;">Diagnostic Summary</td>
        <td>Ranked action items by severity: &#x1F534; CRITICAL, &#x1F7E0; HIGH, &#x1F7E1; MEDIUM, &#x1F7E2; LOW. Each with action verb, count, method, and recommendation.</td>
        <td>After a cycle completes, this tells you exactly what to fix and in what order. Start at the top (CRITICAL) and work down.</td></tr>
    <tr><td style="color: var(--nexus-primary); font-weight: 600;">Policy Health Table</td>
        <td>Full table: Policy Name | Method | Server | Deploy | Effect | Direction | Primary &Delta;% | Verdict. Sorted by severity with method subtotals.</td>
        <td>The definitive status of every policy. Verdicts: &#x26A0;&#xFE0F; BROKEN, &#x1F534; HARMFUL, &#x1F4A4; DEAD WEIGHT, &#x1F7E1; MARGINAL, &#x2705; EFFECTIVE.</td></tr>
</table></div>''', unsafe_allow_html=True)

    # Interpreting results
    st.markdown('''<div class="wiki-section"><h3>Interpreting the Results &mdash; Tags and Verdicts</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    <strong>Test-level tags</strong> (assigned during the cycle):
</p>
<table class="wiki-table" style="margin: 15px 0;">
    <tr><th>Tag</th><th>Color</th><th>What Happened</th><th>What To Do</th></tr>
    <tr><td><strong>EFFECT</strong></td>
        <td style="color: #2ecc71;">Green</td>
        <td>Policy deployed successfully AND metrics changed measurably</td>
        <td>This policy works. ERAD can use it in experiments with confidence.</td></tr>
    <tr><td><strong>NO EFFECT</strong></td>
        <td style="color: #888;">Grey</td>
        <td>Policy deployed successfully but metrics didn't change</td>
        <td>In v2 this is tested under load, so "no effect" genuinely means the policy doesn't move the needle for this method's workload.</td></tr>
    <tr><td><strong>DEPLOY FAILED</strong></td>
        <td style="color: #ff5555;">Red</td>
        <td>The policy could not be applied to the server</td>
        <td>The MCP probe tool is broken, missing, or the server doesn't support this action. Fix the probe before using this policy in experiments.</td></tr>
    <tr><td><strong>PENDING</strong></td>
        <td style="color: #f1c40f;">Yellow</td>
        <td>Test hasn't run yet</td>
        <td>Wait for the cycle to reach this test.</td></tr>
</table>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 15px;">
    <strong>Policy Health verdicts</strong> (assigned after the cycle in the Diagnostic Summary):
</p>
<table class="wiki-table" style="margin: 15px 0;">
    <tr><th>Verdict</th><th>Icon</th><th>Meaning</th><th>Action</th></tr>
    <tr><td><strong>BROKEN</strong></td>
        <td>&#x26A0;&#xFE0F;</td>
        <td>Policy cannot deploy at all</td>
        <td>Check the MCP probe tool. This policy is unusable until fixed.</td></tr>
    <tr><td><strong>HARMFUL</strong></td>
        <td style="color: #ff5555;">&#x1F534;</td>
        <td>Policy deploys but <em>degrades</em> performance</td>
        <td>Remove from the experiment library or investigate why it makes things worse.</td></tr>
    <tr><td><strong>DEAD WEIGHT</strong></td>
        <td>&#x1F4A4;</td>
        <td>Policy deploys but has zero measurable impact</td>
        <td>Candidate for removal from the library. It's taking up experiment slots for nothing.</td></tr>
    <tr><td><strong>MARGINAL</strong></td>
        <td style="color: #f1c40f;">&#x1F7E1;</td>
        <td>Effect detected but less than 1%</td>
        <td>Keep for now, but deprioritize. The effect is real but tiny.</td></tr>
    <tr><td><strong>EFFECTIVE</strong></td>
        <td style="color: #2ecc71;">&#x2705;</td>
        <td>Meaningful positive effect detected</td>
        <td>This policy works. Prioritize it in experiments.</td></tr>
</table></div>''', unsafe_allow_html=True)

    # Safety guarantees
    st.markdown('''<div class="wiki-section"><h3>Safety Guarantees</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    The Policy Tester has the same safety rules as ERAD experiments:
</p>
<div class="code-block" style="font-size: 0.9em; line-height: 1.8; margin-top: 10px;">
  ONE policy at a time &mdash; never stack changes
  Every policy is REVERTED after testing &mdash; server goes back to normal
  No experiments run during testing &mdash; checks for running workflows first
  Pause / Resume / Cancel signals &mdash; you can stop it anytime
  All results saved to Supabase &mdash; permanent audit trail
  Intelligence brief for every test &mdash; AI explains what happened
</div>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 12px;">
    The golden rule: <strong>only one thing changes at a time, and everything gets put back</strong>.
    Your servers are never left in an unknown state.
</p></div>''', unsafe_allow_html=True)

    # The flow diagram
    st.markdown('''<div class="wiki-section"><h3>Policy Tester Flow (v2 &mdash; Workload-Aware)</h3>
<div class="code-block" style="font-size: 0.85em; line-height: 1.6;">
  ERAD Policy Library (74 unique actions)
                  |
    Group policies by method:
    [io_scheduler] [memory_manager] [power_state] [forecaster]
                  |
    FOR EACH METHOD GROUP:
                  |
      DEPLOY WORKLOAD           start a load that exercises this method
                  |
      PRIMING (60s)             workload only, no policy &mdash; clean baseline
                  |
        FOR EACH POLICY in this group:
                  |
          BASELINE (60s)        measure under load, before policy
                  |
          DEPLOY POLICY         apply the change
                  |
          TREATMENT (60s)       measure under load, with policy
                  |
          REVERT                put everything back
                  |
          COOLDOWN (60s)        let the server settle
                  |
          CLASSIFY + BRIEF      verdict and explanation
                  |
      STOP WORKLOAD             remove the load
                  |
      BUFFER (120s)             rest before next group
                  |
    DIAGNOSTIC SUMMARY          ranked action items + health table
</div></div>''', unsafe_allow_html=True)

    # Real example from cycle 3
    st.markdown('''<div class="wiki-section"><h3>Real Example from Our First Test Cycle</h3>
<div class="code-block" style="font-size: 0.9em; line-height: 1.8;">
  CYCLE 3 RESULTS:

  Total tests:     148 (74 policies x 2 servers)
  Deployed OK:     112 (76%)
  Deploy Failed:    36 (24%) &mdash; ALL from power_state methods
  Effects Found:     0 (servers were idle, so no load to affect)

  BREAKDOWN BY METHOD:
  io_scheduler ..... 100% deploy success
  memory_manager ... 100% deploy success
  forecaster ....... 100% deploy success
  power_state ......   0% deploy success  &lt;&lt; PROBLEM FOUND!

  VERDICT:
  Three power_state tools (set_pcie_aspm, set_sched_latency,
  set_sched_migration_cost) are broken on both servers.
  Fix these before running power_state experiments.
</div>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 12px;">
    This is exactly the kind of insight the Policy Tester is designed to provide.
    Without it, the power_state experiments would have run hundreds of iterations
    with broken tools &mdash; wasting time and producing meaningless data.
</p>
<p style="color: var(--color-text); line-height: 1.8; margin-top: 8px;">
    <strong>Note:</strong> Cycle 3 ran on v1 (idle servers). With v2's workload-aware testing,
    the "Effects Found: 0" problem is solved &mdash; policies are now tested under realistic load,
    so genuine effects are visible.
</p></div>''', unsafe_allow_html=True)

    # New in v2
    st.markdown('''<div class="wiki-section"><h3>New in v2 &mdash; What Changed</h3>
<p style="color: var(--color-text); line-height: 1.8;">
    The Policy Tester was rewritten from 644 to 1,719 lines. Here's what's new:
</p>
<table class="wiki-table" style="margin: 15px 0;">
    <tr><th>#</th><th>Feature</th><th>What It Does</th></tr>
    <tr><td>1</td>
        <td style="color: var(--nexus-primary); font-weight: 600;">Workload-Aware Testing</td>
        <td>Policies are grouped by method. A matching workload runs during testing so metrics reflect real load, not idle servers. 60s priming, 60s cooldowns, 120s buffer between groups.</td></tr>
    <tr><td>2</td>
        <td style="color: var(--nexus-primary); font-weight: 600;">Global Progress Bar</td>
        <td>Animated pulsing bar at the top showing tests completed/total, current workload group, target servers, % progress, and elapsed time.</td></tr>
    <tr><td>3</td>
        <td style="color: var(--nexus-primary); font-weight: 600;">Expanded Summary (3 rows)</td>
        <td>Row 1: same 4 metrics. Row 2: Workload Groups, Wall Time, Avg Duration, Window. Row 3: Method Breakdown with color-coded bars.</td></tr>
    <tr><td>4</td>
        <td style="color: var(--nexus-primary); font-weight: 600;">Before / During / After Metrics</td>
        <td>Each test expander shows 3-phase comparison with color-coded delta arrows (&#x25B2; green, &#x25BC; red, &mdash; gray) and a Plotly grouped bar chart.</td></tr>
    <tr><td>5</td>
        <td style="color: var(--nexus-primary); font-weight: 600;">Improved Effect Heatmap</td>
        <td>Values in zero-padded <code>+07.08%</code> format. Columns: Policy | Server | Primary &Delta;% | Total &Delta;% | Direction | Deploy (&#x2705;/&#x274C;).</td></tr>
    <tr><td>6</td>
        <td style="color: var(--nexus-primary); font-weight: 600;">Diagnostic Summary</td>
        <td>Ranked action items by severity: &#x1F534; CRITICAL (deploy failures), &#x1F7E0; HIGH (degraded), &#x1F7E1; MEDIUM (zero effect), &#x1F7E2; LOW (marginal). Each with action verb, count, and recommendation.</td></tr>
    <tr><td>7</td>
        <td style="color: var(--nexus-primary); font-weight: 600;">Policy Health Table</td>
        <td>Full diagnostic table with verdicts: &#x26A0;&#xFE0F; BROKEN, &#x1F534; HARMFUL, &#x1F4A4; DEAD WEIGHT, &#x1F7E1; MARGINAL, &#x2705; EFFECTIVE. Sorted by severity with method subtotals.</td></tr>
    <tr><td>8</td>
        <td style="color: var(--nexus-primary); font-weight: 600;">Updated Flow</td>
        <td>Method-grouped execution with priming, cooldowns, and buffer periods. See the flow diagram above.</td></tr>
</table></div>''', unsafe_allow_html=True)


def _wiki_glossary():
    st.markdown('''<div class="wiki-section"><h3>Glossary &mdash; Plain English Definitions</h3>
<table class="wiki-table">
    <tr><th>Term</th><th>What It Means</th></tr>

    <tr><td><span class="glossary-term">ERAD</span></td>
        <td><strong>Evaluate-Recommend-Adapt-Discover.</strong> The 4-step loop that makes servers better over time. Like a mechanic who keeps tuning your engine and learning from each adjustment.</td></tr>

    <tr><td><span class="glossary-term">Cycle</span></td>
        <td>One complete pass through all 32 experiments (4 strategies &times; 4 methods &times; 2 servers). Like one full semester of classes.</td></tr>

    <tr><td><span class="glossary-term">Experiment</span></td>
        <td>A single test: one strategy + one method + one server. Contains 8-14 iterations. Like one exam question.</td></tr>

    <tr><td><span class="glossary-term">Iteration</span></td>
        <td>One baseline&rarr;change&rarr;measure loop inside an experiment. Like one trial in a science experiment.</td></tr>

    <tr><td><span class="glossary-term">Strategy</span></td>
        <td>HOW we test (Shadow, A/B, Thompson, Bayesian). Like choosing between a survey, a blind taste test, or a focused interview.</td></tr>

    <tr><td><span class="glossary-term">Method</span></td>
        <td>WHAT we tune (Power, I/O, Memory, Forecaster). Like choosing whether to adjust the engine, the tires, or the suspension.</td></tr>

    <tr><td><span class="glossary-term">Policy</span></td>
        <td>A specific setting change. Example: "set I/O scheduler to kyber with queue depth 256." Like a recipe instruction.</td></tr>

    <tr><td><span class="glossary-term">Fitness Score</span></td>
        <td>A single number that combines all the metrics we care about (weighted). Like a GPA that combines all your grades.</td></tr>

    <tr><td><span class="glossary-term">Improvement %</span></td>
        <td>How much better the treatment was vs. baseline. +5% means 5% better. Negative means it got worse.</td></tr>

    <tr><td><span class="glossary-term">Confidence</span></td>
        <td>How sure we are the result isn't random luck. 95% confidence = only 5% chance it's a fluke.</td></tr>

    <tr><td><span class="glossary-term">Baseline</span></td>
        <td>The "before" measurement. Current settings, no changes applied. The control group.</td></tr>

    <tr><td><span class="glossary-term">Treatment</span></td>
        <td>The "after" measurement. New settings applied. The experimental group.</td></tr>

    <tr><td><span class="glossary-term">Guardrail</span></td>
        <td>A safety limit. If crossed, the change is automatically rolled back. Like a speed limiter on a car.</td></tr>

    <tr><td><span class="glossary-term">Rollback</span></td>
        <td>Undoing a change. If something goes wrong, we put everything back the way it was. Ctrl+Z for servers.</td></tr>

    <tr><td><span class="glossary-term">SCBO</span></td>
        <td><strong>Safe Contextual Bayesian Optimization.</strong> The brain that makes smart, safe decisions. Predicts outcomes before acting.</td></tr>

    <tr><td><span class="glossary-term">Gaussian Process (GP)</span></td>
        <td>A mathematical model that learns patterns from data and makes predictions WITH uncertainty estimates. Like a weather forecast that says "70°F, plus or minus 5°."</td></tr>

    <tr><td><span class="glossary-term">Expected Improvement (EI)</span></td>
        <td>A formula that picks the next thing to try by balancing "probably good" vs. "worth exploring." Like deciding between your favorite restaurant (safe bet) and the new place (might be amazing).</td></tr>

    <tr><td><span class="glossary-term">Thompson Sampling</span></td>
        <td>A strategy where you randomly pick actions weighted by how good they've been. Good ones get picked more often, but bad ones still get occasional chances. Like a DJ playing crowd favorites but sneaking in new tracks.</td></tr>

    <tr><td><span class="glossary-term">Cohen's d</span></td>
        <td>A measure of HOW BIG a difference is, not just whether it exists. Small (0.2), Medium (0.5), Large (0.8+). Like the difference between "slightly taller" and "towering over."</td></tr>

    <tr><td><span class="glossary-term">MCP (Model Context Protocol)</span></td>
        <td>The communication standard our probes use. Like USB &mdash; a universal plug that lets the optimizer talk to any server the same way.</td></tr>

    <tr><td><span class="glossary-term">Temporal</span></td>
        <td>The workflow engine that runs ERAD. If the power goes out mid-experiment, Temporal remembers where we left off and picks up automatically. Like a save point in a video game.</td></tr>

    <tr><td><span class="glossary-term">Context Vector</span></td>
        <td>A 5-number snapshot of "what's happening right now" on the server. Lets SCBO make different decisions for different situations.</td></tr>

    <tr><td><span class="glossary-term">Explore vs. Exploit</span></td>
        <td>The fundamental tradeoff: try new things (explore) or stick with what works (exploit). Like trying a new restaurant vs. going to your favorite. Good optimizers balance both.</td></tr>

    <tr><td><span class="glossary-term">Local Optimum</span></td>
        <td>A "pretty good" setting that isn't actually the best. Like finding a nice hill and thinking it's the tallest mountain because you stopped looking. SCBO's exploration prevents getting stuck here.</td></tr>

    <tr><td><span class="glossary-term">NUMA</span></td>
        <td><strong>Non-Uniform Memory Access.</strong> Some RAM is closer to a CPU than other RAM. Accessing close memory is faster. The Memory Manager optimizes which data goes where.</td></tr>

    <tr><td><span class="glossary-term">Policy Tester</span></td>
        <td>A verification tool that tests every policy under realistic workload conditions. v2 groups policies by method, deploys a matching workload, measures before/during/after metrics, then reverts. Produces a diagnostic summary with verdicts (BROKEN, HARMFUL, DEAD WEIGHT, MARGINAL, EFFECTIVE). Catches broken deploys, harmful policies, and dead weight <em>before</em> experiments run. Like a pre-flight checklist that also simulates turbulence.</td></tr>

    <tr><td><span class="glossary-term">Intelligence Brief</span></td>
        <td>An AI-generated summary explaining what happened during a policy test or experiment. Written in plain English so anyone can understand the result.</td></tr>

    <tr><td><span class="glossary-term">RAPL</span></td>
        <td><strong>Running Average Power Limit.</strong> Intel's built-in power cap for CPUs. Like a speed limiter &mdash; you set a wattage ceiling and the CPU won't exceed it.</td></tr>
</table></div>''', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# TAB: COMPETITION (Leaderboards)
# ═══════════════════════════════════════════════════════════════

def render_competition_tab(data: Dict):
    st.markdown('<div class="dashboard-title">COMPETITION</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="dashboard-subtitle">'
        'Experiment Leaderboard &bull; Policy Leaderboard &bull; Who\'s Winning?'
        '</div>',
        unsafe_allow_html=True,
    )

    results = data.get("results") or []
    completed = [r for r in results if r.get("status") == "completed"]

    if not completed:
        st.info("No completed experiments yet. Run some experiments first!")
        return

    section = st.radio(
        "Section:",
        ["\U0001f3c6 Experiment Leaderboard", "\U0001f3af Policy Leaderboard"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if section == "\U0001f3c6 Experiment Leaderboard":
        _render_experiment_leaderboard(completed)
    else:
        _render_policy_leaderboard(completed)


def _render_experiment_leaderboard(completed: List[dict]):
    st.markdown('<div class="section-heading">EXPERIMENT LEADERBOARD</div>', unsafe_allow_html=True)
    st.markdown(
        '<p style="color: var(--color-text); margin-bottom: 15px;">'
        'All completed experiments ranked by primary metric improvement. Best first.'
        '</p>',
        unsafe_allow_html=True,
    )

    # Parse and rank experiments
    ranked = []
    for r in completed:
        conc = _parse_conclusion(r)
        improvement = conc.get("primary_metric_improvement", 0)
        if improvement is None:
            improvement = 0
        ranked.append({"result": r, "conclusion": conc, "improvement": float(improvement)})

    ranked.sort(key=lambda x: x["improvement"], reverse=True)

    # Bar chart of top experiments
    top_n = min(20, len(ranked))
    chart_data = ranked[:top_n]

    fig = go.Figure(go.Bar(
        y=[f"#{i+1} {STRATEGY_SHORT.get(d['result'].get('strategy', ''), '?')}"
           f"\u00d7{METHOD_SHORT.get(d['result'].get('method', ''), '?')}"
           for i, d in enumerate(chart_data)],
        x=[d["improvement"] for d in chart_data],
        orientation="h",
        marker_color=["#00ff41" if d["improvement"] >= 0 else "#ff5555" for d in chart_data],
        text=[f"{d['improvement']:+.2f}%" for d in chart_data],
        textposition="auto",
        textfont=dict(color="white"),
    ))
    fig.add_vline(x=0, line_color="#555")
    fig.update_layout(**_plotly_layout(
        margin=dict(l=140, r=20, t=10, b=40),
        height=max(300, top_n * 32),
        xaxis=dict(title="Improvement %", gridcolor="rgba(0, 255, 65, 0.1)"),
        yaxis=dict(gridcolor="rgba(0, 255, 65, 0.1)", autorange="reversed"),
    ))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("<br>", unsafe_allow_html=True)

    # Expandable cards for each experiment
    for i, entry in enumerate(ranked):
        r = entry["result"]
        conc = entry["conclusion"]
        imp = entry["improvement"]

        strategy_label = STRATEGY_LABELS.get(r.get("strategy", ""), r.get("strategy", "?"))
        method_label = METHOD_LABELS.get(r.get("method", ""), r.get("method", "?"))
        server = r.get("server_hostname", "unknown")
        confidence = conc.get("confidence", 0)
        if confidence is None:
            confidence = 0
        winner = conc.get("winner", "N/A")

        imp_color = "text-ok" if imp >= 0 else "text-error"
        rank_label = f"#{i + 1}"
        medal = ""
        if i == 0:
            medal = " GOLD"
        elif i == 1:
            medal = " SILVER"
        elif i == 2:
            medal = " BRONZE"

        header = (
            f"{rank_label}{medal} | {strategy_label} \u00d7 {method_label} | "
            f"{server} | {imp:+.2f}% improvement | {confidence:.0f}% confidence"
        )

        with st.expander(header, expanded=(i < 3)):
            # Summary
            summary = conc.get("summary", "No summary available.")
            st.markdown(
                f'<div class="experiment-card">'
                f'<p style="color: var(--nexus-primary); font-weight: 600;">Summary</p>'
                f'<p style="color: var(--color-text); line-height: 1.7;">{summary}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Winner and key stats
            iters = conc.get("iterations_completed", "?")
            wall_time = r.get("wall_time_seconds", 0)
            wall_min = wall_time / 60 if wall_time else 0
            cycle_num = r.get("cycle_number", "?")

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(
                    f'<div class="metric-card"><div class="metric-label">Winner</div>'
                    f'<div class="metric-value-sm">{winner}</div></div>',
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    f'<div class="metric-card"><div class="metric-label">Iterations</div>'
                    f'<div class="metric-value-sm">{iters}</div></div>',
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(
                    f'<div class="metric-card"><div class="metric-label">Wall Time</div>'
                    f'<div class="metric-value-sm">{wall_min:.1f}m</div></div>',
                    unsafe_allow_html=True,
                )
            with c4:
                st.markdown(
                    f'<div class="metric-card"><div class="metric-label">Cycle</div>'
                    f'<div class="metric-value-sm">{cycle_num}</div></div>',
                    unsafe_allow_html=True,
                )

            # Per-action breakdown from metadata.all_results
            all_results = (conc.get("metadata") or {}).get("all_results", [])
            if all_results:
                st.markdown(
                    '<div class="section-heading" style="font-size: 0.9em;">PER-ACTION BREAKDOWN</div>',
                    unsafe_allow_html=True,
                )
                rows_html = ""
                for ar in all_results:
                    action = ar.get("action", "unknown")
                    ar_imp = ar.get("improvement", 0)
                    if ar_imp is None:
                        ar_imp = 0
                    p_val = ar.get("p_value", None)
                    sig = ar.get("significant", False)
                    base_mean = ar.get("baseline_mean", "?")
                    treat_mean = ar.get("treatment_mean", "?")

                    imp_cls = "text-ok" if ar_imp >= 0 else "text-error"
                    sig_icon = '<span class="text-ok">YES</span>' if sig else '<span class="text-warn">no</span>'
                    p_str = f"{p_val:.4f}" if p_val is not None else "N/A"

                    rows_html += (
                        f'<tr>'
                        f'<td><code>{action}</code></td>'
                        f'<td class="{imp_cls}">{ar_imp:+.2f}%</td>'
                        f'<td>{p_str}</td>'
                        f'<td>{sig_icon}</td>'
                        f'<td>{base_mean}</td>'
                        f'<td>{treat_mean}</td>'
                        f'</tr>'
                    )

                st.markdown(
                    f'<table class="wiki-table">'
                    f'<tr><th>Action/Policy</th><th>Improvement</th><th>p-value</th>'
                    f'<th>Significant?</th><th>Baseline Mean</th><th>Treatment Mean</th></tr>'
                    f'{rows_html}'
                    f'</table>',
                    unsafe_allow_html=True,
                )

            # Recommended actions
            rec_actions = conc.get("recommended_actions", [])
            if rec_actions:
                st.markdown(
                    '<div class="section-heading" style="font-size: 0.9em;">RECOMMENDED ACTIONS</div>',
                    unsafe_allow_html=True,
                )
                for ra in rec_actions:
                    if isinstance(ra, str):
                        st.markdown(f'<p style="color: var(--color-text);">&bull; <code>{ra}</code></p>', unsafe_allow_html=True)
                    elif isinstance(ra, dict):
                        st.markdown(f'<p style="color: var(--color-text);">&bull; <code>{json.dumps(ra)}</code></p>', unsafe_allow_html=True)


def _render_policy_leaderboard(completed: List[dict]):
    st.markdown('<div class="section-heading">POLICY LEADERBOARD</div>', unsafe_allow_html=True)
    st.markdown(
        '<p style="color: var(--color-text); margin-bottom: 15px;">'
        'Every unique action/policy ever tested, aggregated across all experiments. '
        'Which specific settings produce the best results?'
        '</p>',
        unsafe_allow_html=True,
    )

    # Extract all unique actions from all experiments
    policy_data: Dict[str, List[dict]] = {}

    for r in completed:
        conc = _parse_conclusion(r)
        all_results = (conc.get("metadata") or {}).get("all_results", [])
        for ar in all_results:
            action = ar.get("action", "")
            if not action:
                continue
            imp = ar.get("improvement", 0)
            if imp is None:
                imp = 0

            if action not in policy_data:
                policy_data[action] = []

            policy_data[action].append({
                "improvement": float(imp),
                "p_value": ar.get("p_value"),
                "significant": ar.get("significant", False),
                "baseline_mean": ar.get("baseline_mean"),
                "treatment_mean": ar.get("treatment_mean"),
                "strategy": r.get("strategy", "?"),
                "method": r.get("method", "?"),
                "server": r.get("server_hostname", "?"),
                "cycle": r.get("cycle_number", "?"),
                "experiment_id": r.get("id", "?"),
            })

    if not policy_data:
        st.info("No policy-level data found in experiment conclusions.")
        return

    # Aggregate per policy
    aggregated = []
    for action, entries in policy_data.items():
        improvements = [e["improvement"] for e in entries]
        aggregated.append({
            "action": action,
            "avg_improvement": sum(improvements) / len(improvements),
            "best_improvement": max(improvements),
            "worst_improvement": min(improvements),
            "times_tested": len(entries),
            "entries": entries,
        })

    aggregated.sort(key=lambda x: x["avg_improvement"], reverse=True)

    # Bar chart
    top_n = min(25, len(aggregated))
    chart_items = aggregated[:top_n]

    fig = go.Figure(go.Bar(
        y=[_truncate_action(a["action"], 50) for a in chart_items],
        x=[a["avg_improvement"] for a in chart_items],
        orientation="h",
        marker_color=["#00ff41" if a["avg_improvement"] >= 0 else "#ff5555" for a in chart_items],
        text=[f"{a['avg_improvement']:+.2f}% (n={a['times_tested']})" for a in chart_items],
        textposition="auto",
        textfont=dict(color="white", size=10),
    ))
    fig.add_vline(x=0, line_color="#555")
    fig.update_layout(**_plotly_layout(
        margin=dict(l=300, r=20, t=10, b=40),
        height=max(350, top_n * 32),
        xaxis=dict(title="Avg Improvement %", gridcolor="rgba(0, 255, 65, 0.1)"),
        yaxis=dict(gridcolor="rgba(0, 255, 65, 0.1)", autorange="reversed"),
    ))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("<br>", unsafe_allow_html=True)

    # Expandable cards for each policy
    for i, agg in enumerate(aggregated):
        action = agg["action"]
        avg_imp = agg["avg_improvement"]
        best_imp = agg["best_improvement"]
        worst_imp = agg["worst_improvement"]
        count = agg["times_tested"]
        entries = agg["entries"]

        medal = ""
        if i == 0:
            medal = " GOLD"
        elif i == 1:
            medal = " SILVER"
        elif i == 2:
            medal = " BRONZE"

        # Parse action for human-readable description
        method_name, description = _parse_action_description(action)

        header = (
            f"#{i+1}{medal} | {_truncate_action(action, 60)} | "
            f"avg {avg_imp:+.2f}% | tested {count}x | best {best_imp:+.2f}%"
        )

        with st.expander(header, expanded=(i < 3)):
            # What this policy does
            st.markdown(
                f'<div class="experiment-card">'
                f'<p style="color: var(--nexus-primary); font-weight: 600;">What This Policy Does</p>'
                f'<p style="color: var(--color-text); line-height: 1.7;">'
                f'<strong>Method:</strong> {METHOD_LABELS.get(method_name, method_name)}<br>'
                f'<strong>Action:</strong> <code>{action}</code><br>'
                f'{description}'
                f'</p></div>',
                unsafe_allow_html=True,
            )

            # Stats
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(
                    f'<div class="metric-card"><div class="metric-label">Avg Improvement</div>'
                    f'<div class="metric-value-sm" style="color: {"var(--color-ok)" if avg_imp >= 0 else "var(--color-error)"}">'
                    f'{avg_imp:+.2f}%</div></div>',
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    f'<div class="metric-card"><div class="metric-label">Best</div>'
                    f'<div class="metric-value-sm">{best_imp:+.2f}%</div></div>',
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(
                    f'<div class="metric-card"><div class="metric-label">Worst</div>'
                    f'<div class="metric-value-sm">{worst_imp:+.2f}%</div></div>',
                    unsafe_allow_html=True,
                )
            with c4:
                st.markdown(
                    f'<div class="metric-card"><div class="metric-label">Times Tested</div>'
                    f'<div class="metric-value-sm">{count}</div></div>',
                    unsafe_allow_html=True,
                )

            # All experiments where this policy was tested
            st.markdown(
                '<div class="section-heading" style="font-size: 0.9em;">EXPERIMENTS WITH THIS POLICY</div>',
                unsafe_allow_html=True,
            )
            rows_html = ""
            for e in sorted(entries, key=lambda x: x["improvement"], reverse=True):
                imp_cls = "text-ok" if e["improvement"] >= 0 else "text-error"
                strat_label = STRATEGY_SHORT.get(e["strategy"], e["strategy"])
                meth_label = METHOD_SHORT.get(e["method"], e["method"])
                sig_icon = '<span class="text-ok">YES</span>' if e["significant"] else '<span class="text-warn">no</span>'
                p_str = f"{e['p_value']:.4f}" if e["p_value"] is not None else "N/A"

                rows_html += (
                    f'<tr>'
                    f'<td>{strat_label} \u00d7 {meth_label}</td>'
                    f'<td>{e["server"]}</td>'
                    f'<td>Cycle {e["cycle"]}</td>'
                    f'<td class="{imp_cls}">{e["improvement"]:+.2f}%</td>'
                    f'<td>{p_str}</td>'
                    f'<td>{sig_icon}</td>'
                    f'</tr>'
                )

            st.markdown(
                f'<table class="wiki-table">'
                f'<tr><th>Strategy \u00d7 Method</th><th>Server</th><th>Cycle</th>'
                f'<th>Improvement</th><th>p-value</th><th>Significant?</th></tr>'
                f'{rows_html}'
                f'</table>',
                unsafe_allow_html=True,
            )


def _truncate_action(action: str, max_len: int = 50) -> str:
    """Truncate action string for display."""
    if len(action) <= max_len:
        return action
    return action[:max_len - 3] + "..."


def _parse_action_description(action: str) -> tuple:
    """Parse an action name like 'set_io_scheduler(scheduler=kyber)' into method + human description."""
    method_name = "unknown"
    description = ""

    action_lower = action.lower()

    if "io_scheduler" in action_lower or "scheduler" in action_lower:
        method_name = "io_scheduler"
        description = "Changes the disk I/O scheduling algorithm. Controls how disk access is prioritized between competing programs."
    elif "power" in action_lower or "governor" in action_lower or "frequency" in action_lower or "rapl" in action_lower:
        method_name = "power_state"
        description = "Adjusts CPU power settings &mdash; governor, frequency limits, or power caps. Trades off performance vs. energy consumption."
    elif "memory" in action_lower or "hugepage" in action_lower or "swap" in action_lower or "numa" in action_lower:
        method_name = "memory_manager"
        description = "Modifies memory management settings &mdash; page sizes, swap behavior, or NUMA placement. Optimizes RAM access patterns."
    elif "forecast" in action_lower or "predict" in action_lower:
        method_name = "forecaster"
        description = "Configures the predictive pre-configuration engine. Adjusts how far ahead the system looks and how aggressively it pre-adapts."
    else:
        description = "System-level configuration change."

    # Try to extract params from parentheses
    if "(" in action and ")" in action:
        params_str = action[action.index("(") + 1:action.rindex(")")]
        if params_str:
            description += f"<br><strong>Parameters:</strong> <code>{params_str}</code>"

    return method_name, description


# ═══════════════════════════════════════════════════════════════
# ANALYSIS TAB: Per-Strategy & Per-Method Box Plots
# ═══════════════════════════════════════════════════════════════

def render_improvement_box_plots(completed: List[dict]):
    """
    Insert this into render_analysis_tab() after the Strategy×Method bar chart,
    before the Duration section.

    Call as: render_improvement_box_plots(completed)
    where `completed` is the list of completed experiment results.
    """
    if not completed:
        return

    # Build dataframe
    box_data = []
    for r in completed:
        conc = _parse_conclusion(r)
        imp = conc.get("primary_metric_improvement", 0)
        if imp is None:
            imp = 0
        box_data.append({
            "strategy": STRATEGY_SHORT.get(r.get("strategy", ""), "?"),
            "method": METHOD_SHORT.get(r.get("method", ""), "?"),
            "improvement": float(imp),
        })

    if not box_data:
        return

    df = pd.DataFrame(box_data)

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    # ── Per-Strategy Box Plot ──
    with col1:
        st.markdown('<div class="section-heading">IMPROVEMENT BY STRATEGY</div>', unsafe_allow_html=True)

        strategy_colors = {
            "Shadow": "#8be9fd",
            "A/B": "#bd93f9",
            "Thompson": "#f97316",
            "Bayesian": "#00ff41",
        }

        fig_strat = go.Figure()
        for strat in df["strategy"].unique():
            strat_data = df[df["strategy"] == strat]["improvement"]
            fig_strat.add_trace(go.Box(
                y=strat_data,
                name=strat,
                marker_color=strategy_colors.get(strat, "#00ff41"),
                boxmean="sd",
                line=dict(width=1.5),
            ))

        fig_strat.add_hline(y=0, line_dash="dash", line_color="#555", annotation_text="baseline")
        fig_strat.update_layout(**_plotly_layout(
            margin=dict(l=50, r=20, t=10, b=40),
            height=350,
            yaxis=dict(title="Improvement %", gridcolor="rgba(0, 255, 65, 0.1)"),
            xaxis=dict(gridcolor="rgba(0, 255, 65, 0.1)"),
            showlegend=False,
        ))
        st.plotly_chart(fig_strat, use_container_width=True, config={"displayModeBar": False})

    # ── Per-Method Box Plot ──
    with col2:
        st.markdown('<div class="section-heading">IMPROVEMENT BY METHOD</div>', unsafe_allow_html=True)

        method_colors = {
            "Power": "#ff79c6",
            "I/O": "#f1fa8c",
            "Memory": "#8be9fd",
            "Forecast": "#f97316",
        }

        fig_meth = go.Figure()
        for meth in df["method"].unique():
            meth_data = df[df["method"] == meth]["improvement"]
            fig_meth.add_trace(go.Box(
                y=meth_data,
                name=meth,
                marker_color=method_colors.get(meth, "#00ff41"),
                boxmean="sd",
                line=dict(width=1.5),
            ))

        fig_meth.add_hline(y=0, line_dash="dash", line_color="#555", annotation_text="baseline")
        fig_meth.update_layout(**_plotly_layout(
            margin=dict(l=50, r=20, t=10, b=40),
            height=350,
            yaxis=dict(title="Improvement %", gridcolor="rgba(0, 255, 65, 0.1)"),
            xaxis=dict(gridcolor="rgba(0, 255, 65, 0.1)"),
            showlegend=False,
        ))
        st.plotly_chart(fig_meth, use_container_width=True, config={"displayModeBar": False})
