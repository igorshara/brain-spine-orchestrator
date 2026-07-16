"""Zero-dependency web dashboard for BSO — runs simulations on request.

Веб-дашборд на stdlib http.server (без зовнішніх залежностей): крутиш параметри
(втома, coupling, адаптація, тіло кінематика/MuJoCo) → бекенд проганяє симуляцію →
фронт малює фігурку, що крокує, GRF і криві сечового міхура. Для живих демо
партнерам. Усе ILLUSTRATIVE, дослідницька симуляція.

Запуск:  python3 web/server.py   (далі відкрий http://localhost:8765)
"""

from __future__ import annotations

import json
import math
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bso.autonomic import (  # noqa: E402
    AutonomicCommand,
    AutonomicEvent,
    AutonomicFunction,
    build_autonomic_system,
)
from bso.biomech.kinematic import FOOT_LEN, HIP_HEIGHT, SHANK_LEN, THIGH_LEN  # noqa: E402
from bso.decoder_stub import IntentEvent  # noqa: E402
from bso.degradation import FatigueModel  # noqa: E402
from bso.runtime import build_system  # noqa: E402
from bso.schemas import Mode  # noqa: E402

HERE = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SRC_EXT = (".py", ".md", ".sql", ".txt", ".toml", ".cfg", ".json")


def read_source(rel):
    """Serve a source file from inside the repo so any dashboard block can drill
    down to the code behind it. Sandboxed: the resolved path must stay under the
    repo root, be a regular file and have a viewable extension."""
    rel = (rel or "").lstrip("/").replace("\\", "/")
    target = os.path.abspath(os.path.join(REPO_ROOT, rel))
    if target != REPO_ROOT and not target.startswith(REPO_ROOT + os.sep):
        return {"error": "path outside repository"}
    if not os.path.isfile(target):
        return {"error": f"not found: {rel}"}
    if not target.endswith(SRC_EXT):
        return {"error": "file type not viewable"}
    try:
        with open(target, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
    truncated = False
    if len(content) > 400_000:
        content = content[:400_000] + "\n… (truncated)"
        truncated = True
    return {"path": rel, "content": content,
            "lines": content.count("\n") + 1, "truncated": truncated}


def _leg_points(hip, hip_deg, knee_deg, ankle_deg):
    hx, hy = hip
    h = math.radians(hip_deg)
    knee = (hx + THIGH_LEN * math.sin(h), hy - THIGH_LEN * math.cos(h))
    shank = h - math.radians(knee_deg)
    ankle = (knee[0] + SHANK_LEN * math.sin(shank), knee[1] - SHANK_LEN * math.cos(shank))
    foot = shank + math.radians(90 + ankle_deg)
    toe = (ankle[0] + FOOT_LEN * math.sin(foot), ankle[1] - FOOT_LEN * math.cos(foot))
    return [list(hip), list(knee), list(ankle), list(toe)]


def run_locomotion(p):
    fatigue = None
    if p.get("fatigue"):
        fatigue = FatigueModel(enabled=True, fatigue_rate=0.09, fatigue_max=0.5,
                               drift_rate_per_s=0.004)
    model = None
    if p.get("body") == "mujoco":
        try:
            from bso.biomech.mujoco_model import MuJoCoModel
            model = MuJoCoModel()
        except Exception:
            model = None
    speed = float(p.get("speed", 0.5))
    sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.5, Mode.WALK, speed=speed)]
    dur = float(p.get("dur", 12.0))
    sys_ = build_system(sched, model=model, fatigue=fatigue, adapt=bool(p.get("adapt")),
                        coupling=float(p.get("coupling", 0.0)))
    rec = sys_.run(dur)

    stride = max(1, len(rec.t) // 220)
    frames = []
    for i in range(0, len(rec.t), stride):
        pose = rec.pose[i]
        hip = (pose.get("pelvis_x", 0.0), pose.get("pelvis_z", HIP_HEIGHT))
        tr = math.radians(pose.get("trunk", 0.0))
        head = [hip[0] + 0.6 * math.sin(tr), hip[1] + 0.6 * math.cos(tr)]
        fr = rec.frames[i]
        frames.append({
            "t": round(rec.t[i], 3),
            "trunk": [list(hip), head],
            "L": _leg_points(hip, pose["L_hip"], pose["L_knee"], pose["L_ankle"]),
            "R": _leg_points(hip, pose["R_hip"], pose["R_knee"], pose["R_ankle"]),
            "grfL": round(fr.grf["L"], 1) if fr else 0.0,
            "grfR": round(fr.grf["R"], 1) if fr else 0.0,
        })
    gs = [g for g in rec.gait_state if g is not None]
    fy = [pose.get("L_foot_y", 0.0) for pose in rec.pose[len(rec.pose) // 3:]]
    metrics = {
        "cadence": round(gs[-1].cadence, 0) if gs else 0,
        "balance_ok_pct": round(100 * sum(g.balance_ok for g in gs) / max(1, len(gs))),
        "foot_clearance_m": round(max(fy) - min(fy), 3) if fy else 0,
        "safety_events": len(rec.safety_events),
        "body": "MuJoCo physics" if model is not None else "kinematic",
    }
    return {"frames": frames, "metrics": metrics}


def run_autonomic(p):
    modulation = bool(p.get("modulation"))
    sched = [AutonomicEvent(0.0, AutonomicFunction.BLADDER, AutonomicCommand.STORE),
             AutonomicEvent(120.0, AutonomicFunction.BLADDER, AutonomicCommand.VOID)]
    from bso.safety import SafetySupervisor
    safety = SafetySupervisor()
    sys_ = build_autonomic_system(sched, modulation=modulation, safety=safety)
    log = sys_.run(180.0)
    series = [s for s in log if s and s["function"] == "bladder"]
    stride = max(1, len(series) // 220)
    pts = [{"t": round(i * 0.1, 1), "volume": round(s["volume"], 1),
            "pressure": round(s["pressure"], 1), "ad_risk": round(s["ad_risk"], 2)}
           for i, s in enumerate(series) if i % stride == 0]
    void = series[1200:] if len(series) > 1200 else series
    metrics = {
        "peak_pressure": round(max(s["pressure"] for s in void)),
        "residual_ml": round(series[-1]["volume"]),
        "ad_events": safety.autonomic_ad_events,
    }
    return {"points": pts, "metrics": metrics}


def run_guardian(p):
    """Predictive AD guardian: BP over time for none / reactive / predictive."""
    from bso.ad_guardian import simulate
    out = {}
    for pol in ("none", "reactive", "predictive"):
        rec, m = simulate(pol)
        st = max(1, len(rec["t"]) // 200)
        out[pol] = {"t": [round(x, 1) for x in rec["t"][::st]],
                    "bp": [round(x, 1) for x in rec["bp"][::st]], "metrics": m}
    return out


def run_mapping(p):
    import numpy as np

    from bso.mapping import (
        GROUPS,
        ElectrodeArray,
        auto_map,
        best_contact_per_group,
        mapping_accuracy,
        selectivity,
    )
    arr = ElectrodeArray()
    W_hat, _thr, trials = auto_map(arr)
    acc = mapping_accuracy(W_hat, arr.W)
    truth = best_contact_per_group(arr.W)
    naive = {g: i for i, g in enumerate(GROUPS)}
    manual_acc = sum(naive[g] == truth[g] for g in GROUPS) / len(GROUPS)
    est = best_contact_per_group(W_hat)
    sel = float(np.mean([selectivity(arr.W, est[g], gi) for gi, g in enumerate(GROUPS)]))
    return {
        "groups": GROUPS,
        "true": [[round(v, 3) for v in row] for row in arr.W.tolist()],
        "recovered": [[round(v, 3) for v in row] for row in W_hat.tolist()],
        "best": {g: est[g] for g in GROUPS},
        "metrics": {"accuracy": round(acc * 100), "manual": round(manual_acc * 100),
                    "trials": trials, "selectivity": round(sel, 2)},
    }


CACHE_DIR = os.path.join(HERE, "cache")
import tempfile  # noqa: E402
CLINIC_DB = os.path.join(tempfile.gettempdir(), "bso_clinic.db")  # clinician-approval audit log (ephemeral)


def run_unified(q):
    """Live proof of 'one substrate': build locomotion + autonomic on ONE bus / tick
    loop / safety gate, run them together, and return the machine-checked evidence."""
    from bso.autonomic import AutonomicCommand, AutonomicEvent, AutonomicFunction
    from bso.decoder_stub import IntentEvent, Mode
    from bso.unified import build_unified_system
    loco = [IntentEvent(0.0, Mode.STAND), IntentEvent(0.4, Mode.WALK, speed=0.6)]
    auto = [AutonomicEvent(0.0, AutonomicFunction.BLADDER, AutonomicCommand.STORE)]
    dt, dur = 0.01, 2.0
    uni = build_unified_system(loco, auto, dt=dt)
    rec, auton = uni.run(dur)
    return {
        "evidence": uni.evidence(),
        "gait_frames": len(rec.frames),
        "ticks": int(dur / dt),
        "autonomic_active": auton.cord is not None,
        "safety_clamped": uni.safety.clamped_count,
    }


def run_cohort(q):
    """Cohort foundation model — cold-start lift at zero patient probes."""
    from bso.cohort_model import summary
    return summary(n_cohort=int(q.get("n", 16)))


def run_recovery(q):
    """Recovery-optimizing orchestrator — plasticity-as-objective vs function-first."""
    from bso.recovery_optimizer import compare
    return compare(n_sessions=int(q.get("sessions", 30)))


def run_fusion(q):
    """Multimodal spared-signal fusion — fused vs single modalities, with dropout."""
    from bso.fusion import demo
    return demo(drop=q.get("drop", "cortical"))


def run_twin(q):
    """Digital twin — in-silico pre-optimisation of starting programs per goal."""
    from bso.neurostim_gym import digital_twin_preoptimize
    return digital_twin_preoptimize(patient_seed=int(q.get("seed", 0)))


def run_telemetry(q):
    """Telemetry adapter — integration contract + a live read-only sample."""
    from dataclasses import asdict

    from bso.telemetry import contract, get_source
    s = get_source(q.get("source", "simulated"))
    return {"contract": contract(), "info": s.info(), "sample": asdict(s.read())}


def run_autonomic_clinical(q):
    """Autonomic-first clinical program — per-function baseline→managed + AD safety."""
    from bso.autonomic_clinical import program
    return program(weeks=int(q.get("weeks", 8)))


def run_urodynamics(q):
    """Cystometric study — full urodynamic panel + CMG trace, baseline vs coordinated EES."""
    from bso.urodynamics import study
    return study()


def run_bladder_report(q):
    """Partner-facing urodynamics clinical report (markdown), EN or UA."""
    from bso.clinical_report import urodynamics_report
    return {"markdown": urodynamics_report(lang=q.get("lang", "en"))}


def _cache(name, compute):
    """Serve a precomputed JSON cache when the heavy lib (OpenSim) is unavailable
    on the host; recompute + refresh the cache when it IS available."""
    path = os.path.join(CACHE_DIR, name)
    try:
        result = compute()
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(path, "w") as f:
                json.dump(result, f)
        except Exception:
            pass
        return result
    except Exception as e:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return {"error": f"OpenSim unavailable and no cache: {e}"}


def run_opensim_view(p):
    """Muscle-driven gait on the validated OpenSim model — real anatomy, real
    muscles moving the legs (not the planar cartoon)."""
    return _cache("opensim.json", _compute_opensim_view)


def _compute_opensim_view():
    import numpy as np

    from bso.biomech.opensim_model import run_muscle_driven
    sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=0.6)]
    rec = build_system(sched).run(5.0)
    res = run_muscle_driven(rec.activations, rec.t, t_start=1.0, duration=3.0)
    figs = res["figures"]
    figs3 = res.get("figures3d", figs)
    stride = max(1, len(figs) // 90)
    frames = []
    frames3d = []
    for i in range(0, len(figs), stride):
        f = figs[i]
        frames.append({"pelvis": list(f["pelvis"]), "torso": list(f["torso"]),
                       "L": [list(x) for x in f["l"]], "R": [list(x) for x in f["r"]],
                       "t": round(res["t"][i], 2)})
        g = figs3[i]
        frames3d.append({"pelvis": g["pelvis"], "torso": g["torso"], "L": g["l"], "R": g["r"]})
    hipR = np.array(res["R_hip"][12:])
    hipL = np.array(res["L_hip"][12:])
    corr = float(np.corrcoef(hipR, hipL)[0, 1]) if len(hipR) > 3 else 0.0
    return {"frames": frames, "frames3d": frames3d,
            "traj": {"t": res["t"], "R_hip": res["R_hip"], "L_hip": res["L_hip"],
                     "R_knee": res["R_knee"]},
            "metrics": {"model": "OpenSim gait10dof18musc (18 Hill muscles)",
                        "drive": "muscle-driven forward dynamics",
                        "lr_hip_corr": round(corr, 2), "muscles": 18}}


def run_opensim_mesh(p):
    """Muscle-driven gait + REAL bone meshes (.vtp) and per-frame body transforms,
    for photorealistic 3D rendering in the browser."""
    return _cache("opensim_mesh.json", _compute_opensim_mesh)


def _compute_opensim_mesh():
    from bso.biomech.opensim_model import load_body_meshes, run_muscle_driven
    sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=0.6)]
    rec = build_system(sched).run(5.0)
    res = run_muscle_driven(rec.activations, rec.t, t_start=1.0, duration=3.0,
                            with_transforms=True)
    tfs = res["transforms"]
    stride = max(1, len(tfs) // 70)
    frames = [tfs[i] for i in range(0, len(tfs), stride)]
    meshes = load_body_meshes()
    return {"meshes": meshes, "transforms": frames,
            "bodies": list(meshes.keys()),
            "metrics": {"model": "gait10dof18musc", "muscles": 18,
                        "vertices": sum(len(m["verts"]) // 3 for m in meshes.values())}}


def run_sensors(p, rows=None):
    """Live-sensor lane: decode INTENT from residual signals (real CSV rows if
    uploaded, else a simulated stream) and run the clinical advisor on the state.

    This is the bridge to reality: the same decoder/advisor that runs here on
    synthetic data runs unchanged on real sEMG/IMU/pressure once sensors are wired.
    """
    import numpy as np

    from bso.advisor import assess
    from bso.intent import INTENTS, IntentDecoder, ResidualSignalModel, decode_stream

    sparing = float(p.get("sparing", 0.6))
    # train the decoder on the residual-signal model for this sparing level
    model = ResidualSignalModel(sparing=sparing, seed=1)
    X, y = model.dataset(200)
    dec = IntentDecoder(smooth=5).fit(X, y)

    source = "uploaded sensor CSV" if rows else "simulated live stream"
    if rows:
        # real data path: each row = N_CH residual channels -> decode per sample
        arr = np.array(rows, dtype=float)
        dec._hist = []
        decoded = [dec.predict(r) for r in arr]
        raw = [dec.predict_raw(r) for r in arr]          # instantaneous (unsmoothed) read
        true = None
        series = [{"i": i, "decoded": INTENTS[d]} for i, d in enumerate(decoded)]
        # honest confidence: how often the instantaneous decode agrees with the
        # smoothed decision — high on a clean signal, lower on a noisy one (no fake 1.0)
        conf = float(np.mean([1.0 if rw == dc else 0.0
                              for rw, dc in zip(raw, decoded, strict=False)])) if decoded else 0.0
        last = INTENTS[decoded[-1]] if decoded else "idle"
        walk_recall = None
    else:
        timeline = [("idle", 20), ("stand", 20), ("walk", 40), ("stand", 20), ("idle", 20)]
        true, decoded, _lat = decode_stream(dec, ResidualSignalModel(sparing, seed=2), timeline)
        series = [{"i": i, "true": INTENTS[t], "decoded": INTENTS[d]}
                  for i, (t, d) in enumerate(zip(true, decoded, strict=False))]
        walk_mask = true == INTENTS.index("walk")
        walk_recall = float((decoded[walk_mask] == INTENTS.index("walk")).mean())
        conf = float((true == decoded).mean())
        last = INTENTS[int(decoded[-1])]

    state = {
        "intent": last,
        "intent_conf": conf,
        "sparing": sparing,
        "bladder_pressure": float(p.get("bladder_pressure", 22.0)),
        "ad_bp_rise": float(p.get("ad_bp_rise", 0.0)),
        "walk_recall": walk_recall,
    }
    advice = [a.as_dict() for a in assess(state, lang=p.get("lang", "en"))]
    return {"source": source, "series": series, "state": state, "advice": advice,
            "intents": INTENTS,
            "metrics": {"samples": len(series), "decode_conf": round(conf, 2),
                        "live_intent": last,
                        "walk_recall": round(walk_recall, 2) if walk_recall is not None else "—"}}


def run_programs(p):
    """Igor's real the device partner program map + an auto-mapping framing on HIS data."""
    from bso.stim_programs import PROGRAMS, summary
    progs = [pr.as_dict() | {"group": pr.group} for pr in PROGRAMS]
    s = summary()
    n = s["n_programs"]
    # honest framing: clinician tuned each program by hand; the agent narrows the
    # contact search per goal. ~hours manual vs ~minutes automated (illustrative).
    manual_min = n * 25          # ~25 min hand-tuning per program (illustrative)
    auto_min = round(n * 0.6 + 8)  # parallel narrowing + a few confirmations
    return {"programs": progs, "summary": s,
            "mapping": {"manual_minutes": manual_min, "auto_minutes": auto_min,
                        "speedup": round(manual_min / max(1, auto_min), 1)}}


def run_progmap(p):
    """Auto-mapping (GP-BO) run across Igor's real programs — with per-program
    probe order for animation."""
    from bso.program_mapping import map_all
    return map_all(seed=0)


def run_comment(p):
    """Proactive agent comment on a tab's measured result."""
    from bso.dashboard_agent import comment_on_tab
    tab = p.get("tab", "")
    lang = p.get("lang", "en")
    m = {}
    for k, v in p.items():
        if k in ("tab", "lang"):
            continue
        try:
            m[k] = float(v)
        except (TypeError, ValueError):
            m[k] = v
    if "manual_minutes" in m or "auto_minutes" in m:
        m["mapping"] = {"manual_minutes": m.get("manual_minutes"),
                        "auto_minutes": m.get("auto_minutes"),
                        "speedup": m.get("speedup")}
    return {"text": comment_on_tab(tab, m, lang=lang)}


def run_gym(p):
    """NeuroStim Gym — reproducible benchmark scorecard + digital-twin pre-optimization."""
    from bso.neurostim_gym import benchmark, digital_twin_preoptimize
    return {"benchmark": benchmark(n_patients=int(p.get("n", 16))),
            "twin": digital_twin_preoptimize(int(p.get("patient", 0)))}


def run_autotrain(p):
    """Scheduled autonomic training: 24-h bladder schedule + multi-week training trend."""
    from bso.autonomic_training import schedule_24h, simulate_bladder_day, simulate_training_curve
    interval = float(p.get("interval_h", 4.0))
    return {"schedule": schedule_24h(),
            "day": simulate_bladder_day(interval_h=interval, trained=float(p.get("trained", 0.0))),
            "training": simulate_training_curve(weeks=8)}


def run_predictive(p):
    """Shadow Step invention demo: anticipatory (feed-forward) dorsiflexion vs
    reactive, on the instant twin and the physiological Hill-muscle twin. Returns
    per-arm metrics for both twins + an ankle-angle trace (reactive vs predictive)
    so the dashboard can show the foot lifting EARLIER under prediction."""
    from bso.biomech.kinematic import KinematicModel
    from bso.feedback import FOOT_DRAG_ANKLE_DEG

    DT, DUR, WARM = 0.005, 16.0, 4.0
    LEAD_MS, GAIN, TAIL = 100.0, 1.5, 0.5

    def run(mode, hill):
        sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=0.6)]
        model = KinematicModel(use_muscles=True) if hill else KinematicModel()
        s = build_system(sched, dt=DT, model=model)
        s.feedback.mode = mode
        s.feedback.lead_ms, s.feedback.pred_gain, s.feedback.pred_tail_gain = LEAD_MS, GAIN, TAIL
        return s.run(DUR)

    def metrics(rec):
        drag = swing = 0
        worst = 1e9
        effort = 0.0
        for i, t in enumerate(rec.t):
            if t < WARM:
                continue
            gp = rec.gait_phase[i] or {}
            cp = gp.get("cycle_phase")
            if cp is None or gp.get("cadence", 0.0) <= 0.0:
                continue
            pose, act = rec.pose[i], (rec.activations[i] or {})
            effort += act.get("L_ankle_dorsi", 0.0) + act.get("R_ankle_dorsi", 0.0)
            for side, lp in (("L", cp), ("R", (cp + 0.5) % 1.0)):
                if 0.60 <= lp <= 1.0:
                    swing += 1
                    if pose.get(f"{side}_ankle", 0.0) <= FOOT_DRAG_ANKLE_DEG:
                        drag += 1
                    worst = min(worst, pose.get(f"{side}_foot_y", 0.0))
        return {"drag_pct": round(100.0 * drag / max(1, swing), 1),
                "min_clear_cm": round(100.0 * worst, 2),
                "dorsi_effort": round(effort, 1)}

    def trace(rec):
        # ~2 gait cycles after warmup: left-leg cycle_phase, ankle angle, dorsi cmd
        out = []
        for i, t in enumerate(rec.t):
            if t < WARM + 1.0 or t > WARM + 4.0:
                continue
            gp = rec.gait_phase[i] or {}
            cp = gp.get("cycle_phase")
            if cp is None:
                continue
            pose, act = rec.pose[i], (rec.activations[i] or {})
            out.append({"t": round(t, 3), "phase": round(cp, 3),
                        "ankle": round(pose.get("L_ankle", 0.0), 2),
                        "dorsi": round(act.get("L_ankle_dorsi", 0.0), 3)})
        st = max(1, len(out) // 160)
        return out[::st]

    twins = {}
    for key, hill in (("instant", False), ("hill", True)):
        twins[key] = {m: metrics(run(m, hill)) for m in ("off", "reactive", "predictive")}
    tr = {"reactive": trace(run("reactive", True)),
          "predictive": trace(run("predictive", True))}
    return {"twins": twins, "trace": tr, "drag_threshold_deg": FOOT_DRAG_ANKLE_DEG,
            "params": {"lead_ms": LEAD_MS, "gain": GAIN, "tail": TAIL}}


def run_usedriven(p):
    """Use-driven assist demo: sweep fixed assist 0..1 + the adaptive (fading)
    protocol, returning lasting recovery R (stim OFF) for each."""
    from bso.plasticity import optimal_assist
    return optimal_assist(n_sessions=int(p.get("sessions", 40)))


def run_handpacer(p):
    """Hand-pacer demo: leg decoder stuck while the patient speeds up; the arm
    rhythm tracks the true cadence, the free-running clock does not. Returns the
    before/after cadence per arm + a sampled cadence(t) trace for each."""
    from bso.decoder_stub import IntentEvent
    from bso.runtime import build_system

    DT, DUR, T_CHANGE = 0.005, 12.0, 6.0
    TRUE_BEFORE, TRUE_AFTER, DEC_SPEED = 60.0, 84.0, 0.333

    def true_cadence(t):
        return TRUE_BEFORE if t < T_CHANGE else TRUE_AFTER

    def run(hand):
        sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=DEC_SPEED)]
        kw = {"hand_cadence": true_cadence} if hand else {}
        return build_system(sched, dt=DT, **kw).run(DUR)

    def achieved(rec, t0, t1):
        cycles = 0.0
        prev = None
        for i, t in enumerate(rec.t):
            if not (t0 <= t <= t1):
                continue
            cp = (rec.gait_phase[i] or {}).get("cycle_phase")
            if cp is None:
                continue
            if prev is not None:
                d = cp - prev
                if d < -0.5:
                    d += 1.0
                cycles += max(0.0, d)
            prev = cp
        return round(2.0 * cycles / max((t1 - t0) / 60.0, 1e-9), 1)

    def trace(rec):
        out = []
        for i, t in enumerate(rec.t):
            if t < 1.2:
                continue
            cad = (rec.gait_phase[i] or {}).get("cadence")
            if cad:
                out.append({"t": round(t, 2), "cad": round(cad, 1)})
        st = max(1, len(out) // 160)
        return out[::st]

    free, hand = run(False), run(True)
    return {"true_before": TRUE_BEFORE, "true_after": TRUE_AFTER, "t_change": T_CHANGE,
            "free": {"before": achieved(free, 2.0, T_CHANGE - 0.5),
                     "after": achieved(free, T_CHANGE + 1.0, DUR - 0.5)},
            "hand": {"before": achieved(hand, 2.0, T_CHANGE - 0.5),
                     "after": achieved(hand, T_CHANGE + 1.0, DUR - 0.5)},
            "trace": {"free": trace(free), "hand": trace(hand)}}


def run_duallock(p):
    """Dual-lock demo: EES priming + selective periphery vs single-channel EES,
    charge + spillover for the same net force, swept over current-spread coupling."""
    from bso.dual_lock import compare
    return {"target_net": 0.5,
            "rows": [compare(0.5, c) for c in (0.0, 0.1, 0.2, 0.3, 0.4)]}


def run_balance(p):
    """Sensory closed-loop demo: standing as an inverted pendulum under three
    sensory modes (none / position-only / proprioceptive)."""
    from bso.balance_sensory import compare
    return compare()


def run_reflex(p):
    """Reflex-as-amplifier demo: sweep spinal loop gain — insufficient / weight-
    bearing window / clonus — with a small fixed central drive."""
    from bso.reflex_amp import sweep
    return sweep()


def run_electrodes(p):
    """Igor's electrode paddle layout (the 5-6-5 paddle array) with anatomical labels."""
    from bso.electrode_array import layout
    return layout(lang=p.get("lang", "en"))


def run_plan(p):
    """Agent's contact + parameter recommendation for a goal (learned from real data)."""
    from bso.stim_planner import learn_rules, recommend_parameters
    goal = p.get("goal", "walking")
    lang = p.get("lang", "en")
    return {"goal": goal, "recommendation": recommend_parameters(goal, lang=lang),
            "learned_rules": learn_rules()}


def run_overview(p):
    """Agent's holistic session verdict across all verticals."""
    from bso.dashboard_agent import session_summary
    return {"text": session_summary(lang=p.get("lang", "en"))}


def run_ask(p):
    """In-dashboard assistant: answer a question about Igor's data/system."""
    from bso.dashboard_agent import answer
    q = p.get("q", "").strip()
    state = None
    if "intent" in p:
        state = {"intent": p.get("intent"),
                 "intent_conf": float(p.get("intent_conf", 0.9)),
                 "sparing": float(p.get("sparing", 0.7)),
                 "bladder_pressure": float(p.get("bladder_pressure", 22.0)),
                 "ad_bp_rise": float(p.get("ad_bp_rise", 0.0))}
    lang = p.get("lang", "en")
    if not q:
        msg = ("Ask about the programs, safety or how the system works." if lang != "ua"
               else "Постав питання про програми, безпеку чи роботу системи.")
        return {"text": msg, "source": "fallback"}
    return answer(q, state=state, lang=lang)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _api(self, name, payload, source="illustrative"):
        """Send a JSON API response through the backend↔frontend contract: wrap it
        with version + data source, and warn (server-side) on contract drift."""
        from bso.api_schema import check_contract, envelope
        warn = check_contract(name, payload)
        self._send(200, json.dumps(envelope(payload, source, warn)))

    def _content_len(self):
        """Parse Content-Length defensively (a non-numeric header yields 0, not a 500)."""
        try:
            return int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            return 0

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        for key in ("fatigue", "adapt", "modulation"):
            if key in q:
                q[key] = q[key] in ("1", "true", "on", "yes")
        try:
            # backend↔frontend contract: each run_*(q) returns a dict, wrapped by
            # _api with its data source (real = Igor's actual data, cached = precomputed,
            # illustrative = simulation placeholder).
            api_get = {
                "/api/locomotion": (run_locomotion, "illustrative"),
                "/api/autonomic": (run_autonomic, "illustrative"),
                "/api/mapping": (run_mapping, "illustrative"),
                "/api/guardian": (run_guardian, "illustrative"),
                "/api/opensim": (run_opensim_view, "cached"),
                "/api/opensim_mesh": (run_opensim_mesh, "cached"),
                "/api/sensors": (run_sensors, "illustrative"),
                "/api/programs": (run_programs, "real"),
                "/api/ask": (run_ask, "illustrative"),
                "/api/progmap": (run_progmap, "illustrative"),
                "/api/comment": (run_comment, "illustrative"),
                "/api/overview": (run_overview, "illustrative"),
                "/api/electrodes": (run_electrodes, "real"),
                "/api/predictive": (run_predictive, "illustrative"),
                "/api/usedriven": (run_usedriven, "illustrative"),
                "/api/handpacer": (run_handpacer, "illustrative"),
                "/api/duallock": (run_duallock, "illustrative"),
                "/api/balance": (run_balance, "illustrative"),
                "/api/reflex": (run_reflex, "illustrative"),
                "/api/plan": (run_plan, "illustrative"),
                "/api/autotrain": (run_autotrain, "illustrative"),
                "/api/gym": (run_gym, "illustrative"),
                "/api/unified": (run_unified, "illustrative"),
                "/api/cohort": (run_cohort, "illustrative"),
                "/api/recovery": (run_recovery, "illustrative"),
                "/api/fusion": (run_fusion, "illustrative"),
                "/api/twin": (run_twin, "illustrative"),
                "/api/telemetry": (run_telemetry, "illustrative"),
                "/api/autonomic_clinical": (run_autonomic_clinical, "illustrative"),
                "/api/urodynamics": (run_urodynamics, "illustrative"),
                "/api/bladder_report": (run_bladder_report, "illustrative"),
            }
            if u.path in api_get:
                fn, source = api_get[u.path]
                self._api(u.path, fn(q), source)
            elif u.path == "/api/source":
                self._send(200, json.dumps(read_source(q.get("path", ""))))
            elif u.path == "/api/moco":
                mp = os.path.join(CACHE_DIR, "moco.json")
                if not os.path.exists(mp):
                    mp = os.path.join(os.path.dirname(HERE), "outputs", "moco_muscles.json")
                if os.path.exists(mp):
                    with open(mp) as f:
                        self._send(200, f.read())
                else:
                    self._send(200, json.dumps({"error": "run scenarios/moco_inverse.py first"}))
            elif u.path == "/api/proposal":
                from bso.clinical_approval import N_PROPOSALS, build_proposal, list_decisions
                from bso.recovery import RecoveryDB
                db = RecoveryDB(path=CLINIC_DB)
                log = list_decisions(db)
                idx = len(log)
                prop = build_proposal(idx, q.get("lang", "en")) if idx < N_PROPOSALS else None
                self._api("/api/proposal", {"proposal": prop, "log": log,
                                            "reviewed": idx, "total": N_PROPOSALS}, "illustrative")
            elif u.path in ("/", "/index.html"):
                with open(os.path.join(HERE, "index.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            elif u.path.startswith("/vendor/"):
                name = os.path.basename(u.path)
                fp = os.path.join(HERE, "vendor", name)
                if os.path.isfile(fp):
                    ctype = ("application/javascript" if name.endswith(".js")
                             else "model/gltf-binary" if name.endswith(".glb")
                             else "application/octet-stream")
                    with open(fp, "rb") as f:
                        self._send(200, f.read(), ctype)
                else:
                    self._send(404, "not found", "text/plain")
            else:
                self._send(404, "not found", "text/plain")
        except Exception as e:  # surface errors to the client
            self._send(500, json.dumps({"error": str(e)}))

    def do_POST(self):
        u = urlparse(self.path)
        try:
            if u.path == "/api/sensors":
                n = self._content_len()
                if n > 2_000_000:                       # cap upload (~2 MB) — a sensor CSV is tiny; refuse oversized payloads
                    self._send(413, json.dumps({"error": "payload too large (max 2 MB)"}))
                    return
                raw = self.rfile.read(n).decode("utf-8", "replace") if n else ""
                rows = []
                for line in raw.splitlines():
                    line = line.strip()
                    if not line or line[0].isalpha():  # skip header/blank
                        continue
                    parts = [x for x in line.replace(",", " ").split() if x]
                    try:
                        rows.append([float(x) for x in parts[:5]])
                    except ValueError:
                        continue
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                self._send(200, json.dumps(run_sensors(q, rows=rows or None)))
            elif u.path == "/api/proposal/decide":
                import datetime

                from bso.clinical_approval import (N_PROPOSALS, build_proposal,
                                                   list_decisions, log_decision)
                from bso.recovery import RecoveryDB
                n = self._content_len()
                if n > 200_000:
                    self._send(413, json.dumps({"error": "payload too large"}))
                    return
                body = json.loads(self.rfile.read(n).decode("utf-8", "replace")) if n else {}
                lang = body.get("lang", "en")
                db = RecoveryDB(path=CLINIC_DB)
                idx = len(list_decisions(db))
                if idx >= N_PROPOSALS:
                    self._send(200, json.dumps({"ok": False, "log": list_decisions(db),
                                                "proposal": None, "reviewed": idx,
                                                "total": N_PROPOSALS}))
                    return
                prop = build_proposal(idx, lang)             # the one the clinician saw
                decision = body.get("decision", "approve")
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_decision(db, ts, prop, decision, note=body.get("note", ""))
                log = list_decisions(db)
                nxt = build_proposal(len(log), lang) if len(log) < N_PROPOSALS else None
                self._send(200, json.dumps({"ok": True, "log": log, "proposal": nxt,
                                            "reviewed": len(log), "total": N_PROPOSALS}))
            else:
                self._send(404, "not found", "text/plain")
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}))


def main(port=None):
    # PORT + 0.0.0.0 so it runs on a cloud host (Railway/Render); falls back to
    # localhost:8765 for local use.
    env_port = os.environ.get("PORT")
    port = int(env_port) if env_port else (port or 8765)
    host = "0.0.0.0" if env_port else "127.0.0.1"
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"BSO dashboard on {host}:{port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
