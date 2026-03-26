# ZON ERAD Experiment Dashboard

Live monitoring dashboard for the ERAD (Evaluate-Recommend-Adapt-Discover) experiment engine. Built with Streamlit, matching the Construct CSS theme (Matrix Green).

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![Temporal](https://img.shields.io/badge/Temporal-000000?style=flat&logo=temporal&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=flat&logo=supabase&logoColor=white)

## Features

| Tab | Description |
|-----|-------------|
| **Overview** | Live experiment status, cycle progress, strategy×method heatmap, knowledge base |
| **Experiments** | Full experiment results with filters, policies deployed, iteration logs, winners |
| **Analysis** | Trend charts, convergence analysis, fitness evolution, strategy comparison |
| **Servers** | Per-server experiment history, method breakdown, performance impact |
| **Activity Log** | Temporal workflow events, timeline, raw data export |
| **Wiki** | ERAD glossary, strategy reference, method reference, how-it-works guide |

## Data Sources

- **Temporal**: Queries `erad-experiment-loop-v2` workflow for live status, progress, knowledge
- **Supabase**: `experiment_results`, `strategy_method_effectiveness`, `config_evolution` tables (erad schema)

## Quick Start (bizon1)

```bash
# SSH into bizon1
ssh bizon1

# Clone
git clone https://github.com/alexbernal/zon-erad-dashboard.git
cd zon-erad-dashboard

# Install deps (use the ERAD venv or create a new one)
pip install -r requirements.txt

# Create secrets
mkdir -p .streamlit
cat > .streamlit/secrets.toml << 'EOF'
SUPABASE_URL = "http://127.0.0.1:31443"
SUPABASE_KEY = "<your-service-role-key>"
TEMPORAL_ADDRESS = "localhost:31733"
TEMPORAL_NAMESPACE = "default"
EOF

# Run
streamlit run app.py
```

Dashboard will be available at `http://100.125.67.87:8501` via Tailscale.

## Run in tmux (persistent)

```bash
tmux new-session -d -s erad-dashboard 'cd ~/zon-erad-dashboard && streamlit run app.py'
```

## Architecture

```
┌─────────────────────┐     ┌─────────────────┐
│  Streamlit Dashboard │────▶│  Temporal        │  (workflow queries)
│  (bizon1:8501)       │     │  (bizon1:31733)  │
│                      │     └─────────────────┘
│                      │     ┌─────────────────┐
│                      │────▶│  Supabase        │  (experiment data)
│                      │     │  (bizon1:31443)  │
└─────────────────────┘     └─────────────────┘
```

## Theme

Construct CSS — Matrix green (`#00ff41`), dark background (`#0a0f0a`), JetBrains Mono font. Matches the existing [ZON Metrics Dashboard](https://zon-metrics-probe-opt-ab.streamlit.app/).

## License

Internal use — ZON Energy
