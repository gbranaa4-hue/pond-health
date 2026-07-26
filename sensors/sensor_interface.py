"""
Abstract sensor-reading interface for the pond health monitor.

Swap SimulatedPondReader for a real hardware reader (e.g. one that polls
an ESP32 over serial/MQTT, or reads I2C probes directly on a Raspberry
Pi) without touching any of the prediction/diagnosis/alert code --
everything downstream only depends on the Reading shape below.
"""
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class Reading:
    timestamp: float             # unix seconds
    temperature_c: float          # water temperature, Celsius
    ph: float                     # 0-14
    turbidity_ntu: float          # Nephelometric Turbidity Units
    dissolved_oxygen_mg_l: float
    conductivity_us_cm: float     # electrical conductivity, microsiemens/cm


class SensorReader(ABC):
    """Anything that can produce a Reading implements this."""

    @abstractmethod
    def read(self, at_time: float = None) -> Reading:
        ...
