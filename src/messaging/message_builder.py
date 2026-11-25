"""Builds outbound OceanEnvMsg payloads from EnvironmentSample DTOs."""

import math

from ocean_interfaces.msg import Environment

from models.environment_sample import EnvironmentSample


class MessageBuilder:
    """Mapper from internal EnvironmentSample to outbound OceanEnvMsg.
    """

    def __init__(self, fallback_value: float = math.nan) -> None:
        """Initialize the MessageBuilder.

        Args:
            fallback_value: Numeric sentinel used when a sample field is None.
                Defaults to math.nan (can be set to 0.0 if downstream requires finite floats).
        """
        self._fallback_value = float(fallback_value)

    def _sanitize_float(self, value: float | None) -> float:
        """Convert None or non-finite values into a Python float."""
        if value is None or math.isnan(value):
            return self._fallback_value
        return float(value)

    def build(self, sample: EnvironmentSample) -> Environment:
        """Map a EnvironmentSample into a populated environment topic push.

        Args:
            sample: Telemetry sample.

        Returns:
            Populated OceanEnvMsg for the ROS 2 publisher.
        """
        msg = Environment()
        msg.xdot_ms = self._sanitize_float(sample.velocity_u_ms)
        msg.ydot_ms = self._sanitize_float(sample.velocity_v_ms)
        msg.salinity_ppt = self._sanitize_float(sample.salinity_psu)
        msg.temperature_c = self._sanitize_float(sample.water_temp_c)
        return msg