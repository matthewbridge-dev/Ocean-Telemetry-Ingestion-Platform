"""Normalized 3D ocean telemetry chunk data model."""

from dataclasses import dataclass
from datetime import datetime
import numpy as np

from models.bounding_box import BoundingBox


@dataclass(frozen=True, slots=True)
class NormalizedChunk:
    """In-memory, 3D ocean grid chunk.
    """

    bounds: BoundingBox
    timestamp: datetime
    depth_levels: np.ndarray   # 1D float32, shape (Depth,) in meters
    lats: np.ndarray           # 2D float32, shape (Y, X) in [-90, 90]
    lons: np.ndarray           # 2D float32, shape (Y, X) in [-180, 180)
    water_temp_c: np.ndarray   # 3D float32, shape (Depth, Y, X) in Celsius
    salinity_psu: np.ndarray   # 3D float32, shape (Depth, Y, X) in PSU
    velocity_u_ms: np.ndarray  # 3D float32, shape (Depth, Y, X) in m/s (eastward)
    velocity_v_ms: np.ndarray  # 3D float32, shape (Depth, Y, X) in m/s (northward)