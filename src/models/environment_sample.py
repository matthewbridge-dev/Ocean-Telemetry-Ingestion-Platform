"""Single-point ocean telemetry sample data model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EnvironmentSample:
    """Normalized, single-point ocean telemetry returned by a chunk lookup.
    """

    water_temp_c: float | None
    salinity_psu: float | None
    velocity_u_ms: float | None
    velocity_v_ms: float | None

    # Optional matched grid coordinates (useful for logging/debugging snap distance)
    matched_lat: float | None = None
    matched_lon: float | None = None
    matched_depth_m: float | None = None