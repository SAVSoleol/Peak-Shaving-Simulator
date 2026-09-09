"""PDF report generation for the dedicated Peak Shaving Simulator.

Style intentionally follows the existing Soleol Battery Sizer report:
- black left sidebar;
- Soleol orange section titles;
- white KPI cards;
- blue = neutral information;
- green = positive / improvement;
- red = limitation / failed threshold.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from fpdf import FPDF

from peak_shaving_engine import top_peaks_table

SOLEOL_ORANGE = (233, 78, 53)
DARK = (0, 0, 0)
TEXT = (35, 35, 35)
MUTED = (100, 110, 120)
BLUE = (37, 99, 235)
GREEN = (34, 160, 85)
RED = (210, 55, 55)
LIGHT_BG = (248, 250, 252)
LIGHT_BLUE = (239, 246, 255)
LIGHT_GREEN = (236, 253, 245)
LIGHT_RED = (254, 242, 242)
BORDER = (220, 225, 230)

FOOTER_SIZE = 7


def _tx(s) -> str:
    repl = {
        "—": "-", "–": "-", "→": "->", "≥": ">=", "≤": "<=", "≈": "~",
        "•": "-", "’": "'", "…": "...", "œ": "oe",
    }
    s = str(s)
    for k, v in repl.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def _fmt0(v) -> str:
    return f"{float(v):,.0f}".replace(",", " ")


def _pdf_bytes(pdf: FPDF) -> bytes:
    out = pdf.output()
    return bytes(out) if isinstance(out, (bytes, bytearray)) else out.encode("latin-1")


class ReportPDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-10)
        self.set_font("Arial", "", FOOTER_SIZE)
        self.set_text_color(*MUTED)
        self.cell(0, 5, _tx("SOLEOL - Peak Shaving Simulator"), align="L")
        self.set_y(-10)
        self.cell(0, 5, _tx(f"Page {self.page_no()} / {{nb}}"), align="R")


def _resolve_header_image() -> str | None:
    candidates = [
        Path("rapport_header_montagnes.png"),
        Path(__file__).resolve().parent / "rapport_header_montagnes.png",
    ]
    for p in candidates:
        if p.is_file():
            return str(p)
    return None


def _resolve_logo_path(logo_path: str | None = None) -> str | None:
    candidates = []
    if logo_path:
        candidates.append(Path(logo_path))
    candidates.extend([
        Path("logo_soleol.png"), Path("logo_soleol.jpg"),
        Path("soleol_logo.png"), Path("soleol_logo.jpg"),
    ])
    for p in candidates:
        if p.is_file():
            return str(p)
    return None


def _side_bar(
    pdf: FPDF,
    *,
    client_name: str,
    source_name: str,
    coverage_days: float,
    capacity_kWh: float,
    discharge_power_kW: float,
    logo_path: str | None = None,
):
    pdf.set_fill_color(*DARK)
    pdf.rect(0, 0, 52, 297, style="F")

    logo = _resolve_logo_path(logo_path)
    if logo:
        pdf.image(logo, x=8, y=11, w=36)
    else:
        pdf.set_xy(8, 12)
        pdf.set_font("Arial", "B", 16)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(36, 8, "SOLEOL SA", ln=True)
        pdf.set_x(8)
        pdf.set_font("Arial", "", 8)
        pdf.set_text_color(230, 235, 240)
        pdf.cell(36, 5, _tx("ÉNERGIE SOLAIRE"), ln=True)

    pdf.set_draw_color(*SOLEOL_ORANGE)
    pdf.line(8, 60, 20, 60)

    pdf.set_xy(8, 66)
    pdf.set_font("Arial", "B", 7)
    pdf.set_text_color(255, 255, 255)
    pdf.multi_cell(36, 4.5, _tx("ÉTUDE\nPEAK SHAVING"))

    pdf.line(8, 84, 20, 84)

    infos = [
        ("CLIENT", client_name.strip() or "À renseigner"),
        ("GRD", "Groupe E"),
        ("PÉRIODE", f"{coverage_days:.0f} jours"),
        ("BATTERIE", f"{capacity_kWh:.0f} kWh / {discharge_power_kW:.0f} kW"),
        ("FICHIER", source_name),
    ]
    y = 92
    for label, value in infos:
        pdf.set_xy(8, y)
        pdf.set_font("Arial", "B", 7.2)
        pdf.set_text_color(*SOLEOL_ORANGE)
        pdf.cell(36, 4, _tx(label), ln=True)
        pdf.set_x(8)
        pdf.set_font("Arial", "", 7.8)
        pdf.set_text_color(255, 255, 255)
        pdf.multi_cell(36, 4, _tx(value))
        y += 18

    pdf.set_xy(8, 222)
    pdf.set_font("Arial", "B", 8.5)
    pdf.set_text_color(*SOLEOL_ORANGE)
    pdf.multi_cell(36, 4.2, _tx("Réduire les pointes,\noptimiser les coûts."))


def _section_title(pdf: FPDF, x: float, y: float, text: str):
    pdf.set_xy(x, y)
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*SOLEOL_ORANGE)
    pdf.cell(140, 6, _tx(text))


def _metric_box(
    pdf: FPDF,
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
    value: str,
    sub: str = "",
    color=BLUE,
    compact: bool = False,
):
    pdf.set_draw_color(*BORDER)
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(x, y, w, h, style="DF")

    if compact:
        label_y, value_y, sub_y = y + 3, y + 10.5, y + h - 6.5
        label_size, value_size, sub_size = 6.5, 12.4, 6.1
        label_line, sub_line = 3.3, 3.1
    else:
        label_y, value_y, sub_y = y + 4, y + 13, y + h - 9
        label_size, value_size, sub_size = 7.1, 14.2, 6.9
        label_line, sub_line = 3.6, 3.7

    pdf.set_xy(x + 4, label_y)
    pdf.set_font("Arial", "B", label_size)
    pdf.set_text_color(*TEXT)
    pdf.multi_cell(w - 8, label_line, _tx(label.upper()), align="L")

    pdf.set_xy(x + 4, value_y)
    pdf.set_font("Arial", "B", value_size)
    pdf.set_text_color(*color)
    pdf.cell(w - 8, 7, _tx(value))

    if sub:
        pdf.set_xy(x + 4, sub_y)
        pdf.set_font("Arial", "", sub_size)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(w - 8, sub_line, _tx(sub))


def _info_box(
    pdf: FPDF,
    x: float, y: float, w: float, h: float,
    title: str, text: str,
    fill, border,
):
    pdf.set_draw_color(*border)
    pdf.set_fill_color(*fill)
    pdf.rect(x, y, w, h, style="DF")
    pdf.set_xy(x + 5, y + 4)
    pdf.set_font("Arial", "B", 8)
    pdf.set_text_color(*border)
    pdf.cell(w - 10, 5, _tx(title))
    pdf.set_xy(x + 5, y + 11)
    pdf.set_font("Arial", "", 8.2)
    pdf.set_text_color(*TEXT)
    pdf.multi_cell(w - 10, 4, _tx(text))


def _plot_annual(df, result, dt_hours: float) -> BytesIO:
    ts = pd.to_datetime(df["timestamp"])
    before = np.asarray(df["import_kWh"], dtype=float) / dt_hours
    after = np.asarray(result.import_after_kWh_series, dtype=float) / dt_hours

    fig, ax = plt.subplots(figsize=(11, 3.1))
    ax.plot(ts, before, lw=0.85, color="#FB8C00", label="Puissance avant")
    ax.plot(ts, after, lw=0.95, color="#2EAD63", label="Puissance après")
    ax.axhline(result.target_kW, color="#2563EB", ls="--", lw=1.1, label=f"Seuil {result.target_kW:.0f} kW")
    ax.set_ylabel("kW", fontsize=9)
    ax.set_title("Puissance réseau avant / après Peak Shaving", fontsize=12, weight="bold", pad=6)
    ax.legend(ncol=3, fontsize=8.3, frameon=False, loc="upper center")
    ax.grid(alpha=.18)
    ax.tick_params(axis="both", labelsize=8)
    fig.subplots_adjust(left=0.075, right=0.995, top=0.83, bottom=0.17)
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=165, bbox_inches="tight", pad_inches=.03)
    plt.close(fig)
    buf.seek(0)
    return buf


def _plot_failed_day(df, result, dt_hours: float) -> BytesIO:
    ts = pd.to_datetime(df["timestamp"])
    day = pd.Timestamp(result.failed_timestamp).normalize()
    mask = ts.dt.normalize() == day

    before = np.asarray(df["import_kWh"], dtype=float)[mask] / dt_hours
    after_ok = np.asarray(result.import_after_kWh_series, dtype=float)[mask] / dt_hours
    discharge = np.asarray(result.battery_discharge_kWh_series, dtype=float)[mask] / dt_hours
    x = ts[mask]

    fig, ax = plt.subplots(figsize=(11, 3.1))
    ax.plot(x, before, "-o", ms=2, lw=1.6, color="#FB8C00", label="Avant")
    ax.plot(x, after_ok, "-o", ms=2, lw=1.5, color="#2EAD63", label="Après")
    ax.plot(x, discharge, lw=1.25, ls=":", color="#7C3AED", label="Décharge batterie")
    ax.axhline(result.target_kW, color="#2563EB", ls="--", lw=1.0, label=f"Garanti {result.target_kW:.0f} kW")
    ax.axhline(result.failed_target_kW, color="#D32F2F", ls=":", lw=1.0, label=f"Impossible {result.failed_target_kW:.0f} kW")
    ax.set_ylabel("kW", fontsize=9)
    ax.set_title(
        f"Premier seuil impossible - {pd.Timestamp(result.failed_timestamp):%d.%m.%Y}",
        fontsize=12, weight="bold", pad=8,
    )
    ax.legend(ncol=5, fontsize=7.8, frameon=False, loc="upper center")
    ax.grid(alpha=.18)
    ax.tick_params(axis="both", labelsize=8)
    fig.subplots_adjust(left=0.075, right=0.995, top=0.83, bottom=0.17)
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=165, bbox_inches="tight", pad_inches=.03)
    plt.close(fig)
    buf.seek(0)
    return buf


def _plot_soc(df, result, soc_min_pct: float, reserve_pct: float) -> BytesIO:
    ts = pd.to_datetime(df["timestamp"])
    fig, ax = plt.subplots(figsize=(11, 2.7))
    ax.plot(ts, result.soc_pct, lw=1.0, color="#7C3AED")
    ax.axhline(reserve_pct, color="#2563EB", ls=":", lw=1.0, label=f"Réserve cible {reserve_pct:.0f}%")
    ax.axhline(soc_min_pct, color="#D32F2F", ls="--", lw=1.0, label=f"SOC min {soc_min_pct:.0f}%")
    ax.set_ylim(0, 105)
    ax.set_ylabel("SOC (%)", fontsize=9)
    ax.set_title("État de charge de la batterie", fontsize=11.5, weight="bold", pad=5)
    ax.legend(ncol=2, fontsize=8, frameon=False, loc="upper center")
    ax.grid(alpha=.18)
    ax.tick_params(axis="both", labelsize=8)
    fig.subplots_adjust(left=0.075, right=0.995, top=0.82, bottom=0.18)
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=165, bbox_inches="tight", pad_inches=.03)
    plt.close(fig)
    buf.seek(0)
    return buf


def _page_1(
    pdf, *,
    client_name, source_name, coverage_days,
    capacity_kWh, charge_power_kW, discharge_power_kW,
    roundtrip_eff, soc_min_pct, reserve_target_pct,
    grid_recharge, power_tariff, result, logo_path=None,
):
    pdf.add_page()
    _side_bar(
        pdf,
        client_name=client_name,
        source_name=source_name,
        coverage_days=coverage_days,
        capacity_kWh=capacity_kWh,
        discharge_power_kW=discharge_power_kW,
        logo_path=logo_path,
    )

    x0 = 58

    # Header inspired by the approved mockup:
    # strong title on the left, panoramic Swiss landscape fading to white on the right.
    pdf.set_xy(x0, 13)
    pdf.set_font("Arial", "B", 18)
    pdf.set_text_color(*SOLEOL_ORANGE)
    pdf.cell(75, 8, _tx("Peak Shaving"))

    pdf.set_xy(x0, 22)
    pdf.set_font("Arial", "B", 13)
    pdf.set_text_color(*TEXT)
    pdf.cell(75, 6, _tx("Synthèse de l'étude"))

    header_image = _resolve_header_image()
    if header_image:
        pdf.image(header_image, x=x0 + 74, y=11, w=70, h=24)

    pdf.set_xy(x0, 37)
    pdf.set_font("Arial", "", 8.2)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(
        140, 4.2,
        _tx("Analyse de la puissance quart-horaire et recherche automatique "
            "du seuil minimal soutenable par une batterie.")
    )

    pdf.set_draw_color(*BORDER)
    pdf.line(x0, 51, x0 + 144, 51)

    _section_title(pdf, x0, 55, "RÉSULTATS PRINCIPAUX")

    annual_before = result.peak_before_kW * power_tariff * 12
    annual_after = result.peak_after_kW * power_tariff * 12

    # Principal results: 3 columns x 2 rows, larger and easier to read.
    w, gap, h = 46, 3, 31
    y1 = 66
    cards1 = [
        ("Pointe avant", f"{result.peak_before_kW:.0f} kW", "Maximum mesuré", BLUE),
        ("Seuil soutenable", f"{result.target_kW:.0f} kW", "Trouvé automatiquement", GREEN),
        ("Pointe après", f"{result.peak_after_kW:.0f} kW", "Après simulation annuelle", GREEN),
    ]
    for i, (lab, val, sub, col) in enumerate(cards1):
        _metric_box(pdf, x0 + i*(w+gap), y1, w, h, lab, val, sub, col)

    y2 = 102
    cards2 = [
        ("Écrêtage garanti", f"{result.reduction_kW:.0f} kW", "Réduction du maximum", GREEN),
        ("Coût puissance avant", f"{_fmt0(annual_before)} CHF/an", "Avant Peak Shaving", BLUE),
        ("Coût puissance après", f"{_fmt0(annual_after)} CHF/an", "Après écrêtage", GREEN),
    ]
    for i, (lab, val, sub, col) in enumerate(cards2):
        _metric_box(pdf, x0 + i*(w+gap), y2, w, h, lab, val, sub, col)

    # Main commercial result, visually dominant.
    pdf.set_draw_color(*GREEN)
    pdf.set_fill_color(*LIGHT_GREEN)
    pdf.rect(x0, 140, 144, 29, style="DF")
    pdf.set_xy(x0 + 5, 145)
    pdf.set_font("Arial", "B", 7.5)
    pdf.set_text_color(*GREEN)
    pdf.cell(134, 4, _tx("ÉCONOMIE ANNUELLE PEAK SHAVING"), align="C")
    pdf.set_xy(x0 + 5, 151)
    pdf.set_font("Arial", "B", 17)
    pdf.cell(134, 8, _tx(f"{_fmt0(result.annual_saving_chf)} CHF/an"), align="C")
    pdf.set_xy(x0 + 5, 160)
    pdf.set_font("Arial", "", 6.8)
    pdf.set_text_color(*MUTED)
    pdf.cell(
        134, 4,
        _tx(f"Réduction de {result.reduction_kW:.0f} kW sur la pointe annuelle - "
            f"{power_tariff:.2f} CHF/kW/mois"),
        align="C",
    )

    _section_title(pdf, x0, 176, "CONFIGURATION ET PARAMÈTRES")

    # Technical information: smaller cards, 4 columns x 2 rows.
    sw, sgap, sh = 35, 2, 27
    y3 = 187
    cards3 = [
        ("Capacité batterie", f"{capacity_kWh:.0f} kWh", "Paramètre de simulation", BLUE),
        ("Puissance charge", f"{charge_power_kW:.0f} kW", "Limite de charge", BLUE),
        ("Puissance décharge", f"{discharge_power_kW:.0f} kW", "Limite de décharge", BLUE),
        ("Rendement", f"{roundtrip_eff*100:.0f} %", "Aller-retour", BLUE),
    ]
    for i, (lab, val, sub, col) in enumerate(cards3):
        _metric_box(pdf, x0 + i*(sw+sgap), y3, sw, sh, lab, val, sub, col, compact=True)

    y4 = 219
    cards4 = [
        ("Énergie déchargée", f"{_fmt0(result.battery_discharge_kWh)} kWh", "Sur la période", BLUE),
        ("Recharge réseau", f"{_fmt0(result.grid_charge_kWh)} kWh", "Sous le seuil", BLUE),
        ("Recharge PV", f"{_fmt0(result.pv_charge_kWh)} kWh", "Surplus valorisé", GREEN),
        ("SOC minimum simulé", f"{np.min(result.soc_pct):.0f} %", f"SOC mini : {soc_min_pct:.0f} %", RED if np.min(result.soc_pct) <= soc_min_pct + 1 else BLUE),
    ]
    for i, (lab, val, sub, col) in enumerate(cards4):
        _metric_box(pdf, x0 + i*(sw+sgap), y4, sw, sh, lab, val, sub, col, compact=True)

    if result.failed_reason == "energy":
        limit_sentence = (
            f"La limite actuelle est principalement énergétique : le SOC minimum de "
            f"{soc_min_pct:.0f} % est atteint au premier seuil inférieur. Une capacité "
            f"en kWh plus importante pourrait permettre d'abaisser davantage la bande."
        )
    elif result.failed_reason == "power":
        limit_sentence = (
            "La limite actuelle vient principalement de la puissance de décharge. "
            "Une puissance batterie plus élevée pourrait permettre d'abaisser davantage la bande."
        )
    elif result.failed_reason == "power_and_energy":
        limit_sentence = (
            "La puissance et l'énergie sont toutes deux limitantes. Une augmentation des kW et des kWh "
            "serait nécessaire pour réduire davantage la bande."
        )
    else:
        limit_sentence = (
            "La limite est liée à une succession de pointes et à la restauration de la réserve. "
            "Une capacité supérieure et/ou une stratégie de recharge adaptée pourraient améliorer le résultat."
        )

    conclusion = (
        f"La batterie simulée de {capacity_kWh:.0f} kWh / {discharge_power_kW:.0f} kW "
        f"réduit la pointe réseau de {result.peak_before_kW:.0f} à {result.peak_after_kW:.0f} kW. "
        f"L'écrêtage garanti de {result.reduction_kW:.0f} kW représente environ "
        f"{_fmt0(result.annual_saving_chf)} CHF/an d'économie de puissance. "
        + limit_sentence
    )
    _info_box(pdf, x0, 250, 144, 31, "CONCLUSION", conclusion, LIGHT_BLUE, BLUE)


def _page_2(
    pdf, *,
    df, dt_hours, result,
    client_name, source_name, coverage_days,
    capacity_kWh, discharge_power_kW,
    soc_min_pct, reserve_target_pct, logo_path=None,
):
    pdf.add_page()
    _side_bar(
        pdf,
        client_name=client_name,
        source_name=source_name,
        coverage_days=coverage_days,
        capacity_kWh=capacity_kWh,
        discharge_power_kW=discharge_power_kW,
        logo_path=logo_path,
    )
    x0 = 58
    pdf.set_xy(x0, 14)
    pdf.set_font("Arial", "B", 17.5)
    pdf.set_text_color(*SOLEOL_ORANGE)
    pdf.cell(140, 8, _tx("ANALYSE DU PEAK SHAVING"))

    annual = _plot_annual(df, result, dt_hours)
    failed = _plot_failed_day(df, result, dt_hours)
    soc = _plot_soc(df, result, soc_min_pct, reserve_target_pct)

    pdf.image(annual, x=x0, y=29, w=144, h=59)
    pdf.image(failed, x=x0, y=91, w=144, h=64)
    pdf.image(soc, x=x0, y=158, w=144, h=44)

    reason = {
        "power": "la puissance de décharge maximale est atteinte",
        "energy": "le SOC minimum est atteint : l'énergie disponible devient limitante",
        "power_and_energy": "la puissance et l'énergie sont simultanément limitantes",
        "sequence": "une succession de pointes ne permet pas de restaurer suffisamment la réserve",
    }.get(result.failed_reason, "la configuration atteint sa limite")

    _failed_threshold_box(pdf, x0, 205, 144, 36, result)

    if result.failed_reason == "power":
        action = "Augmenter la puissance de décharge peut permettre d'abaisser davantage le seuil."
    elif result.failed_reason == "energy":
        action = "Augmenter la capacité énergétique peut permettre d'abaisser davantage le seuil."
    elif result.failed_reason == "power_and_energy":
        action = "Augmenter à la fois la puissance et la capacité est nécessaire pour abaisser davantage le seuil."
    else:
        action = "Augmenter la capacité et/ou optimiser la recharge de réserve peut permettre d'abaisser davantage le seuil."

    _info_box(pdf, x0, 246, 69, 27, "DIAGNOSTIC", reason.capitalize() + ".", LIGHT_BLUE, BLUE)
    _info_box(pdf, x0 + 75, 246, 69, 27, "ACTION POSSIBLE", action, LIGHT_GREEN, GREEN)


def _failed_threshold_box(pdf, x, y, w, h, result):
    pdf.set_draw_color(*RED)
    pdf.set_fill_color(*LIGHT_RED)
    pdf.rect(x, y, w, h, style="DF")

    pdf.set_xy(x + 5, y + 4)
    pdf.set_font("Arial", "B", 8.2)
    pdf.set_text_color(*RED)
    pdf.cell(w - 10, 5, _tx(f"PREMIER SEUIL IMPOSSIBLE : {result.failed_target_kW:.0f} kW"))

    rows = [
        ("Date et heure", pd.Timestamp(result.failed_timestamp).strftime("%d.%m.%Y à %H:%M")),
        ("Puissance réseau", f"{result.failed_after_kW:.1f} kW"),
        ("Dépassement de la cible", f"+{result.failed_shortfall_kW:.1f} kW"),
        ("Décharge batterie", f"{result.failed_discharge_kW:.1f} kW"),
        ("SOC atteint", f"{result.failed_soc_pct:.1f} %"),
    ]
    yy = y + 12
    for label, value in rows:
        pdf.set_xy(x + 6, yy)
        pdf.set_font("Arial", "B", 6.6)
        pdf.set_text_color(*TEXT)
        pdf.cell(48, 4, _tx(label))
        pdf.set_xy(x + 56, yy)
        pdf.set_font("Arial", "", 6.8)
        pdf.cell(w - 62, 4, _tx(value))
        yy += 4.5


def _table_header(pdf, x, y, widths, labels):
    pdf.set_xy(x, y)
    pdf.set_fill_color(*DARK)
    pdf.set_text_color(255,255,255)
    pdf.set_font("Arial", "B", 6.5)
    xx = x
    for w, label in zip(widths, labels):
        pdf.set_xy(xx, y)
        pdf.cell(w, 7, _tx(label), border=1, fill=True, align="C")
        xx += w


def _page_3(
    pdf, *,
    df, dt_hours, result, power_tariff,
    client_name, source_name, coverage_days,
    capacity_kWh, discharge_power_kW,
    roundtrip_eff, soc_min_pct, reserve_target_pct, grid_recharge, target_resolution_kW,
    logo_path=None,
):
    pdf.add_page()
    _side_bar(
        pdf,
        client_name=client_name,
        source_name=source_name,
        coverage_days=coverage_days,
        capacity_kWh=capacity_kWh,
        discharge_power_kW=discharge_power_kW,
        logo_path=logo_path,
    )
    x0 = 58
    pdf.set_xy(x0, 14)
    pdf.set_font("Arial", "B", 17)
    pdf.set_text_color(*SOLEOL_ORANGE)
    pdf.cell(140, 8, _tx("DÉTAIL DES POINTES"))

    _section_title(pdf, x0, 30, "TOP 10 DES POINTES")
    top = top_peaks_table(df, result, dt_hours, n=10)
    widths = [37, 20, 20, 24, 20, 23]
    labels = ["Date / heure", "Avant", "Après", "Décharge", "SOC", "Écrêtage"]
    _table_header(pdf, x0, 41, widths, labels)

    y = 48
    pdf.set_font("Arial", "", 6.4)
    for _, row in top.iterrows():
        vals = [
            pd.Timestamp(row["Date / heure"]).strftime("%d.%m.%Y %H:%M"),
            f'{row["Avant (kW)"]:.0f}',
            f'{row["Après (kW)"]:.0f}',
            f'{row["Décharge batterie (kW)"]:.0f}',
            f'{row["SOC (%)"]:.1f} %',
            f'{row["Écrêtage (kW)"]:.0f}',
        ]
        xx = x0
        for j, (w, val) in enumerate(zip(widths, vals)):
            pdf.set_xy(xx, y)
            pdf.set_text_color(*(GREEN if j == 5 else TEXT))
            pdf.cell(w, 6.2, _tx(val), border=1, align="R" if j > 0 else "L")
            xx += w
        y += 6.2

    _section_title(pdf, x0, y + 7, "POINTES MENSUELLES")
    ts = pd.to_datetime(df["timestamp"])
    before = np.asarray(df["import_kWh"], dtype=float) / dt_hours
    after = np.asarray(result.import_after_kWh_series, dtype=float) / dt_hours
    monthly = pd.DataFrame({"timestamp":ts, "Avant":before, "Après":after})
    # Rapport client : garder l'année principale de la courbe (2025 ici).
    dominant_year = int(monthly["timestamp"].dt.year.value_counts().idxmax())
    monthly = monthly[monthly["timestamp"].dt.year == dominant_year].copy()
    monthly["Mois"] = monthly["timestamp"].dt.to_period("M")
    monthly = monthly.groupby("Mois")[["Avant","Après"]].max().reset_index()
    monthly["Réduction"] = monthly["Avant"] - monthly["Après"]

    widths2 = [40, 34, 34, 36]
    _table_header(pdf, x0, y + 18, widths2, ["Mois", "Avant (kW)", "Après (kW)", "Réduction (kW)"])
    yy = y + 25
    pdf.set_font("Arial", "", 6.6)
    for _, row in monthly.iterrows():
        vals = [str(row["Mois"]), f'{row["Avant"]:.0f}', f'{row["Après"]:.0f}', f'{row["Réduction"]:.0f}']
        xx = x0
        for j, (w, val) in enumerate(zip(widths2, vals)):
            pdf.set_xy(xx, yy)
            pdf.set_text_color(*(GREEN if j == 3 else TEXT))
            pdf.cell(w, 6, _tx(val), border=1, align="R" if j > 0 else "L")
            xx += w
        yy += 6

    # Bottom blocks inspired by the approved mockup.
    bottom_y = min(yy + 7, 218)
    left_w = 80
    right_w = 60

    pdf.set_draw_color(*BORDER)
    pdf.set_fill_color(*LIGHT_BG)
    pdf.rect(x0, bottom_y, left_w, 52, style="DF")
    pdf.set_xy(x0 + 4, bottom_y + 4)
    pdf.set_font("Arial", "B", 7.5)
    pdf.set_text_color(*SOLEOL_ORANGE)
    pdf.cell(left_w - 8, 5, _tx("HYPOTHÈSES ET PARAMÈTRES DE CALCUL"))

    rows = [
        ("Mode de facturation", "Bande annuelle Groupe E"),
        ("Tarif puissance", f"{power_tariff:.2f} CHF/kW/mois"),
        ("Précision du seuil", f"{target_resolution_kW:.1f} kW"),
        ("Rendement aller-retour", f"{roundtrip_eff*100:.0f} %"),
        ("SOC technique fixe", f"{soc_min_pct:.0f} %"),
        ("Réserve Peak Shaving", f"{reserve_target_pct:.0f} %"),
        ("Recharge depuis le réseau", "Oui" if grid_recharge else "Non"),
    ]
    ry = bottom_y + 11
    for label, value in rows:
        pdf.set_xy(x0 + 4, ry)
        pdf.set_font("Arial", "", 5.9)
        pdf.set_text_color(*MUTED)
        pdf.cell(39, 4.7, _tx(label))
        pdf.set_xy(x0 + 43, ry)
        pdf.set_font("Arial", "B", 5.9)
        pdf.set_text_color(*TEXT)
        pdf.cell(left_w - 47, 4.7, _tx(value), align="R")
        ry += 5.1

    formula = (
        f"{result.reduction_kW:.0f} kW x {power_tariff:.2f} CHF/kW/mois\n"
        f"x 12 = {_fmt0(result.annual_saving_chf)} CHF/an"
    )
    _info_box(pdf, x0 + left_w + 4, bottom_y, right_w, 24, "FORMULE D'ÉCONOMIE", formula, LIGHT_GREEN, GREEN)

    remarks = (
        "Réductions mensuelles indicatives. Économie calculée sur la baisse de la bande annuelle. "
        "Surplus PV utilisé en priorité. Résultats issus des données quart-horaires fournies."
    )
    _info_box(pdf, x0 + left_w + 4, bottom_y + 28, right_w, 36, "REMARQUES", remarks, LIGHT_BLUE, BLUE)


def generate_peak_shaving_report(
    *,
    df,
    meta,
    result,
    client_name: str,
    capacity_kWh: float,
    charge_power_kW: float,
    discharge_power_kW: float,
    roundtrip_eff: float,
    soc_min_pct: float,
    reserve_target_pct: float,
    grid_recharge: bool,
    power_tariff: float,
    target_resolution_kW: float = 1.0,
    logo_path: str | None = None,
) -> bytes:
    pdf = ReportPDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=False)

    source_name = getattr(meta, "source", "Courbe de charge")
    coverage_days = float(getattr(meta, "coverage_days", 0.0) or 0.0)
    dt_hours = float(getattr(meta, "dt_hours", 0.25) or 0.25)

    common = dict(
        client_name=client_name,
        source_name=source_name,
        coverage_days=coverage_days,
        capacity_kWh=capacity_kWh,
        discharge_power_kW=discharge_power_kW,
        logo_path=logo_path,
    )

    _page_1(
        pdf,
        **common,
        charge_power_kW=charge_power_kW,
        roundtrip_eff=roundtrip_eff,
        soc_min_pct=soc_min_pct,
        reserve_target_pct=reserve_target_pct,
        grid_recharge=grid_recharge,
        power_tariff=power_tariff,
        result=result,
    )
    _page_2(
        pdf,
        **common,
        df=df,
        dt_hours=dt_hours,
        result=result,
        soc_min_pct=soc_min_pct,
        reserve_target_pct=reserve_target_pct,
    )
    _page_3(
        pdf,
        **common,
        df=df,
        dt_hours=dt_hours,
        result=result,
        power_tariff=power_tariff,
        roundtrip_eff=roundtrip_eff,
        soc_min_pct=soc_min_pct,
        reserve_target_pct=reserve_target_pct,
        grid_recharge=grid_recharge,
        target_resolution_kW=target_resolution_kW,
    )
    return _pdf_bytes(pdf)
