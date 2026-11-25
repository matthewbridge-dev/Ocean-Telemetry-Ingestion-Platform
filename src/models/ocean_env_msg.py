"""Demo Ocean Env Msg
"""

from dataclasses import dataclass
import math


# TODO: Replace this data class with the ROs Pub generated one
@dataclass
class OceanEnvMsg:
    """MVP stub matching the target ROS 2 environment message fields."""

    water_temp_c: float = math.nan
    salinity_psu: float = math.nan
    velocity_u_ms: float = math.nan
    velocity_v_ms: float = math.nan