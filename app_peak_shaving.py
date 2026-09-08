"""Dedicated Peak Shaving Simulator - Streamlit.

Based on the Battery Sizer project, but focused only on demand-peak reduction.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from loaders import load_meter_file
from peak_shaving_engine import find_min_sustainable_target, top_peaks_table

st.set_page_config(
    page_title="Peak Shaving Simulator",
    page_icon="⚡",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {max-width: 1500px; padding-top: 1.6rem; padding-bottom: 2rem;}
    .ps-title {font-size:2rem;font-weight:850;margin-bottom:.15rem;}
    .ps-sub {color:#94a3b8;margin-bottom:1.2rem;}
    .ps-grid {display:grid;grid-template-columns:repeat(5,minmax(160px,1fr));gap:12px;margin:14px 0;}
    .ps-card {background:linear-gradient(180deg,rgba(15,23,42,.96),rgba(2,6,23,.9));
              border:1px solid rgba(148,163,184,.2);border-radius:14px;padding:16px 18px;min-height:118px;}
    .ps-label {font-size:.88rem;font-weight:700;color:#e5e7eb;margin-bottom:12px;}
    .ps-value {font-size:1.8rem;font-weight:850;line-height:1.05;}
    .ps-subv {color:#94a3b8;font-size:.78rem;margin-top:8px;}
    .blue{color:#4f8cff}.green{color:#4ade80}.orange{color:#fb923c}.purple{color:#a855f7}.red{color:#ff6b6b}
    @media(max-width:1100px){.ps-grid{grid-template-columns:repeat(2,minmax(160px,1fr));}}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="ps-title">⚡ Peak Shaving Simulator</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="ps-sub">Analyse de la puissance quart-horaire et recherche automatique du seuil minimal soutenable par une batterie.</div>',
    unsafe_allow_html=True,
)

# --------------------------------------------------------------- Sidebar
st.sidebar.header("Paramètres")

st.sidebar.markdown("**Batterie**")
capacity_kWh = st.sidebar.number_input(
    "Capacité nominale (kWh)", min_value=1.0, value=610.0, step=10.0, format="%.1f"
)
charge_power_kW = st.sidebar.number_input(
    "Puissance de charge (kW)", min_value=1.0, value=300.0, step=10.0, format="%.1f"
)
discharge_power_kW = st.sidebar.number_input(
    "Puissance de décharge (kW)", min_value=1.0, value=300.0, step=10.0, format="%.1f"
)
roundtrip_eff = st.sidebar.slider(
    "Rendement aller-retour", min_value=0.50, max_value=1.00, value=0.80, step=0.01
)
soc_min_pct = st.sidebar.slider(
    "SOC minimum (%)", min_value=0, max_value=50, value=10, step=5
)
reserve_target_pct = st.sidebar.slider(
    "Réserve Peak Shaving cible (%)",
    min_value=10, max_value=100, value=80, step=5,
    help=(
        "SOC que le contrôleur cherche à restaurer avant les pointes. "
        "La batterie peut descendre jusqu'au SOC minimum pendant l'écrêtage."
    ),
)
grid_recharge = st.sidebar.checkbox(
    "Autoriser la recharge depuis le réseau",
    value=True,
    help="La recharge réseau utilise seulement la marge disponible sous le seuil afin de ne pas créer une nouvelle pointe.",
)

st.sidebar.markdown("**Facturation Groupe E**")
billing_label = st.sidebar.selectbox(
    "Mode de facturation",
    [
        "Bande annuelle",
        "Maximum mensuel",
    ],
    index=0,
)
billing_mode = "annual_band" if billing_label == "Bande annuelle" else "monthly_max"
power_tariff = st.sidebar.number_input(
    "Tarif puissance (CHF/kW/mois)",
    min_value=0.0, value=5.10, step=0.10, format="%.2f"
)
target_resolution = st.sidebar.selectbox(
    "Précision du seuil",
    [0.5, 1.0, 2.0, 5.0],
    index=1,
    format_func=lambda x: f"{x:.1f} kW",
)

uploaded = st.file_uploader(
    "Courbe de charge (Excel ou CSV avec date/heure, import et export)",
    type=["xlsx", "xls", "csv"],
)

if not uploaded:
    st.info("Charge une courbe de puissance pour lancer l'analyse.")
    st.stop()

@st.cache_data(show_spinner=False)
def _load(name: str, data: bytes):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / name
        p.write_bytes(data)
        # For this dedicated tool, uploaded import/export values are expected to
        # represent power when the headers indicate kW. The reused loader detects this.
        return load_meter_file(p, data_unit="auto")

try:
    df, meta = _load(uploaded.name, uploaded.getvalue())
except Exception as e:
    st.error(f"Impossible de lire le fichier : {e}")
    st.stop()

if df.empty:
    st.error("Aucune donnée exploitable.")
    st.stop()

dt_hours = float(meta.dt_hours)
measured_peak = float(df["import_kWh"].max() / dt_hours) if dt_hours > 0 else 0.0

st.caption(
    f"Source détectée : **{meta.vendor}** · pas de temps : **{dt_hours*60:.0f} min** · "
    f"{meta.n_rows:,} points · unité appliquée : **{meta.data_unit}**"
)

with st.spinner("Recherche du seuil Peak Shaving minimal soutenable..."):
    result = find_min_sustainable_target(
        df["import_kWh"].values,
        df["export_kWh"].values,
        df["timestamp"].values,
        dt_hours=dt_hours,
        capacity_kWh=capacity_kWh,
        charge_power_kW=charge_power_kW,
        discharge_power_kW=discharge_power_kW,
        roundtrip_eff=roundtrip_eff,
        soc_min_pct=soc_min_pct,
        reserve_target_pct=reserve_target_pct,
        grid_recharge=grid_recharge,
        target_resolution_kW=target_resolution,
        tariff_chf_per_kw_month=power_tariff,
        billing_mode=billing_mode,
    )

def f0(v):
    return f"{float(v):,.0f}".replace(",", " ")

def f1(v):
    return f"{float(v):,.1f}".replace(",", " ")

def _limiter_text(reason: str) -> str:
    labels = {
        "power": "puissance de décharge maximale atteinte",
        "energy": "énergie disponible / SOC minimum limitant",
        "power_and_energy": "puissance et énergie toutes deux limitantes",
        "sequence": "succession de pointes / réserve insuffisamment restaurée",
        "boundary": "intervalle le plus proche de la limite soutenable",
        "other": "combinaison de contraintes",
    }
    return labels.get(str(reason), "combinaison de contraintes")

st.markdown(
    f"""
    <div class="ps-grid">
      <div class="ps-card"><div class="ps-label">Pointe avant</div><div class="ps-value orange">{f1(result.peak_before_kW)} kW</div><div class="ps-subv">Maximum mesuré</div></div>
      <div class="ps-card"><div class="ps-label">Seuil soutenable</div><div class="ps-value green">{f1(result.target_kW)} kW</div><div class="ps-subv">Trouvé automatiquement</div></div>
      <div class="ps-card"><div class="ps-label">Pointe après</div><div class="ps-value green">{f1(result.peak_after_kW)} kW</div><div class="ps-subv">Après simulation annuelle</div></div>
      <div class="ps-card"><div class="ps-label">Écrêtage garanti</div><div class="ps-value blue">{f1(result.reduction_kW)} kW</div><div class="ps-subv">Réduction du maximum</div></div>
      <div class="ps-card"><div class="ps-label">Économie puissance</div><div class="ps-value green">{f0(result.annual_saving_chf)} CHF/an</div><div class="ps-subv">{power_tariff:.2f} CHF/kW/mois</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

annual_cost_before = result.peak_before_kW * power_tariff * 12.0
annual_cost_after = result.peak_after_kW * power_tariff * 12.0

b1, b2, b3 = st.columns(3)
b1.metric(
    "Configuration batterie",
    f"{capacity_kWh:.0f} kWh / {discharge_power_kW:.0f} kW",
    help="Capacité nominale et puissance de décharge utilisées pour la simulation."
)
b2.metric(
    "Coût puissance avant",
    f"{annual_cost_before:,.0f} CHF/an".replace(",", " "),
    help=f"{result.peak_before_kW:.1f} kW × {power_tariff:.2f} CHF/kW/mois × 12"
)
b3.metric(
    "Coût puissance après",
    f"{annual_cost_after:,.0f} CHF/an".replace(",", " "),
    delta=f"-{result.annual_saving_chf:,.0f} CHF/an".replace(",", " "),
    help=f"{result.peak_after_kW:.1f} kW × {power_tariff:.2f} CHF/kW/mois × 12"
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Énergie déchargée", f"{f0(result.battery_discharge_kWh)} kWh")
c2.metric("Recharge réseau", f"{f0(result.grid_charge_kWh)} kWh")
c3.metric("Recharge PV", f"{f0(result.pv_charge_kWh)} kWh")
c4.metric("SOC minimum simulé", f"{np.min(result.soc_pct):.0f} %")

power_headroom = max(discharge_power_kW - result.critical_discharge_kW, 0.0)
soc_headroom = max(result.critical_soc_pct - soc_min_pct, 0.0)
d1, d2 = st.columns(2)
d1.metric(
    "Marge puissance à l'intervalle limitant",
    f"{power_headroom:.1f} kW",
    help="Faible marge = augmenter les kW de la batterie peut améliorer l'écrêtage."
)
d2.metric(
    "Marge SOC à l'intervalle limitant",
    f"{soc_headroom:.1f} points",
    help="Faible marge = augmenter les kWh / l'énergie disponible peut améliorer l'écrêtage."
)

st.subheader("Pourquoi ne peut-on pas descendre plus bas ?")
st.error(
    f"**{result.failed_target_kW:.1f} kW n'est pas soutenable.** "
    f"Premier échec : **{result.failed_timestamp:%d.%m.%Y %H:%M}** — "
    f"{_limiter_text(result.failed_reason)}. "
    f"La puissance réseau atteint **{result.failed_after_kW:.1f} kW**, soit "
    f"**{result.failed_shortfall_kW:.1f} kW** au-dessus de la cible. "
    f"Décharge batterie : **{result.failed_discharge_kW:.1f} kW** ; "
    f"SOC : **{result.failed_soc_pct:.1f} %**."
)

if result.failed_reason == "power":
    st.warning(
        "Diagnostic : la limite vient principalement des **kW de décharge**. "
        "Augmenter la puissance batterie peut réduire davantage la bande."
    )
elif result.failed_reason == "energy":
    st.warning(
        "Diagnostic : la limite vient principalement des **kWh disponibles / SOC**. "
        "Augmenter la capacité énergétique peut réduire davantage la bande."
    )
elif result.failed_reason == "power_and_energy":
    st.warning(
        "Diagnostic : **kW et kWh sont tous deux limitants** sur le premier seuil impossible."
    )
else:
    st.warning(
        "Diagnostic : le seuil inférieur échoue à cause d'une **séquence de pointes** "
        "et de la capacité de la batterie à restaurer sa réserve entre elles."
    )

# --------------------------------------------------------------- Overview chart
ts = pd.to_datetime(df["timestamp"])
before_kw = df["import_kWh"].to_numpy(float) / dt_hours
after_kw = result.import_after_kWh_series / dt_hours
dis_kw = result.battery_discharge_kWh_series / dt_hours

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=ts, y=before_kw, name="Puissance avant", mode="lines",
    line=dict(color="#fb923c", width=1.3),
))
fig.add_trace(go.Scatter(
    x=ts, y=after_kw, name="Puissance après", mode="lines",
    line=dict(color="#4ade80", width=1.6),
))
fig.add_hline(
    y=result.target_kW, line_dash="dash", line_color="#4f8cff",
    annotation_text=f"Seuil {result.target_kW:.1f} kW",
)
fig.update_layout(
    title="Puissance réseau avant / après Peak Shaving",
    xaxis_title="Date",
    yaxis_title="kW",
    height=470,
    hovermode="x unified",
    legend=dict(orientation="h", y=1.08),
)
st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------------------- Critical day chart
crit_ts = pd.Timestamp(result.failed_timestamp) if result.failed_timestamp is not None else ts.iloc[before_kw.argmax()]
day = crit_ts.normalize()
mask = ts.dt.normalize() == day

fig2 = go.Figure()
fig2.add_trace(go.Scatter(
    x=ts[mask], y=before_kw[mask], name="Avant", mode="lines+markers",
    line=dict(color="#fb923c", width=2.2),
))
fig2.add_trace(go.Scatter(
    x=ts[mask], y=after_kw[mask], name="Après", mode="lines+markers",
    line=dict(color="#4ade80", width=2.2),
))
fig2.add_trace(go.Scatter(
    x=ts[mask], y=dis_kw[mask], name="Décharge batterie", mode="lines",
    line=dict(color="#a855f7", width=2, dash="dot"),
))
fig2.add_hline(
    y=result.target_kW,
    line_dash="dash",
    line_color="#4f8cff",
    annotation_text=f"Garanti {result.target_kW:.1f} kW",
)
fig2.add_hline(
    y=result.failed_target_kW,
    line_dash="dot",
    line_color="#ff6b6b",
    annotation_text=f"Impossible {result.failed_target_kW:.1f} kW",
)
fig2.update_layout(
    title=f"Premier seuil impossible ({result.failed_target_kW:.1f} kW) : {crit_ts:%d.%m.%Y}",
    xaxis_title="Heure",
    yaxis_title="kW",
    height=430,
    hovermode="x unified",
    legend=dict(orientation="h", y=1.08),
)
st.plotly_chart(fig2, use_container_width=True)

# --------------------------------------------------------------- SOC chart
fig3 = go.Figure(go.Scatter(
    x=ts, y=result.soc_pct, name="SOC", mode="lines",
    line=dict(color="#a855f7", width=1.3),
))
fig3.add_hline(y=soc_min_pct, line_dash="dash", line_color="#ff6b6b",
               annotation_text=f"SOC min {soc_min_pct}%")
fig3.add_hline(y=reserve_target_pct, line_dash="dot", line_color="#4f8cff",
               annotation_text=f"Réserve cible {reserve_target_pct}%")
fig3.update_layout(
    title="État de charge de la batterie",
    xaxis_title="Date",
    yaxis_title="SOC (%)",
    yaxis=dict(range=[0, 100]),
    height=380,
)
st.plotly_chart(fig3, use_container_width=True)

# --------------------------------------------------------------- Top peaks
st.subheader("10 pointes les plus importantes")
top = top_peaks_table(df, result, dt_hours, n=10)
display = top.copy()
display["Date / heure"] = display["Date / heure"].dt.strftime("%d.%m.%Y %H:%M")
for c in ["Avant (kW)", "Après (kW)", "Décharge batterie (kW)", "SOC (%)", "Écrêtage (kW)"]:
    display[c] = display[c].round(1)
st.dataframe(display, use_container_width=True, hide_index=True)

# --------------------------------------------------------------- Monthly peak table
monthly = pd.DataFrame({
    "timestamp": ts,
    "Avant (kW)": before_kw,
    "Après (kW)": after_kw,
})
monthly["Période"] = monthly["timestamp"].dt.to_period("M")
monthly = monthly.groupby("Période")[["Avant (kW)", "Après (kW)"]].max()

# Reindex Jan-Dec of every year present so late-year months never disappear from display.
years = sorted(monthly.index.year.unique().tolist())
full_periods = []
for year in years:
    full_periods.extend(pd.period_range(f"{year}-01", f"{year}-12", freq="M"))
monthly = monthly.reindex(full_periods)
monthly.index.name = "Période"
monthly = monthly.reset_index()
monthly["Mois"] = monthly["Période"].astype(str)
monthly["Réduction (kW)"] = monthly["Avant (kW)"] - monthly["Après (kW)"]
monthly = monthly[["Mois", "Avant (kW)", "Après (kW)", "Réduction (kW)"]]
st.subheader("Pointes mensuelles")
st.dataframe(monthly.round(1), use_container_width=True, hide_index=True)
if billing_mode == "annual_band":
    st.caption(
        "En mode bande annuelle Groupe E, ces réductions mensuelles sont uniquement des diagnostics. "
        f"L'économie contractuelle retenue est calculée sur la baisse de la pointe annuelle : "
        f"{result.reduction_kW:.1f} kW × {power_tariff:.2f} CHF/kW/mois × 12 = "
        f"{result.annual_saving_chf:,.0f} CHF/an.".replace(",", " ")
    )
else:
    st.caption(
        "En mode maximum mensuel, l'économie est calculée mois par mois à partir des maxima mensuels."
    )

st.caption(
    f"Seuil garanti : {result.target_kW:.1f} kW. "
    f"Premier seuil inférieur testé : {result.failed_target_kW:.1f} kW, non soutenable. "
    "La recharge réseau est limitée par la puissance de charge et par la marge disponible sous le seuil. "
    "Le surplus PV est utilisé en priorité lorsqu'il est disponible."
)
