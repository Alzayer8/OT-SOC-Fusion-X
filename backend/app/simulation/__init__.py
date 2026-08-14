"""Deterministic synthetic Oil & Gas transfer-process simulation boundary.

This package has no transport, persistence, protocol, or device-control dependency.
"""

from app.simulation.config import DOMAIN_IDENTIFIER, SIMULATOR_VERSION, SimulationConfig
from app.simulation.engine import OilGasTransferSimulator
from app.simulation.models import GroundTruthEvent, SimulationStep, TelemetrySample
from app.simulation.scenarios import ScenarioSchedule, approved_scenarios

__all__ = [
    "DOMAIN_IDENTIFIER",
    "SIMULATOR_VERSION",
    "GroundTruthEvent",
    "OilGasTransferSimulator",
    "ScenarioSchedule",
    "SimulationConfig",
    "SimulationStep",
    "TelemetrySample",
    "approved_scenarios",
]
