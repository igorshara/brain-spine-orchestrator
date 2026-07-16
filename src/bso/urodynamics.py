"""Urodynamics — a clinician-grade cystometric study from the bladder model.

Computes the standard urodynamic panel a urologist/partner expects, derived honestly
from the in-silico filling–storage–voiding simulation (`autonomic.simulate_bladder`):
maximum cystometric capacity, detrusor pressures, bladder compliance, detrusor leak-
point pressure (DLPP), neurogenic detrusor overactivity (NDO), maximum flow (Qmax),
post-void residual (PVR), bladder voiding efficiency (BVE), detrusor-sphincter
dyssynergia (DSD) and autonomic-dysreflexia rise — with the <40 cmH₂O upper-tract safety criterion.

Illustrative research simulation — not a medical device; numbers are illustrative.
"""
from __future__ import annotations

from .autonomic import simulate_bladder

# <40 cmH₂O upper-tract safety criterion: sustained detrusor storage pressure ≥ 40 cmH₂O endangers the
# upper urinary tract (kidneys). The single most important safety number.
MCGUIRE_CMH2O = 40.0


def cystometrogram(modulation: bool, dyssynergia: bool = True, dt: float = 0.1,
                   fill_s: float = 120.0, void_s: float = 60.0) -> dict:
    """One cystometric study. Returns a down-sampled CMG trace + the urodynamic panel."""
    bladder, ad, rec = simulate_bladder(modulation, dyssynergia, dt, fill_s, void_s)
    n_fill = int(fill_s / dt)
    P, V, Q, T = rec.bladder_pressure, rec.bladder_volume, rec.outflow, rec.t
    fillP, fillV, fillQ = P[:n_fill], V[:n_fill], Q[:n_fill]
    voidP, voidQ = P[n_fill:], Q[n_fill:]

    mcc = round(V[n_fill - 1])                                   # max cystometric capacity (mL)
    p_end_fill = round(fillP[-1], 1)
    p_max_storage = round(max(fillP), 1)
    dV, dP = fillV[-1] - fillV[0], max(1e-6, fillP[-1] - fillP[0])
    compliance = round(dV / dP, 1)                              # mL/cmH₂O
    p_max_void = round(max(voidP), 1) if voidP else 0.0
    qmax = round(max(voidQ), 1) if voidQ else 0.0              # mL/s
    pvr = round(V[-1])                                          # post-void residual (mL)
    voided = max(0, mcc - pvr)
    bve = round(100 * voided / mcc) if mcc > 0 else 0          # bladder voiding efficiency (%)

    dlpp = None                                                # detrusor leak-point pressure
    for i in range(n_fill):
        if fillQ[i] > 0.05:
            dlpp = round(fillP[i], 1)
            break

    ndo, armed = 0, True                                        # neurogenic detrusor overactivity
    for i in range(n_fill):
        spike = fillP[i] - (fillV[i] / bladder.compliance)     # active (detrusor) component
        if spike > 15 and armed:
            ndo += 1
            armed = False
        elif spike < 5:
            armed = True

    stride = max(1, len(T) // 150)
    trace = [{"t": round(T[i], 1), "p": round(P[i], 1), "v": round(V[i]),
              "q": round(Q[i], 2)} for i in range(0, len(T), stride)]

    return {
        "trace": trace,
        "metrics": {
            "mcc_ml": mcc,
            "p_end_fill_cmH2O": p_end_fill,
            "p_max_storage_cmH2O": p_max_storage,
            "compliance_ml_cmH2O": compliance,
            "p_max_void_cmH2O": p_max_void,
            "qmax_ml_s": qmax,
            "pvr_ml": pvr,
            "voided_ml": voided,
            "bve_pct": bve,
            "dlpp_cmH2O": dlpp,
            "ndo_contractions": ndo,
            "ad_rise_mmHg": round(ad.systolic_rise),
            "dsd": bool(dyssynergia and not modulation),
            "safe_storage": p_max_storage < MCGUIRE_CMH2O,
            "mcguire_risk": p_max_storage >= MCGUIRE_CMH2O,
        },
    }


def study() -> dict:
    """Baseline (neurogenic DSD) vs coordinated-EES cystometric study."""
    return {
        "baseline": cystometrogram(modulation=False, dyssynergia=True),
        "coordinated": cystometrogram(modulation=True, dyssynergia=True),
        "mcguire_cmH2O": MCGUIRE_CMH2O,
    }
