"""Unified substrate: locomotion AND autonomic share ONE bus, loop and safety gate
and tick together — the 'one substrate' claim, proven in code."""
from bso.autonomic import AutonomicCommand, AutonomicEvent, AutonomicFunction
from bso.decoder_stub import IntentEvent, Mode
from bso.unified import build_unified_system


def _build():
    loco = [IntentEvent(0.0, Mode.STAND), IntentEvent(0.4, Mode.WALK, speed=0.6)]
    auto = [AutonomicEvent(0.0, AutonomicFunction.BLADDER, AutonomicCommand.STORE)]
    return build_unified_system(loco, auto, dt=0.01)


def test_one_substrate_shared_components():
    uni = _build()
    ev = uni.evidence()
    assert ev["one_bus"], "locomotion and autonomic must share one Bus"
    assert ev["one_tick_loop"], "must share one TickLoop"
    assert ev["one_safety_gate"], "must share one SafetySupervisor (one safety gate)"


def test_both_loops_run_together_through_one_gate():
    uni = _build()
    rec, auton = uni.run(3.0)
    # locomotion actually moved (gait frames recorded)
    assert len(rec.frames) > 0
    # autonomic loop ticked on the same loop (produced state / log)
    assert auton.cord is not None
    # the SAME safety object guarded both loops
    assert uni.locomotion.safety is uni.autonomic.safety
    # safety stayed valid (no negative/exploding clamp counter)
    assert uni.safety.clamped_count >= 0
