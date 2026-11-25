"""Builds outbound OceanEnvMsg payloads from EnvironmentSample DTOs."""

import math

from models import EnvironmentSample, OceanEnvMsg


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

    def build(self, sample: EnvironmentSample) -> OceanEnvMsg:
        """Map a EnvironmentSample into a populated OceanEnvMsg.

        Args:
            sample: Telemetry sample.

        Returns:
            Populated OceanEnvMsg for the ROS 2 publisher.
        """
        msg = OceanEnvMsg()
        msg.water_temp_c = self._sanitize_float(sample.water_temp_c)
        msg.salinity_psu = self._sanitize_float(sample.salinity_psu)
        msg.velocity_u_ms = self._sanitize_float(sample.velocity_u_ms)
        msg.velocity_v_ms = self._sanitize_float(sample.velocity_v_ms)
        return msg