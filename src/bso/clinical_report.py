"""Partner-facing clinical report — urodynamics study (markdown), EN + UA.

Renders the urodynamic panel (`urodynamics.study`) into a structured report a clinical
partner can read: method, full cystometric panel baseline vs coordinated-EES,
interpretation, the <40 cmH₂O upper-tract safety verdict, a protocol recommendation and
references. Illustrative research simulation — decision-support, not a diagnosis.
"""
from __future__ import annotations

from .urodynamics import MCGUIRE_CMH2O, study

# (key, English label, Ukrainian label, unit)
_ROWS = [
    ("mcc_ml", "Max cystometric capacity", "Макс. цистометрична ємність", " mL"),
    ("p_end_fill_cmH2O", "End-fill detrusor pressure", "Тиск детрузора в кінці наповнення", " cmH₂O"),
    ("p_max_storage_cmH2O", "Max storage detrusor pressure", "Макс. тиск зберігання", " cmH₂O"),
    ("compliance_ml_cmH2O", "Bladder compliance", "Комплаєнс міхура", " mL/cmH₂O"),
    ("p_max_void_cmH2O", "Max voiding detrusor pressure", "Макс. тиск спорожнення", " cmH₂O"),
    ("qmax_ml_s", "Max flow rate (Qmax)", "Макс. потік (Qmax)", " mL/s"),
    ("pvr_ml", "Post-void residual (PVR)", "Залишковий об’єм (PVR)", " mL"),
    ("voided_ml", "Voided volume", "Виділений об’єм", " mL"),
    ("bve_pct", "Bladder voiding efficiency", "Ефективність спорожнення", " %"),
    ("dlpp_cmH2O", "Detrusor leak-point pressure", "Тиск витоку детрузора (DLPP)", " cmH₂O"),
    ("ndo_contractions", "Neurogenic detrusor overactivity", "Нейрогенна гіперактивність детрузора", ""),
    ("ad_rise_mmHg", "Autonomic-dysreflexia BP rise", "Приріст тиску (автономна дисрефлексія)", " mmHg"),
    ("dsd", "Detrusor-sphincter dyssynergia", "Детрузорно-сфінктерна дисинергія", ""),
    ("safe_storage", "Safe storage (<40 cmH₂O)", "Безпечне зберігання (<40 cmH₂O)", ""),
]


def _fmt(v, ua: bool) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return ("так" if v else "ні") if ua else ("yes" if v else "no")
    return str(v)


def urodynamics_report(lang: str = "en") -> str:
    ua = lang == "ua"
    s = study()
    b, c = s["baseline"]["metrics"], s["coordinated"]["metrics"]
    L = []
    if ua:
        L += [
            "# Уродинамічне дослідження — Brain-Spine Orchestrator", "",
            "> **Дослідницька симуляція / цифровий двійник — ІЛЮСТРАТИВНІ значення, не діагноз і "
            "не медичний виріб.** Лише підтримка рішень; вирішує лікар і застосовує на сертифікованому приладі.", "",
            "## Контекст",
            "- **Показання:** нейрогенна дисфункція нижніх сечових шляхів після травми спинного мозку "
            "(грудний рівень, напр. T5–T6), з детрузорно-сфінктерною дисинергією (DSD).",
            "- **Порівняння:** стандартний нейрогенний baseline проти **координованої епідуральної "
            "стимуляції (EES)**, що відновлює детрузорно-сфінктерну синергію.",
            "- **Метод:** in-silico цистометрограма — кероване наповнення, зберігання, тоді команда "
            "спорожнення; тиск детрузора, об’єм і потік реєструються протягом усього циклу.", "",
            "## Уродинамічна панель", "",
            "| Параметр | Початковий (DSD) | Координована EES |", "|---|---|---|",
        ]
    else:
        L += [
            "# Urodynamics Study — Brain-Spine Orchestrator", "",
            "> **Research simulation / digital twin — ILLUSTRATIVE values, not a diagnosis and not a "
            "medical device.** Decision-support only; the clinician decides and applies on a certified device.", "",
            "## Context",
            "- **Indication:** neurogenic lower urinary tract dysfunction after spinal cord injury "
            "(thoracic, e.g. T5–T6), with detrusor-sphincter dyssynergia (DSD).",
            "- **Comparison:** standard neurogenic baseline vs **coordinated epidural electrical "
            "stimulation (EES)** restoring detrusor–sphincter synergy.",
            "- **Method:** in-silico cystometrogram — controlled fill, storage, then a voiding command; "
            "detrusor pressure, volume and flow recorded throughout.", "",
            "## Urodynamic panel", "",
            "| Parameter | Baseline (DSD) | Coordinated EES |", "|---|---|---|",
        ]
    for key, en, uk, unit in _ROWS:
        label = uk if ua else en
        bv = _fmt(b[key], ua) + (unit if not isinstance(b[key], bool) and b[key] is not None else "")
        cv = _fmt(c[key], ua) + (unit if not isinstance(c[key], bool) and c[key] is not None else "")
        L.append(f"| {label} | {bv} | {cv} |")
    L.append("")
    safe = (b["safe_storage"])
    if ua:
        L += [
            "## Інтерпретація",
            f"- **Початковий (DSD):** високотиск, неефективне спорожнення — пік тиску детрузора "
            f"**{b['p_max_void_cmH2O']} cmH₂O**, Qmax **{b['qmax_ml_s']} mL/s**, залишок "
            f"**{b['pvr_ml']} mL** (ефективність **{b['bve_pct']}%**), приріст тиску при автономній "
            f"дисрефлексії **+{b['ad_rise_mmHg']} mmHg**. Цей патерн веде до інфекцій, ризику для нирок "
            f"і небезпечної для життя дисрефлексії.",
            f"- **Координована EES:** низькотиск, повне спорожнення — пік тиску "
            f"**{c['p_max_void_cmH2O']} cmH₂O**, Qmax **{c['qmax_ml_s']} mL/s**, залишок "
            f"**{c['pvr_ml']} mL** (ефективність **{c['bve_pct']}%**), дисинергія усунена і "
            f"**без автономної дисрефлексії** (+{c['ad_rise_mmHg']} mmHg).",
            f"- **Безпека (<{int(MCGUIRE_CMH2O)} cmH₂O):** тиск зберігання "
            f"{'у межах' if safe else 'ВИЩЕ'} порога захисту нирок (макс. зберігання "
            f"**{b['p_max_storage_cmH2O']} cmH₂O**).", "",
            "## Рекомендація",
            "- **Протокол:** координована EES над **S2–S4 (крижовий відділ)** на **~30 Гц** для "
            "низькотискового повного спорожнення; разом із плановим режимом ведення міхура (~кожні 4 год) "
            "і предиктивним вартовим автономної дисрефлексії.",
            "- **Моніторинг:** повторна цистометрія для підтвердження зберігання <40 cmH₂O і залишку "
            "<50 mL; відстеження епізодів АД та інфекцій.",
            "- **Рішення за людиною:** кожна зміна параметра пропонується лікарю на підтвердження і "
            "логується (підтримка рішень, не автономне керування).", "",
            "## Джерела",
            "- Опубліковані дані — тиск витоку детрузора <40 cmH₂O захищає верхні сечові шляхи.",
            "- Опубліковані дослідження спінальної стимуляції — для функції міхура після травми.",
            "- Рецензоване дослідження імплантованої стимуляції (2025) — відновлення автономної/"
            "гемодинамічної стабільності після травми.", "",
            "_Згенеровано Brain-Spine Orchestrator (модуль «автономіка-перший»). Ілюстративна "
            "симуляція — вирішує лікар._",
        ]
    else:
        L += [
            "## Interpretation",
            f"- **Baseline (DSD):** high-pressure, inefficient voiding — peak detrusor pressure "
            f"**{b['p_max_void_cmH2O']} cmH₂O**, Qmax **{b['qmax_ml_s']} mL/s**, post-void residual "
            f"**{b['pvr_ml']} mL** (voiding efficiency **{b['bve_pct']}%**), with an autonomic-dysreflexia "
            f"rise of **+{b['ad_rise_mmHg']} mmHg**. This pattern drives recurrent infection, upper-tract "
            f"risk and life-threatening dysreflexia.",
            f"- **Coordinated EES:** low-pressure, complete voiding — peak detrusor pressure "
            f"**{c['p_max_void_cmH2O']} cmH₂O**, Qmax **{c['qmax_ml_s']} mL/s**, residual "
            f"**{c['pvr_ml']} mL** (efficiency **{c['bve_pct']}%**), dyssynergia resolved and "
            f"**no autonomic dysreflexia** (+{c['ad_rise_mmHg']} mmHg).",
            f"- **Safety (<{int(MCGUIRE_CMH2O)} cmH₂O):** storage pressure is "
            f"{'within' if safe else 'ABOVE'} the upper-tract safety threshold (max storage "
            f"**{b['p_max_storage_cmH2O']} cmH₂O**).", "",
            "## Recommendation",
            "- **Protocol:** coordinated EES over **S2–S4 (sacral)** at **~30 Hz** for low-pressure, "
            "complete voiding; pair with a scheduled bladder-management regimen (≈4-hourly) and a "
            "predictive autonomic-dysreflexia guardian.",
            "- **Monitoring:** repeat cystometry to confirm storage <40 cmH₂O and PVR <50 mL; track AD "
            "events and infection rate.",
            "- **Human-in-the-loop:** every parameter change is proposed to the clinician for approval "
            "and logged (decision-support, not autonomous control).", "",
            "## References",
            "- Published evidence — detrusor leak-point pressure <40 cmH₂O protects the upper urinary tract.",
            "- Published spinal-stimulation studies — for bladder function after SCI.",
            "- A peer-reviewed implanted-stimulation study (2025) — restoring autonomic/haemodynamic "
            "stability after SCI.", "",
            "_Generated by Brain-Spine Orchestrator (autonomic-first clinical module). Illustrative "
            "simulation — clinician decides._",
        ]
    return "\n".join(L)
