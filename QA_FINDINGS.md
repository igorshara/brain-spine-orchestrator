# QA_FINDINGS — brain-spine-orchestrator
_Згенеровано Opora QA Fleet · 2026-07-16 · 🔴1 🟡15 ⚪31_

> Оцінено без LLM (сирі сканери).

Завдання на виправлення (за пріоритетом). Кодинг-агент може брати в роботу зверху вниз.

## 🔴 P0
- [ ] **B324: Use of weak SHA1 hash for security. Consider usedforsecurity=False** — `src/bso/clinical_approval.py:91`
  - confidence=HIGH; 90         p["safety_note"] = "within safety envelope" if lang != "ua" else "у межах безпеки"
91     p["id"] = hashlib.sha1((p["target"] + p["summary"]).encode()).hexdigest()[:8]
92     return p

## 🟡 P1
- [ ] **Хардкод /tmp/cpg_kin.sto в demo-сценарії** — `scenarios/moco_inverse.py:90`
  - confidence=MEDIUM; 89     tab.addTableMetaDataString("inDegrees", "no")
90     osim.STOFileAdapter.write(tab, "/tmp/cpg_kin.sto")
91
- [ ] **Читання з /tmp/cpg_kin.sto хардкодом** — `scenarios/moco_inverse.py:99`
  - confidence=MEDIUM; 98     inv.setModel(mp)
99     tp = osim.TableProcessor("/tmp/cpg_kin.sto")
100     tp.append(osim.TabOpLowPassFilter(8))
- [ ] **f-string DELETE FROM {t} у demo-recovery** — `scenarios/recovery_demo.py:55`
  - confidence=MEDIUM; 54     for t in ("metrics", "sessions", "programs", "leads", "partners", "tasks"):
55         db.conn.execute(f"DELETE FROM {t}")
56     db.conn.commit()
- [ ] **ET.parse без захисту від XXE/billion-laughs** — `src/bso/biomech/opensim_model.py:138`
  - confidence=HIGH; 137     import xml.etree.ElementTree as ET
138     root = ET.parse(path).getroot()
139     piece = root.find(".//Piece")
- [ ] **Хардкод /tmp для STO-файлу** — `scenarios/moco_dataset.py:57`
  - confidence=MEDIUM; 56         return None
57     ms.write("/tmp/ds_sol.sto")
58     lines = open("/tmp/ds_sol.sto").read().splitlines()
- [ ] **Читання з хардкодженого /tmp** — `scenarios/moco_dataset.py:58`
  - confidence=MEDIUM; 57     ms.write("/tmp/ds_sol.sto")
58     lines = open("/tmp/ds_sol.sto").read().splitlines()
59     hi = [i for i, ln in enumerate(lines) if ln.strip() == "endheader"][0]
- [ ] **/tmp/moco_inverse_solution.sto** — `scenarios/moco_inverse.py:144`
  - confidence=MEDIUM; 143         print(f"MOCO RAN. converged={success}, objective={ms.getObjective():.3f}")
144         ms.write("/tmp/moco_inverse_solution.sto")
145         print("solution written -> /tmp/moco_inverse_s
- [ ] **_export_json з /tmp шляху** — `scenarios/moco_inverse.py:146`
  - confidence=MEDIUM; 145         print("solution written -> /tmp/moco_inverse_solution.sto")
146         _export_json("/tmp/moco_inverse_solution.sto")
147         if success:
- [ ] **Запис /tmp/track_ref.sto** — `scenarios/moco_track.py:79`
  - confidence=MEDIUM; 78     tab.addTableMetaDataString("inDegrees", "no")
79     osim.STOFileAdapter.write(tab, "/tmp/track_ref.sto")
80
- [ ] **Читання /tmp/track_ref.sto** — `scenarios/moco_track.py:89`
  - confidence=MEDIUM; 88     track.setModel(mp)
89     track.setStatesReference(osim.TableProcessor("/tmp/track_ref.sto"))
90     track.set_states_global_tracking_weight(1.0)
- [ ] **/tmp/moco_track_solution.sto запис** — `scenarios/moco_track.py:109`
  - confidence=MEDIUM; 108         if success:
109             sol.write("/tmp/moco_track_solution.sto")
110             import numpy as _np
- [ ] **Читання /tmp/moco_track_solution.sto** — `scenarios/moco_track.py:111`
  - confidence=MEDIUM; 110             import numpy as _np
111             ls = open("/tmp/moco_track_solution.sto").read().splitlines()
112             hi = [i for i, x in enumerate(ls) if x.strip() == "endheader"][0]
- [ ] **B608 хибна тривога у dashboard_agent** — `src/bso/dashboard_agent.py:244`
  - confidence=LOW; 243         return (
244             f"Big picture. You have {s['n_programs']} real stimulator programs (banks "
245             f"{', '.join(s['groups'])}) — the system speaks the clinical partner's 
- [ ] **B608: Possible SQL injection vector through string-based query construction.** — `src/bso/recovery.py:56`
  - confidence=MEDIUM; 55         qs = ",".join("?" * len(cols))
56         cur = self.conn.execute(f"INSERT INTO {table}({keys}) VALUES({qs})", tuple(cols.values()))
57         self.conn.commit()
- [ ] **B608: Possible SQL injection vector through string-based query construction.** — `src/bso/recovery.py:87`
  - confidence=LOW; 86     def rows(self, table, where="", params=()):
87         q = f"SELECT * FROM {table}" + (f" WHERE {where}" if where else "")
88         return [dict(r) for r in self.conn.execute(q, params)]

## ⚪ P2
- [ ] **ruff E702 ×2: Multiple statements on one line (semicolon)** — `Users/igorsharanda/claude-projects/brain-spine-orchestrator/tests/test_urodynamics.py:7`
  - 2 випадків правила E702.
- [ ] **ruff F841 ×1: Local variable `span` is assigned to but never used** — `Users/igorsharanda/claude-projects/brain-spine-orchestrator/scenarios/hand_pacer.py:64`
  - 1 випадків правила F841.
- [ ] **ruff E501 ×59: Line too long (101 > 100)** — `Users/igorsharanda/claude-projects/brain-spine-orchestrator/scenarios/predictive_step.py:89`
  - 59 випадків правила E501.
- [ ] **ruff F401 ×4: `bso.plasticity.use_driven_course` imported but unused** — `Users/igorsharanda/claude-projects/brain-spine-orchestrator/scenarios/use_driven_assist.py:23`
  - 4 випадків правила F401.
- [ ] **ruff B905 ×2: `zip()` without an explicit `strict=` parameter** — `Users/igorsharanda/claude-projects/brain-spine-orchestrator/scenarios/use_driven_assist.py:34`
  - 2 випадків правила B905.
- [ ] **ruff I001 ×6: Import block is un-sorted or un-formatted** — `Users/igorsharanda/claude-projects/brain-spine-orchestrator/src/bso/autonomic_clinical.py:12`
  - 6 випадків правила I001.
- [ ] **ruff UP037 ×2: Remove quotes from type annotation** — `Users/igorsharanda/claude-projects/brain-spine-orchestrator/src/bso/config/muscles.py:37`
  - 2 випадків правила UP037.
- [ ] **assert у pytest-тесті адаптації** — `tests/test_adaptation.py:38`
  - confidence=HIGH; 37     degraded = build_system(SCHED, fatigue=_fatigue()).run(DUR)
38     assert _late_clearance(degraded) < _late_clearance(nominal) * 0.8
39
- [ ] **assert у тесті ефекту адаптації** — `tests/test_adaptation.py:44`
  - confidence=HIGH; 43     adapted = build_system(SCHED, fatigue=_fatigue(), adapt=True).run(DUR)
44     assert _late_clearance(adapted) > _late_clearance(degraded) * 1.2, (
45         "adaptation should retain meaningfu
- [ ] **assert на gains після адаптації** — `tests/test_adaptation.py:51`
  - confidence=HIGH; 50     adapted = build_system(SCHED, fatigue=_fatigue(), adapt=True).run(DUR)
51     assert adapted.gains[-1]["L_knee_flex"] > 1.2
52
- [ ] **assert на діапазон gains** — `tests/test_adaptation.py:58`
  - confidence=HIGH; 57     final = adapted.gains[-1]
58     assert all(abs(v - 1.0) < 0.3 for v in final.values())
59
- [ ] **assert на amplitude_mA ліміти** — `tests/test_adaptation.py:65`
  - confidence=HIGH; 64         for c in cmds:
65             assert c.amplitude_mA <= LIMITS.amplitude_max_mA + 1e-9
66             assert c.charge_per_phase_uC <= LIMITS.charge_per_phase_max_uC + 1e-9
- [ ] **assert на charge_per_phase_uC** — `tests/test_adaptation.py:66`
  - confidence=HIGH; 65             assert c.amplitude_mA <= LIMITS.amplitude_max_mA + 1e-9
66             assert c.charge_per_phase_uC <= LIMITS.charge_per_phase_max_uC + 1e-9
67
- [ ] **assert для перевірки розміру параметрів у learned_adaptation** — `src/bso/learned_adaptation.py:38`
  - confidence=HIGH; 37     def set_params(self, p: np.ndarray) -> None:
38         assert len(p) == self.size, f"expected {self.size} params, got {len(p)}"
39         i = 0
- [ ] **os.execv для перезапуску в MOCO-скрипті** — `scenarios/moco_inverse.py:32`
  - confidence=MEDIUM; 31     os.environ["_BSO_MOCO_DYLD"] = "1"
32     os.execv(sys.executable, [sys.executable, *sys.argv])
33
- [ ] **try/except/pass навколо Logger.setLevelString** — `src/bso/biomech/opensim_model.py:62`
  - confidence=HIGH; 61         osim.Logger.setLevelString("Off")
62     except Exception:
63         pass
64     model = osim.Model(model_path or os.path.abspath(DEFAULT_MODEL))
- [ ] **xml.etree для парсингу .vtp геометрії** — `src/bso/biomech/opensim_model.py:137`
  - confidence=HIGH; 136     """Parse an ASCII VTK PolyData (.vtp) -> (verts flat [x,y,z,...], faces [i,j,k,...])."""
137     import xml.etree.ElementTree as ET
138     root = ET.parse(path).getroot()
- [ ] **try/except/pass у Model loader** — `src/bso/biomech/opensim_model.py:207`
  - confidence=HIGH; 206             osim.Logger.setLevelString("Off")  # silence missing-geometry warnings
207         except Exception:
208             pass
209         self.model = osim.Model(model_path or os.path.absp
- [ ] **assert within_limits() у clinical_mapping** — `src/bso/clinical_mapping.py:127`
  - confidence=HIGH; 126         cfg = self._cfg(self._candidates[int(np.argmax(acq))])
127         assert cfg.within_limits()  # never propose an unsafe config
128         return cfg
- [ ] **os.execv для перезапуску з DYLD** — `scenarios/moco_dataset.py:25`
  - confidence=MEDIUM; 24     os.environ["_BSO_MOCO_DYLD"] = "1"
25     os.execv(sys.executable, [sys.executable, *sys.argv])
26
- [ ] **os.execv у moco_track** — `scenarios/moco_track.py:26`
  - confidence=MEDIUM; 25     os.environ["_BSO_MOCO_DYLD"] = "1"
26     os.execv(sys.executable, [sys.executable, *sys.argv])
27
- [ ] **assert у тесті ad_guardian** — `tests/test_ad_guardian.py:12`
  - confidence=HIGH; 11         info = g.observe(t * 1.0, 5.0 + t * 2.0)  # pressure rising 2/s
12     assert info["slope"] > 1.0
13     assert info["forecast"] > 5.0 + 5 * 2.0  # forecast extrapolates upward
- [ ] **assert у тесті** — `tests/test_ad_guardian.py:13`
  - confidence=HIGH; 12     assert info["slope"] > 1.0
13     assert info["forecast"] > 5.0 + 5 * 2.0  # forecast extrapolates upward
14
- [ ] **assert у тесті** — `tests/test_ad_guardian.py:20`
  - confidence=HIGH; 19     _, pred = simulate("predictive")
20     assert none["ad_events"] > 50            # unmanaged dyssynergia floods AD
21     assert pred["ad_events"] == 0            # predictive prevents it entir
- [ ] **assert у тесті** — `tests/test_ad_guardian.py:21`
  - confidence=HIGH; 20     assert none["ad_events"] > 50            # unmanaged dyssynergia floods AD
21     assert pred["ad_events"] == 0            # predictive prevents it entirely
22     assert pred["ad_events"] < re
- [ ] **assert у тесті** — `tests/test_ad_guardian.py:22`
  - confidence=HIGH; 21     assert pred["ad_events"] == 0            # predictive prevents it entirely
22     assert pred["ad_events"] < react["ad_events"]  # better than reactive
23     assert pred["peak_pressure"] < non
- [ ] **assert у тесті** — `tests/test_ad_guardian.py:23`
  - confidence=HIGH; 22     assert pred["ad_events"] < react["ad_events"]  # better than reactive
23     assert pred["peak_pressure"] < none["peak_pressure"]
24
- [ ] **assert у тесті** — `tests/test_ad_guardian.py:30`
  - confidence=HIGH; 29     # faster filling -> the guardian warns at least as early (smaller/equal time)
30     assert fast["first_warning_s"] is not None and slow["first_warning_s"] is not None
31     assert fast["first
- [ ] **assert у тесті** — `tests/test_ad_guardian.py:31`
  - confidence=HIGH; 30     assert fast["first_warning_s"] is not None and slow["first_warning_s"] is not None
31     assert fast["first_warning_s"] <= slow["first_warning_s"] + 1e-6
32     assert fast["ad_events"] == 0 a
- [ ] **assert у тесті** — `tests/test_ad_guardian.py:32`
  - confidence=HIGH; 31     assert fast["first_warning_s"] <= slow["first_warning_s"] + 1e-6
32     assert fast["ad_events"] == 0 and slow["ad_events"] == 0
- [ ] **B101: Use of assert detected. The enclosed code will be removed when compiling to optimised byte code.** — `src/bso/recovery.py:62`
  - confidence=HIGH; 61     def log_metric(self, date, domain, score, note=""):
62         assert domain in DOMAINS, f"domain must be one of {DOMAINS}"
63         return self._ins("metrics", date=date, domain=domain, scor
