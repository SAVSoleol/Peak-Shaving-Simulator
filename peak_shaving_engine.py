"""Peak Shaving simulation engine.

Dedicated to demand-peak reduction on quarter-hour (or other interval) meter data.

Principles
----------
- Input data are interval energies in kWh after normalization by loaders.py.
- The battery can charge from PV export and, optionally, from the grid.
- Grid recharge is always limited so it does not create a new peak above the target.
- A configurable reserve target is maintained when possible.
- The engine automatically finds the lowest sustainable grid-power target.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class PeakResult:
    target_kW: float
    peak_before_kW: float
    peak_after_kW: float
    reduction_kW: float
    annual_saving_chf: float
    import_before_kWh: float
    import_after_kWh: float
    export_before_kWh: float
    export_after_kWh: float
    grid_charge_kWh: float
    pv_charge_kWh: float
    battery_discharge_kWh: float
    soc_kWh: np.ndarray
    soc_pct: np.ndarray
    import_after_kWh_series: np.ndarray
    export_after_kWh_series: np.ndarray
    battery_charge_grid_kWh_series: np.ndarray
    battery_charge_pv_kWh_series: np.ndarray
    battery_discharge_kWh_series: np.ndarray
    binding_reason: str
    critical_timestamp: pd.Timestamp | None
    critical_before_kW: float
    critical_after_kW: float
    critical_discharge_kW: float
    critical_soc_pct: float
    failed_target_kW: float
    failed_peak_after_kW: float
    failed_timestamp: pd.Timestamp | None
    failed_before_kW: float
    failed_after_kW: float
    failed_discharge_kW: float
    failed_soc_pct: float
    failed_shortfall_kW: float
    failed_reason: str


def _eta_components(roundtrip_eff: float) -> tuple[float, float]:
    rte = min(max(float(roundtrip_eff), 1e-6), 1.0)
    eta = rte ** 0.5
    return eta, eta


def simulate_target(
    import_kWh,
    export_kWh,
    timestamps,
    *,
    dt_hours: float,
    capacity_kWh: float,
    charge_power_kW: float,
    discharge_power_kW: float,
    roundtrip_eff: float,
    soc_min_pct: float,
    reserve_target_pct: float,
    target_kW: float,
    grid_recharge: bool = True,
    initial_soc_pct: float | None = None,
) -> dict:
    """Simulate one fixed grid-power target.

    `reserve_target_pct` is the SOC level the controller tries to restore whenever
    there is headroom below the target. Peak shaving may discharge below that level
    down to `soc_min_pct` if required.
    """
    imp = np.asarray(import_kWh, dtype=float)
    exp = np.asarray(export_kWh, dtype=float)
    ts = pd.to_datetime(timestamps)

    n = len(imp)
    if len(exp) != n or len(ts) != n:
        raise ValueError("Import, export and timestamps must have the same length.")

    cap = max(float(capacity_kWh), 0.0)
    soc_min = cap * min(max(float(soc_min_pct) / 100.0, 0.0), 1.0)
    reserve = cap * min(max(float(reserve_target_pct) / 100.0, 0.0), 1.0)
    reserve = max(reserve, soc_min)

    if initial_soc_pct is None:
        soc = reserve
    else:
        soc = cap * min(max(float(initial_soc_pct) / 100.0, 0.0), 1.0)
        soc = max(soc, soc_min)

    eta_c, eta_d = _eta_components(roundtrip_eff)
    max_charge_step = max(float(charge_power_kW), 0.0) * dt_hours
    max_discharge_step = max(float(discharge_power_kW), 0.0) * dt_hours
    target_step = max(float(target_kW), 0.0) * dt_hours

    imp_after = np.zeros(n)
    exp_after = np.zeros(n)
    soc_series = np.zeros(n)
    pv_charge = np.zeros(n)
    grid_charge = np.zeros(n)
    discharge = np.zeros(n)

    power_limited = False
    energy_limited = False

    for i in range(n):
        # 1) Use PV export first, but only to restore the dedicated Peak Shaving
        # reserve. The zone above the reserve boundary belongs to autoconsumption
        # and is intentionally outside this dedicated simulator.
        pv_in = min(exp[i], max_charge_step)
        pv_in = min(pv_in, max((reserve - soc) / eta_c, 0.0))
        pv_in = max(pv_in, 0.0)
        soc += pv_in * eta_c
        exp_after[i] = max(exp[i] - pv_in, 0.0)
        pv_charge[i] = pv_in

        # 2) Grid recharge only up to the reserve target, and only with headroom
        # below the desired demand target.
        grid_in = 0.0
        if grid_recharge and soc < reserve and imp[i] < target_step:
            headroom = max(target_step - imp[i], 0.0)
            reserve_need_input = max((reserve - soc) / eta_c, 0.0)
            grid_in = min(headroom, max_charge_step, reserve_need_input)
            grid_in = max(grid_in, 0.0)
            soc += grid_in * eta_c
        grid_charge[i] = grid_in

        grid_demand = imp[i] + grid_in

        # 3) Discharge only when demand exceeds the target.
        need = max(grid_demand - target_step, 0.0)
        available_to_min_soc = max((soc - soc_min) * eta_d, 0.0)
        dis = min(need, max_discharge_step, available_to_min_soc)
        dis = max(dis, 0.0)

        if need > dis + 1e-9:
            if need > max_discharge_step + 1e-9:
                power_limited = True
            if need > available_to_min_soc + 1e-9:
                energy_limited = True

        soc -= dis / eta_d
        soc = min(max(soc, soc_min), cap)
        discharge[i] = dis
        imp_after[i] = max(grid_demand - dis, 0.0)
        soc_series[i] = soc

    before_kw = imp / dt_hours
    after_kw = imp_after / dt_hours
    discharge_kw = discharge / dt_hours
    peak_before = float(np.max(before_kw)) if n else 0.0
    peak_after = float(np.max(after_kw)) if n else 0.0

    # Identify the interval that really constrains a lower target:
    # among intervals sitting at/near the achieved ceiling, prefer the one with
    # the lowest SOC margin and/or the highest discharge-power usage.
    if n:
        ceiling = peak_after
        near = np.where(after_kw >= ceiling - max(0.5, 0.002 * max(ceiling, 1.0)))[0]
        if len(near) == 0:
            near = np.array([int(np.argmax(after_kw))])

        soc_margin_kWh = soc_series[near] - soc_min
        power_margin_kW = max(float(discharge_power_kW), 0.0) - discharge_kw[near]

        # Low SOC and low power margin are both "bad"; normalize to build a score.
        soc_span = max(cap - soc_min, 1e-9)
        p_span = max(float(discharge_power_kW), 1e-9)
        score = (soc_margin_kWh / soc_span) + (power_margin_kW / p_span)
        crit_local = int(np.argmin(score))
        max_idx = int(near[crit_local])
    else:
        max_idx = 0

    soc_at_crit = float(soc_series[max_idx]) if n else 0.0
    dis_at_crit_kw = float(discharge_kw[max_idx]) if n else 0.0
    at_power_limit = dis_at_crit_kw >= max(float(discharge_power_kW), 0.0) - max(0.5, 0.002 * max(float(discharge_power_kW), 1.0))
    at_energy_limit = soc_at_crit <= soc_min + max(0.5, 0.002 * max(cap, 1.0))

    if at_power_limit and at_energy_limit:
        reason = "power_and_energy"
    elif at_power_limit:
        reason = "power"
    elif at_energy_limit:
        reason = "energy"
    elif peak_after <= target_kW + 1e-6:
        # Target is sustainable, but this is the interval closest to the boundary.
        reason = "boundary"
    elif power_limited and energy_limited:
        reason = "power_and_energy"
    elif power_limited:
        reason = "power"
    elif energy_limited:
        reason = "energy"
    else:
        reason = "other"

    return {
        "target_kW": float(target_kW),
        "peak_before_kW": peak_before,
        "peak_after_kW": peak_after,
        "reduction_kW": max(peak_before - peak_after, 0.0),
        "import_before_kWh": float(imp.sum()),
        "import_after_kWh": float(imp_after.sum()),
        "export_before_kWh": float(exp.sum()),
        "export_after_kWh": float(exp_after.sum()),
        "grid_charge_kWh": float(grid_charge.sum()),
        "pv_charge_kWh": float(pv_charge.sum()),
        "battery_discharge_kWh": float(discharge.sum()),
        "soc_kWh": soc_series,
        "soc_pct": np.where(cap > 0, soc_series / cap * 100.0, 0.0),
        "import_after_kWh_series": imp_after,
        "export_after_kWh_series": exp_after,
        "battery_charge_grid_kWh_series": grid_charge,
        "battery_charge_pv_kWh_series": pv_charge,
        "battery_discharge_kWh_series": discharge,
        "binding_reason": reason,
        "critical_timestamp": pd.Timestamp(ts[max_idx]) if n else None,
        "critical_before_kW": float(before_kw[max_idx]) if n else 0.0,
        "critical_after_kW": float(after_kw[max_idx]) if n else 0.0,
        "critical_discharge_kW": float(discharge_kw[max_idx]) if n else 0.0,
        "critical_soc_pct": float((soc_series[max_idx] / cap * 100.0) if (n and cap > 0) else 0.0),
    }



def _diagnose_failed_target(
    import_kWh,
    export_kWh,
    timestamps,
    *,
    dt_hours: float,
    capacity_kWh: float,
    charge_power_kW: float,
    discharge_power_kW: float,
    roundtrip_eff: float,
    soc_min_pct: float,
    reserve_target_pct: float,
    target_kW: float,
    grid_recharge: bool,
) -> dict:
    """Simulate an intentionally-too-low target and identify the first real failure.

    The useful diagnostic is not the successful boundary interval. It is the first
    interval where the requested target cannot be held, and whether the shortfall
    comes from discharge power, available energy/SOC, or both.
    """
    r = simulate_target(
        import_kWh,
        export_kWh,
        timestamps,
        dt_hours=dt_hours,
        capacity_kWh=capacity_kWh,
        charge_power_kW=charge_power_kW,
        discharge_power_kW=discharge_power_kW,
        roundtrip_eff=roundtrip_eff,
        soc_min_pct=soc_min_pct,
        reserve_target_pct=reserve_target_pct,
        target_kW=target_kW,
        grid_recharge=grid_recharge,
    )

    imp = np.asarray(import_kWh, dtype=float)
    ts = pd.to_datetime(timestamps)
    after_kw = np.asarray(r["import_after_kWh_series"], dtype=float) / dt_hours
    before_kw = imp / dt_hours
    dis_kw = np.asarray(r["battery_discharge_kWh_series"], dtype=float) / dt_hours
    soc_pct = np.asarray(r["soc_pct"], dtype=float)

    # Find the first interval that actually exceeds the requested target.
    viol = np.where(after_kw > float(target_kW) + 1e-6)[0]
    if len(viol) == 0:
        idx = int(np.argmax(after_kw))
    else:
        idx = int(viol[0])

    shortfall = max(float(after_kw[idx] - target_kW), 0.0)
    power_tol = max(0.5, 0.002 * max(float(discharge_power_kW), 1.0))
    soc_tol = max(0.5, 0.002 * 100.0)

    power_lim = float(dis_kw[idx]) >= float(discharge_power_kW) - power_tol
    energy_lim = float(soc_pct[idx]) <= float(soc_min_pct) + soc_tol

    if power_lim and energy_lim:
        reason = "power_and_energy"
    elif power_lim:
        reason = "power"
    elif energy_lim:
        reason = "energy"
    else:
        # A sequential-energy limitation can appear before SOC reaches the absolute
        # minimum at the exact failing interval because prior intervals consumed the
        # reserve. Treat this as a sequence limitation.
        reason = "sequence"

    return {
        "target_kW": float(target_kW),
        "peak_after_kW": float(np.max(after_kw)),
        "timestamp": pd.Timestamp(ts[idx]),
        "before_kW": float(before_kw[idx]),
        "after_kW": float(after_kw[idx]),
        "discharge_kW": float(dis_kw[idx]),
        "soc_pct": float(soc_pct[idx]),
        "shortfall_kW": float(shortfall),
        "reason": reason,
    }

def find_min_sustainable_target(
    import_kWh,
    export_kWh,
    timestamps,
    *,
    dt_hours: float,
    capacity_kWh: float,
    charge_power_kW: float,
    discharge_power_kW: float,
    roundtrip_eff: float,
    soc_min_pct: float,
    reserve_target_pct: float,
    grid_recharge: bool = True,
    target_resolution_kW: float = 0.5,
    tariff_chf_per_kw_month: float = 5.10,
    billing_mode: str = "annual_band",
) -> PeakResult:
    """Find the lowest target that the battery can hold over the whole data set.

    The search is monotonic and uses bisection. The result is rounded upward to the
    requested target resolution to avoid claiming a threshold below the simulated limit.
    """
    imp = np.asarray(import_kWh, dtype=float)
    if len(imp) == 0:
        raise ValueError("No import data.")
    if dt_hours <= 0:
        raise ValueError("dt_hours must be > 0.")

    peak_before = float(np.max(imp / dt_hours))
    lo = max(0.0, peak_before - max(float(discharge_power_kW), 0.0) - 5.0)
    hi = peak_before

    def ok(target):
        r = simulate_target(
            import_kWh, export_kWh, timestamps,
            dt_hours=dt_hours,
            capacity_kWh=capacity_kWh,
            charge_power_kW=charge_power_kW,
            discharge_power_kW=discharge_power_kW,
            roundtrip_eff=roundtrip_eff,
            soc_min_pct=soc_min_pct,
            reserve_target_pct=reserve_target_pct,
            target_kW=target,
            grid_recharge=grid_recharge,
        )
        return r["peak_after_kW"] <= target + 1e-6, r

    # Bisection to sub-resolution precision.
    last = None
    for _ in range(40):
        mid = (lo + hi) / 2.0
        feasible, r = ok(mid)
        last = r
        if feasible:
            hi = mid
        else:
            lo = mid

    res = max(float(target_resolution_kW), 0.1)
    target = np.ceil(hi / res) * res
    feasible, r = ok(target)

    # Defensive upward nudge in case of numerical boundary effects.
    tries = 0
    while not feasible and tries < 20:
        target += res
        feasible, r = ok(target)
        tries += 1

    reduction = max(float(r["peak_before_kW"]) - float(r["peak_after_kW"]), 0.0)

    # Diagnose the first target immediately below the guaranteed threshold.
    # This is the most useful engineering explanation of "why not lower?".
    failed_target = max(0.0, float(target) - res)
    failed = _diagnose_failed_target(
        import_kWh,
        export_kWh,
        timestamps,
        dt_hours=dt_hours,
        capacity_kWh=capacity_kWh,
        charge_power_kW=charge_power_kW,
        discharge_power_kW=discharge_power_kW,
        roundtrip_eff=roundtrip_eff,
        soc_min_pct=soc_min_pct,
        reserve_target_pct=reserve_target_pct,
        target_kW=failed_target,
        grid_recharge=grid_recharge,
    )

    mode = str(billing_mode or "annual_band").lower()
    tariff = max(float(tariff_chf_per_kw_month), 0.0)

    if mode == "annual_band":
        saving = reduction * tariff * 12.0
    else:
        idx = pd.to_datetime(timestamps)
        before_kw = np.asarray(import_kWh, dtype=float) / dt_hours
        after_kw = np.asarray(r["import_after_kWh_series"], dtype=float) / dt_hours
        tmp = pd.DataFrame({
            "month": idx.to_period("M"),
            "before": before_kw,
            "after": after_kw,
        })
        monthly = tmp.groupby("month")[["before", "after"]].max()
        saving = float(((monthly["before"] - monthly["after"]).clip(lower=0.0) * tariff).sum())

    return PeakResult(
        target_kW=float(target),
        peak_before_kW=float(r["peak_before_kW"]),
        peak_after_kW=float(r["peak_after_kW"]),
        reduction_kW=reduction,
        annual_saving_chf=float(saving),
        import_before_kWh=float(r["import_before_kWh"]),
        import_after_kWh=float(r["import_after_kWh"]),
        export_before_kWh=float(r["export_before_kWh"]),
        export_after_kWh=float(r["export_after_kWh"]),
        grid_charge_kWh=float(r["grid_charge_kWh"]),
        pv_charge_kWh=float(r["pv_charge_kWh"]),
        battery_discharge_kWh=float(r["battery_discharge_kWh"]),
        soc_kWh=np.asarray(r["soc_kWh"], dtype=float),
        soc_pct=np.asarray(r["soc_pct"], dtype=float),
        import_after_kWh_series=np.asarray(r["import_after_kWh_series"], dtype=float),
        export_after_kWh_series=np.asarray(r["export_after_kWh_series"], dtype=float),
        battery_charge_grid_kWh_series=np.asarray(r["battery_charge_grid_kWh_series"], dtype=float),
        battery_charge_pv_kWh_series=np.asarray(r["battery_charge_pv_kWh_series"], dtype=float),
        battery_discharge_kWh_series=np.asarray(r["battery_discharge_kWh_series"], dtype=float),
        binding_reason=str(r["binding_reason"]),
        critical_timestamp=r["critical_timestamp"],
        critical_before_kW=float(r["critical_before_kW"]),
        critical_after_kW=float(r["critical_after_kW"]),
        critical_discharge_kW=float(r["critical_discharge_kW"]),
        critical_soc_pct=float(r["critical_soc_pct"]),
        failed_target_kW=float(failed["target_kW"]),
        failed_peak_after_kW=float(failed["peak_after_kW"]),
        failed_timestamp=failed["timestamp"],
        failed_before_kW=float(failed["before_kW"]),
        failed_after_kW=float(failed["after_kW"]),
        failed_discharge_kW=float(failed["discharge_kW"]),
        failed_soc_pct=float(failed["soc_pct"]),
        failed_shortfall_kW=float(failed["shortfall_kW"]),
        failed_reason=str(failed["reason"]),
    )


def top_peaks_table(df: pd.DataFrame, result: PeakResult, dt_hours: float, n: int = 10) -> pd.DataFrame:
    """Return the highest original quarter-hour peaks and their post-battery values."""
    out = pd.DataFrame({
        "Date / heure": pd.to_datetime(df["timestamp"]),
        "Avant (kW)": np.asarray(df["import_kWh"], dtype=float) / dt_hours,
        "Après (kW)": np.asarray(result.import_after_kWh_series, dtype=float) / dt_hours,
        "Décharge batterie (kW)": np.asarray(result.battery_discharge_kWh_series, dtype=float) / dt_hours,
        "SOC (%)": result.soc_pct,
    })
    out["Écrêtage (kW)"] = out["Avant (kW)"] - out["Après (kW)"]
    return out.nlargest(int(n), "Avant (kW)").sort_values("Avant (kW)", ascending=False).reset_index(drop=True)
