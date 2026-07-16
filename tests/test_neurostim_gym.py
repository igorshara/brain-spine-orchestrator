"""NeuroStim Gym — open benchmark for SCI neurostimulation algorithms."""

from __future__ import annotations

from bso.neurostim_gym import (
    TASKS,
    NeuroStimEnv,
    Patient,
    benchmark,
    digital_twin_preoptimize,
)


def test_patient_is_reproducible():
    a, b = Patient(seed=7), Patient(seed=7)
    assert a.best_contact == b.best_contact and a.func_amp == b.func_amp


def test_env_api_reset_step():
    env = NeuroStimEnv("contact_mapping", seed=1)
    obs = env.reset()
    assert "t" in obs
    obs, r, done, info = env.step(env.patient.best_contact)
    assert r > 0.9 and "safety_violations" in info     # best contact → high selectivity


def test_amplitude_safety_penalty():
    env = NeuroStimEnv("amplitude_titration", seed=2)
    env.reset()
    _, r, _, info = env.step(19.0)                      # above safe limit
    assert r < 0 and info["safety_violations"] == 1


def test_benchmark_gpbo_beats_random_on_efficiency_and_safety():
    b = benchmark(n_patients=12)
    sc = b["scorecard"]
    # sample-efficiency: GP-BO needs fewer steps to map a contact than random
    steps = {a: sc[a]["contact_mapping"]["steps_to_target"] for a in ("gp_bo", "random")}
    assert steps["gp_bo"] < steps["random"]
    # safety: GP-BO titrates amplitude with fewer violations than random
    viol = {a: sc[a]["amplitude_titration"]["safety_violations"] for a in ("gp_bo", "random")}
    assert viol["gp_bo"] < viol["random"]


def test_benchmark_is_reproducible():
    assert benchmark(n_patients=8) == benchmark(n_patients=8)


def test_digital_twin_outputs_programs():
    d = digital_twin_preoptimize(0)
    assert len(d["programs"]) == 3 and d["total_insilico_probes"] > 0
    for p in d["programs"]:
        assert 1 <= p["best_contact"] <= 16


def test_all_tasks_runnable():
    for t in TASKS:
        env = NeuroStimEnv(t, seed=0)
        env.reset()
        env.step(env.action_space.get("low", 0) if env.action_space["type"] == "box" else 0)
