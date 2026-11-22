"""Visual layer: CSS theme, hero banner, KPI cards, section headers, Plotly template."""
from __future__ import annotations

import base64
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

ASSETS = Path(__file__).resolve().parent / "assets"

TEAL, TEAL_D, GREEN, AMBER, RED, INK, MUTED = "#0d9488", "#065f46", "#16a34a", "#f59e0b", "#dc2626", "#0f172a", "#64748b"
PALETTE = ["#0d9488", "#f59e0b", "#2563eb", "#16a34a", "#9333ea", "#dc2626", "#0891b2"]

# Hero background: original illustration (mountains, steam, sun) as inline SVG
_HERO_SVG = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 260' preserveAspectRatio='xMidYMid slice'>
<defs><linearGradient id='s' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#042f2e'/><stop offset='.55' stop-color='#0f766e'/><stop offset='1' stop-color='#14b8a6'/></linearGradient>
<radialGradient id='sun' cx='.5' cy='.5' r='.5'><stop offset='0' stop-color='#fde68a' stop-opacity='.95'/><stop offset='1' stop-color='#f59e0b' stop-opacity='0'/></radialGradient></defs>
<rect width='1200' height='260' fill='url(#s)'/>
<circle cx='980' cy='70' r='120' fill='url(#sun)'/>
<path d='M0 260 L170 140 L260 200 L420 90 L560 210 L700 120 L840 200 L980 110 L1200 230 L1200 260Z' fill='#022c22' opacity='.55'/>
<path d='M0 260 L120 200 L300 170 L460 220 L640 160 L820 230 L1000 180 L1200 240 L1200 260Z' fill='#011a14' opacity='.7'/>
<g fill='none' stroke='#ecfeff' stroke-width='5' stroke-linecap='round' opacity='.35'>
<path d='M420 88 c-18 -18 18 -28 0 -46 c-14 -14 10 -24 0 -36'/><path d='M445 92 c-18 -18 18 -28 0 -46'/>
<path d='M980 108 c-16 -16 16 -26 0 -42'/></g>
<g stroke='#99f6e4' stroke-width='2' opacity='.25'><line x1='0' y1='60' x2='1200' y2='60'/><line x1='0' y1='120' x2='1200' y2='120'/></g>
</svg>"""


def _b64(s: str | bytes) -> str:
    b = s.encode() if isinstance(s, str) else s
    return base64.b64encode(b).decode()


CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, button, input, textarea {{ font-family: 'Plus Jakarta Sans', sans-serif !important; }}
[data-testid="stAppViewContainer"] {{
  background: radial-gradient(1200px 500px at 100% -10%, #ccfbf1 0%, rgba(204,251,241,0) 60%),
              radial-gradient(900px 400px at -10% 110%, #fef3c7 0%, rgba(254,243,199,0) 60%), #f6f8fb;
}}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 1.2rem; max-width: 1400px; }}

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, #042f2e 0%, #064e3b 55%, #065f46 100%); }}
[data-testid="stSidebar"] * {{ color: #ecfdf5; }}
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{ padding-top: .6rem; }}
[data-testid="stSidebar"] .stNumberInput input, [data-testid="stSidebar"] [data-baseweb="input"] input {{ color: #0f172a !important; }}
[data-testid="stSidebar"] [data-testid="stExpander"] {{ background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.15); border-radius: 14px; }}
[data-testid="stSidebar"] [data-testid="stExpander"] details, [data-testid="stSidebar"] [data-testid="stExpander"] summary {{ background: transparent !important; }}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {{ background: rgba(255,255,255,.08) !important; }}
[data-testid="stSidebar"] [data-testid="stExpander"] summary p, [data-testid="stSidebar"] [data-testid="stExpander"] summary span {{ color:#ecfdf5 !important; font-weight:700; }}
[data-testid="stSidebar"] button {{ background: rgba(255,255,255,.12) !important; border: 1px solid rgba(255,255,255,.25) !important; }}
[data-testid="stSidebar"] button:hover {{ background: rgba(20,184,166,.45) !important; }}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {{ background: rgba(255,255,255,.08); border: 1px dashed rgba(255,255,255,.35); }}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button {{ color:#ecfdf5 !important; }}
[data-testid="stSidebar"] .element-container {{ margin-bottom: -.35rem; }}
.side-card {{ background: rgba(255,255,255,.08); border-radius: 12px; padding: 10px 12px; font-size: .78rem; line-height: 1.45; }}
.side-card b {{ color:#5eead4; }}

/* ---------- Hero ---------- */
.hero {{ position: relative; border-radius: 22px; overflow: hidden; padding: 28px 32px 26px; color: #fff; margin-bottom: 14px;
  background-image: url("data:image/svg+xml;base64,{_b64(_HERO_SVG)}"); background-size: cover; background-position: center;
  box-shadow: 0 18px 40px -18px rgba(4,47,46,.55); }}
.hero .row {{ display:flex; align-items:center; gap:18px; }}
.hero img {{ width:64px; height:64px; filter: drop-shadow(0 6px 14px rgba(0,0,0,.35)); }}
.hero h1 {{ font-size: 2.05rem; font-weight: 800; margin: 0; color:#fff; letter-spacing:-.5px; }}
.hero .sub {{ opacity:.88; font-size: .95rem; margin-top: 2px; }}
.hero .chips {{ margin-top: 14px; display:flex; flex-wrap:wrap; gap:8px; }}
.chip {{ background: rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.28); backdrop-filter: blur(6px);
  padding: 4px 11px; border-radius: 999px; font-size: .78rem; }}

/* ---------- Tabs ---------- */
.stTabs [data-baseweb="tab-list"] {{ gap: 6px; background: #ffffffcc; padding: 6px; border-radius: 14px;
  box-shadow: 0 4px 16px -10px rgba(15,23,42,.35); flex-wrap: wrap; }}
.stTabs [data-baseweb="tab"] {{ height: 40px; border-radius: 10px; padding: 0 14px; background: transparent; font-weight: 600; }}
.stTabs [aria-selected="true"] {{ background: linear-gradient(135deg,#0d9488,#065f46) !important; color: #fff !important; }}
.stTabs [aria-selected="true"] p, .stTabs [aria-selected="true"] span {{ color:#fff !important; }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display:none; }}

/* ---------- KPI cards ---------- */
.kpi-grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 6px 0 18px; }}
.kpi {{ background:#fff; border-radius: 18px; padding: 14px 14px 14px 18px; box-shadow: 0 10px 30px -18px rgba(15,23,42,.45);
  border: 1px solid #e2e8f0; position: relative; overflow: hidden; }}
.kpi:before {{ content:""; position:absolute; inset:0 auto 0 0; width:5px; background: var(--accent); }}
.kpi .ic {{ width:38px; height:38px; border-radius: 11px; display:flex; align-items:center; justify-content:center; font-size: 20px;
  background: var(--soft); margin-bottom: 8px; }}
.kpi .lb {{ color:{MUTED}; font-size:.7rem; font-weight:600; text-transform: uppercase; letter-spacing:.6px; }}
.kpi .vl {{ color:{INK}; font-size:1.3rem; font-weight:800; line-height:1.2; margin-top:2px; white-space: nowrap; }}
.kpi .dl {{ display:inline-block; margin-top:6px; font-size:.78rem; font-weight:700; padding:2px 9px; border-radius:999px; }}
.up {{ background:#dcfce7; color:#166534; }} .down {{ background:#fee2e2; color:#991b1b; }} .neu {{ background:#f1f5f9; color:#334155; }}
.rec {{ font-size:1.9rem !important; letter-spacing:1px; }}

/* ---------- Section header & cards ---------- */
.sec {{ display:flex; align-items:center; gap:12px; margin: 18px 0 10px; }}
.sec .bdg {{ width:40px; height:40px; border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:20px;
  background: linear-gradient(135deg,#ccfbf1,#99f6e4); box-shadow: inset 0 0 0 1px #5eead4; }}
.sec h3 {{ margin:0; font-size:1.25rem; font-weight:800; color:{INK}; }}
.sec .cap {{ color:{MUTED}; font-size:.85rem; }}
.card {{ background:#fff; border-radius:16px; padding:16px 18px; border:1px solid #e2e8f0; box-shadow: 0 8px 24px -18px rgba(15,23,42,.4); }}
.card h4 {{ margin:0 0 6px; font-size:1rem; }}
.card ul {{ margin: 0; padding-left: 1.1rem; }} .card li {{ margin: 3px 0; font-size:.9rem; }}
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {{ border-radius: 14px; overflow: hidden; box-shadow: 0 8px 24px -20px rgba(15,23,42,.5); }}
[data-testid="stPlotlyChart"] {{ background:#fff; border-radius: 16px; padding: 6px; border:1px solid #e2e8f0; box-shadow: 0 8px 24px -20px rgba(15,23,42,.5); }}
[data-testid="stMetric"] {{ background:#fff; border-radius: 14px; padding: 12px 14px; border:1px solid #e2e8f0; }}
.footer {{ text-align:center; color:{MUTED}; font-size:.78rem; margin: 28px 0 8px; }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def asset_b64(name: str) -> str:
    return _b64((ASSETS / name).read_bytes())


def hero(title: str, subtitle: str, chips: list[str]) -> None:
    chips_html = "".join(f"<span class='chip'>{c}</span>" for c in chips)
    st.markdown(
        f"""<div class="hero"><div class="row">
        <img src="data:image/svg+xml;base64,{asset_b64('icon.svg')}"/>
        <div><h1>{title}</h1><div class="sub">{subtitle}</div></div></div>
        <div class="chips">{chips_html}</div></div>""",
        unsafe_allow_html=True,
    )


def kpi_cards(items: list[dict]) -> None:
    """items: dict(icon, label, value, delta=None, tone='up'|'down'|'neu', accent, soft, cls='')"""
    html = ""
    for it in items:
        d = f"<span class='dl {it.get('tone', 'neu')}'>{it['delta']}</span>" if it.get("delta") else ""
        html += (f"<div class='kpi' style='--accent:{it.get('accent', TEAL)};--soft:{it.get('soft', '#ccfbf1')}'>"
                 f"<div class='ic'>{it['icon']}</div><div class='lb'>{it['label']}</div>"
                 f"<div class='vl {it.get('cls', '')}' style='color:{it.get('color', INK)}'>{it['value']}</div>{d}</div>")
    st.markdown(f"<div class='kpi-grid'>{html}</div>", unsafe_allow_html=True)


def section(icon: str, title: str, caption: str = "") -> None:
    cap = f"<div class='cap'>{caption}</div>" if caption else ""
    st.markdown(f"<div class='sec'><div class='bdg'>{icon}</div><div><h3>{title}</h3>{cap}</div></div>",
                unsafe_allow_html=True)


def card(title: str, bullets: list[str], icon: str = "") -> str:
    lis = "".join(f"<li>{b}</li>" for b in bullets)
    return f"<div class='card'><h4>{icon} {title}</h4><ul>{lis}</ul></div>"


def register_plotly_template() -> None:
    t = go.layout.Template()
    t.layout = go.Layout(
        font=dict(family="Plus Jakarta Sans, Segoe UI, Arial", color=INK, size=13),
        colorway=PALETTE, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="#e2e8f0", zerolinecolor="#cbd5e1"), yaxis=dict(gridcolor="#e2e8f0", zerolinecolor="#cbd5e1"),
        title=dict(font=dict(size=16, color=INK)), hoverlabel=dict(bgcolor="#0f172a", font_color="#fff"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    pio.templates["pgeo"] = t
    pio.templates.default = "plotly_white+pgeo"
