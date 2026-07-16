"""Igor's electrode paddle — the 5-6-5 paddle array (16 contacts), anatomically labeled.

16 контактів = паддл a 16-contact paddle array: 3 колонки (5 ліворуч, 6 посередині,
5 праворуч), імплантований над попереково-крижовим відділом (зазвичай хребці T11–L1). Це
ТА САМА пластина, яку команда leading researchers використала у a published trial (Wagner et al., Nature 2018).

Мітки контактів (який за що відповідає) — з опублікованої анатомії EES:
  • рострально (вгорі, ~L1–L2): згиначі стегна (iliopsoas) / тулуб;
  • L2–L4 (median L3): розгиначі коліна (quadriceps/rectus femoris) — СТОЯННЯ;
  • L4–L5: tibialis anterior (тильне згинання, фаза переносу) + hamstrings;
  • L5–S1 (median L5): triceps surae/gastrocnemius (підошовне згинання) — поштовх, СТОЯННЯ;
  • S2: тазове дно / сечовий міхур / кишківник / ерекція (автономні).
  Серединна колонка → сегментарна специфічність/білатерально/вісь; бічні → ліва/права нога.
Джерела: Greiner 2021 (spinal motor mapping, PMC7773960), a published trial (2018) (a published trial),
Capogrosso/leading researchers spatiotemporal.

⚠️ ЧЕСНО: це ТИПОВА мапа EES. Точне «контакт→м'яз» для Ігоря залежить від реального
положення пластини (рентген) — підтвердити у the clinical partner. Тут — обґрунтована стартова гіпотеза.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Contact:
    id: int
    col: str          # 'L' | 'M' | 'R'
    row: int          # 0 = rostral (top) .. caudal (bottom)
    level: str        # estimated spinal segment, e.g. 'L3'
    side: str         # 'left' | 'mid' | 'right'
    target: str       # muscle / function (UA)
    role: str         # flexor | extensor | dorsiflexor | autonomic | axial

    def as_dict(self) -> dict:
        return {"id": self.id, "col": self.col, "row": self.row, "level": self.level,
                "side": self.side, "target": self.target, "role": self.role}


def _c(i, col, row, level, side, target, role):
    return Contact(i, col, row, level, side, target, role)


# 5-6-5 layout, rostral (row 0) -> caudal. Mid column carries the 6; sides 5 each.
CONTACTS: list[Contact] = [
    # --- middle column (6): midline / bilateral / axial ---
    _c(1, "M", 0, "L1", "mid", "trunk / axial", "axial"),
    _c(2, "M", 1, "L2", "mid", "hip flexors, bilateral", "flexor"),
    _c(3, "M", 2, "L3", "mid", "knee extensors (quadriceps) — standing", "extensor"),
    _c(4, "M", 3, "L4", "mid", "knee/shank transition", "extensor"),
    _c(5, "M", 4, "S1", "mid", "plantarflexion (gastroc) — standing", "extensor"),
    _c(6, "M", 5, "S2", "mid", "pelvic / bladder / bowel / erectile", "autonomic"),
    # --- left column (5): left leg ---
    _c(7, "L", 0, "L2", "left", "left hip — flexor (pull up)", "flexor"),
    _c(8, "L", 1, "L3", "left", "left knee — extensor", "extensor"),
    _c(9, "L", 2, "L4", "left", "left foot — dorsiflexion (swing)", "dorsiflexor"),
    _c(10, "L", 3, "L5", "left", "left hamstring", "flexor"),
    _c(11, "L", 4, "S1", "left", "left calf — push-off", "extensor"),
    # --- right column (5): right leg ---
    _c(12, "R", 0, "L2", "right", "right hip — flexor (pull up)", "flexor"),
    _c(13, "R", 1, "L3", "right", "right knee — extensor", "extensor"),
    _c(14, "R", 2, "L4", "right", "right foot — dorsiflexion (swing)", "dorsiflexor"),
    _c(15, "R", 3, "L5", "right", "right hamstring", "flexor"),
    _c(16, "R", 4, "S1", "right", "right calf — push-off", "extensor"),
]

# Ukrainian labels (kept as the additional language for the toggle).
TARGET_UA = {
    1: "тулуб / вісь", 2: "згиначі стегна, білатерально",
    3: "розгиначі коліна (quadriceps) — стояння", 4: "коліно/гомілка перехід",
    5: "підошовне згинання (gastroc) — стояння", 6: "таз / міхур / кишківник / ерекція",
    7: "ліве стегно — згинач (pull up)", 8: "ліве коліно — розгинач",
    9: "ліва стопа — тильне згин. (перенос)", 10: "ліве підколінне (hamstring)",
    11: "ліва литка — поштовх", 12: "праве стегно — згинач (pull up)",
    13: "праве коліно — розгинач", 14: "права стопа — тильне згин. (перенос)",
    15: "праве підколінне (hamstring)", 16: "права литка — поштовх",
}

N = len(CONTACTS)
_BY_ID = {c.id: c for c in CONTACTS}


def by_id(i: int) -> Contact:
    return _BY_ID[i]


# Which contacts each functional goal would engage (anatomy-driven hypothesis).
GOAL_CONTACTS: dict[str, list[int]] = {
    "walking": [7, 12, 9, 14, 3, 5],     # alternate hip/dorsiflexors (swing) + extensors (stance)
    "standing": [3, 5, 8, 13, 11, 16],   # bilateral knee + ankle extensors (postural)
    "trunk": [1, 2],                     # axial / proximal
    "pulling_up": [7, 12],               # hip flexors (sit -> pull up)
    "pushing": [11, 16],                 # plantarflexors (push)
    "decrease_spasticity": [2, 3, 4, 5],  # broad tonic midline
    "overnight": [1, 6],                 # low axial / autonomic maintenance
    # autonomic recovery targets Igor cares about most:
    "bladder": [6], "bowel": [6], "erectile": [6],
}


def contacts_for_goal(goal: str) -> list[Contact]:
    return [by_id(i) for i in GOAL_CONTACTS.get(goal, [])]


def layout(lang: str = "en") -> dict:
    """Paddle layout + per-contact labels for the dashboard."""
    contacts = []
    for c in CONTACTS:
        d = c.as_dict()
        if lang == "ua":
            d["target"] = TARGET_UA.get(c.id, d["target"])
        contacts.append(d)
    return {"name": "the 5-6-5 paddle array (16 contacts)",
            "columns": {"L": 5, "M": 6, "R": 5},
            "contacts": contacts,
            "goals": dict(GOAL_CONTACTS.items())}
