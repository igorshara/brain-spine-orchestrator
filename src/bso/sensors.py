"""Sensor corruption: Gaussian noise + frame dropout, for robustness stress.

Псування сенсорів для стрес-тестів робастності. Реальні IMU/EMG/датчики GRF
шумлять і губляться (пропуск пакетів телеметрії). Цей компонент сидить МІЖ тілом
і Шаром 3: читає чистий ``sensor_frame`` від плану й перепубліковує зашумлену
(і подеколи «застряглу») версію, яку бачить sensor fusion.

Детермінований за seed (np.random.default_rng), щоб прогони відтворювались.
"""

from __future__ import annotations

import numpy as np

from .bus import Bus
from .schemas import SensorFrame

TOPIC = "sensor_frame"


class SensorCorruptor:
    """Adds noise to joint angles / GRF and randomly holds the previous frame
    (dropout). Insert AFTER Body and BEFORE Feedback in the tick order."""

    def __init__(self, noise_deg: float = 0.0, noise_grf_N: float = 0.0,
                 dropout_prob: float = 0.0, seed: int = 0) -> None:
        self.noise_deg = noise_deg
        self.noise_grf_N = noise_grf_N
        self.dropout_prob = dropout_prob
        self.rng = np.random.default_rng(seed)
        self._last: SensorFrame | None = None

    def tick(self, t: float, dt: float, bus: Bus) -> None:
        frame: SensorFrame | None = bus.latest(TOPIC)
        if frame is None:
            return

        # Dropout: republish the last delivered frame (stale telemetry).
        if self._last is not None and self.dropout_prob > 0 and \
                self.rng.random() < self.dropout_prob:
            bus.publish(TOPIC, self._last)
            return

        ja = dict(frame.joint_angles)
        if self.noise_deg > 0:
            for k in ja:
                ja[k] += float(self.rng.normal(0.0, self.noise_deg))
        grf = dict(frame.grf)
        if self.noise_grf_N > 0:
            for k in grf:
                grf[k] = max(0.0, grf[k] + float(self.rng.normal(0.0, self.noise_grf_N)))

        corrupted = SensorFrame(t=frame.t, imu=frame.imu, joint_angles=ja, grf=grf,
                                emg=frame.emg)
        self._last = corrupted
        bus.publish(TOPIC, corrupted)
