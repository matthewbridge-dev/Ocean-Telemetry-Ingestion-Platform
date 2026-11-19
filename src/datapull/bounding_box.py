"""bounding_box.py

Dataclass for defining and validating spatial bounds for a data fetch.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class BoundingBox:
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float
    max_depth_m: float = 100.0

    def __post_init__(self) -> None:
        if not (-180.0 <= self.min_lon < self.max_lon <= 180.0):
            raise ValueError(
                f"Longitudes must satisfy -180 <= min_lon < max_lon <= 180 "
                f"(got {self.min_lon}, {self.max_lon})."
            )
        if not (-90.0 <= self.min_lat < self.max_lat <= 90.0):
            raise ValueError(
                f"Latitudes must satisfy -90 <= min_lat < max_lat <= 90 "
                f"(got {self.min_lat}, {self.max_lat})."
            )
        if self.max_depth_m < 0.0:
            raise ValueError(
                f"max_depth_m must be non-negative (got {self.max_depth_m})."
            )