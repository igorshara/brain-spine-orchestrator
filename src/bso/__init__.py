"""Brain-Spine Orchestrator (BSO).

Дослідницький симулятор / цифровий двійник оркестраційного шару для
стимуляційної сторони brain-spine інтерфейсу. Це НЕ медичний пристрій.

The package exposes the message contracts (``schemas``), the deterministic
tick-loop (``bus``) and the six processing layers. Safety invariants live in
``bso.safety`` and ``bso.config.limits`` and have absolute priority.
"""

__version__ = "0.1.0"

DISCLAIMER = (
    "RESEARCH SIMULATION ONLY. No real hardware, no implant telemetry, no "
    "patient data. All numeric limits are ILLUSTRATIVE, not clinically validated."
)
