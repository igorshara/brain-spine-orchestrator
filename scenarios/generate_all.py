"""Regenerate every demo figure into outputs/ — the visual pack for partners.

Регенерує всі фігури проєкту в outputs/ одним запуском (для партнерського пакета).
Деякі сценарії повільні (MuJoCo, навчання CEM) — повний прогін ~3-5 хв.

Запуск:  python3 scenarios/generate_all.py
"""

from __future__ import annotations

import importlib
import time

import _bootstrap  # noqa: F401

SCENARIOS = [
    "walk", "sit_to_stand", "stairs", "resilience",
    "walk_mujoco", "stress_physics", "balance_recovery", "autonomic_demo",
    "learn_adaptation", "coupling_study", "muscle_gait", "managed_bladder",
    "electrode_mapping", "bopt_mapping", "opensim_gait", "opensim_muscle_driven",
    "clinical_assistant", "recovery_demo", "ad_guardian_demo", "plasticity_demo", "cohort_demo",
    "intent_demo",
]


def main() -> None:
    for name in SCENARIOS:
        t0 = time.perf_counter()
        print(f"\n########## {name} ##########")
        try:
            mod = importlib.import_module(name)
            mod.main(render=True)
            print(f"[{name}] done in {time.perf_counter() - t0:.1f}s")
        except Exception as e:  # keep going so one failure doesn't block the pack
            print(f"[{name}] FAILED: {e}")


if __name__ == "__main__":
    main()
