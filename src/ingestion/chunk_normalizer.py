"""Normalizes raw NOAA Global RTOFS xarray Datasets into NormalizedChunk."""

from datetime import datetime, timezone
import logging
import numpy as np
import xarray as xr

from models import BoundingBox, NormalizedChunk

logger = logging.getLogger(__name__)

# Valid coordinate bounds for NOAA Global RTOFS
RTOFS_MAX_VALID_LATITUDE: float = 90.0
RTOFS_MAX_VALID_LONGITUDE: float = 500.0

REQUIRED_VARS: tuple[str, ...] = ("temperature", "salinity", "u", "v")
REQUIRED_COORDS: tuple[str, ...] = ("Latitude", "Longitude", "Depth")


class ChunkNormalizer:
    """Cleans raw xarray Datasets and extracts contiguous NumPy arrays."""

    @staticmethod
    def _sanitize_latitudes(raw_lats: np.ndarray) -> np.ndarray:
        """Mask out-of-range latitude sentinels to NaN."""
        sanitized = np.where(
            np.abs(raw_lats) > RTOFS_MAX_VALID_LATITUDE,
            np.nan,
            raw_lats,
        )
        return np.ascontiguousarray(sanitized, dtype=np.float32)

    @staticmethod
    def _sanitize_longitudes(raw_lons: np.ndarray) -> np.ndarray:
        """Mask land/edge sentinels (>= 500) to NaN and wrap into [-180.0, 180.0)."""
        cleaned = np.where(
            np.abs(raw_lons) >= RTOFS_MAX_VALID_LONGITUDE,
            np.nan,
            raw_lons,
        )
        wrapped = ((cleaned + 180.0) % 360.0) - 180.0
        return np.ascontiguousarray(wrapped, dtype=np.float32)

    def normalize(self, raw_ds: xr.Dataset, bounds: BoundingBox) -> NormalizedChunk:
        """Validate, sanitize, and convert a raw xarray.Dataset into a NormalizedChunk.

        Args:
            raw_ds: Uncleaned 3D xarray.Dataset returned by DataFetcher.fetch().
            bounds: BoundingBox used to request this chunk.

        Returns:
            NormalizedChunk backed by contiguous float32 NumPy arrays.

        Raises:
            KeyError: If required variables or coordinates are missing.
        """
        missing_vars = [v for v in REQUIRED_VARS if v not in raw_ds.data_vars]
        if missing_vars:
            raise KeyError(
                f"Raw dataset missing required variables: {missing_vars}. "
                f"Available: {list(raw_ds.data_vars)}"
            )

        missing_coords = [c for c in REQUIRED_COORDS if c not in raw_ds.coords]
        if missing_coords:
            raise KeyError(
                f"Raw dataset missing required coordinates: {missing_coords}. "
                f"Available: {list(raw_ds.coords)}"
            )

        lats = self._sanitize_latitudes(raw_ds["Latitude"].values)
        lons = self._sanitize_longitudes(raw_ds["Longitude"].values)
        depths = np.ascontiguousarray(raw_ds["Depth"].values, dtype=np.float32)

        chunk = NormalizedChunk(
            bounds=bounds,
            timestamp=datetime.now(timezone.utc),
            depth_levels=depths,
            lats=lats,
            lons=lons,
            water_temp_c=np.ascontiguousarray(raw_ds["temperature"].values, dtype=np.float32),
            salinity_psu=np.ascontiguousarray(raw_ds["salinity"].values, dtype=np.float32),
            velocity_u_ms=np.ascontiguousarray(raw_ds["u"].values, dtype=np.float32),
            velocity_v_ms=np.ascontiguousarray(raw_ds["v"].values, dtype=np.float32),
        )

        logger.info(
            "ChunkNormalizer: Normalized chunk (Depth=%d, Y=%d, X=%d)",
            chunk.depth_levels.shape[0],
            chunk.lats.shape[0],
            chunk.lats.shape[1],
        )
        return chunk