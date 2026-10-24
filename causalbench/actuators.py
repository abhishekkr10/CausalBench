"""Actuator contract. Physical outputs are deliberately unavailable."""
from .provenance import loaded_source, register_source
_LOADED_SOURCE=register_source(__file__)
from typing import Protocol

class Actuator(Protocol):
    def command(self, value: str, time_ms: int) -> dict: ...

class SimulatedActuator:
    """Command visualization only; no dynamics, torque, or settling model."""
    def command(self, value, time_ms):
        if value not in ('HOLD', 'PULSE'):
            raise ValueError('Unsupported command')
        return {'simulated': True, 'time_ms': time_ms, 'command': value,
                'visual_angle_deg': 45 if value == 'PULSE' else 0}

class PhysicalActuator:
    def __init__(self, *, enabled=False):
        if not enabled:
            raise RuntimeError('Physical output disabled by default')
        raise NotImplementedError('Implement and bench-validate a hardware adapter before enabling output')
