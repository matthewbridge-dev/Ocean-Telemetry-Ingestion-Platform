"""data_fetch.py

Data Fetch for grabbing global ocean surface telemetry slices from NOAA Global RTOFS
via NOMADS Direct HTTPS (rtofs_glo_2ds_*_prog.nc).
"""

from datetime import datetime, timedelta, timezone
import logging
import os
import certifi
import fsspec
import numpy as np
import xarray as xr
from datapull.bounding_box import BoundingBox

# Ensure aiohttp/fsspec uses certifi's CA bundle on macOS
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

logger = logging.getLogger(__name__)

NOMADS_BASE_URL = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/rtofs/prod"

# Global 2D surface prognostic NetCDF files (contains sst, sss, u_velocity, v_velocity)
CANDIDATE_2D_FILES: list[str] = [
    "rtofs_glo_2ds_n024_prog.nc",
    "rtofs_glo_2ds_f000_prog.nc",
]

VAR_RENAME_MAP: dict[str, str] = {
    "sst": "temperature",
    "sss": "salinity",
    "u_velocity": "u",
    "v_velocity": "v",
}


class DataFetch:

    def __init__(self, fallback_days: int = 2):
        """Initializes the HTTPS filesystem client for NOAA NOMADS Global RTOFS."""
        self.fallback_days = fallback_days
        # 4 MB block size minimizes HTTP Range requests to stay well under NOMADS rate limits
        self.fs = fsspec.filesystem(
            "https",
            block_size=4 * 1024 * 1024,
            headers={"User-Agent": "OceanTelemetryIngestionPlatform/1.0"},
        )
        self._cached_url: str | None = None
        self._cached_lats: np.ndarray | None = None
        self._cached_lons: np.ndarray | None = None
        logger.info("DataFetch initialized for NOMADS: %s", NOMADS_BASE_URL)

    def _find_latest_url(self) -> str:
        """Finds the latest available global 2D prognostic NetCDF URL on NOMADS."""
        if self._cached_url is not None:
            return self._cached_url

        last_err: Exception | None = None
        for day_offset in range(self.fallback_days):
            date_str = (
                datetime.now(timezone.utc) - timedelta(days=day_offset)
            ).strftime("%Y%m%d")
            for filename in CANDIDATE_2D_FILES:
                url = f"{NOMADS_BASE_URL}/rtofs.{date_str}/{filename}"
                try:
                    # Use info() instead of exists() so SSL/HTTP errors aren't hidden
                    self.fs.info(url)
                    logger.info("Found Global RTOFS surface file: %s", url)
                    self._cached_url = url
                    return url
                except Exception as exc:
                    last_err = exc
                    logger.debug("Probe failed for %s: %s", url, exc)

        raise FileNotFoundError(
            f"No Global RTOFS 2D surface file found on NOMADS in the last "
            f"{self.fallback_days} days. Last error: {last_err}"
        )

    @staticmethod
    def _normalize_lons(lons: np.ndarray) -> np.ndarray:
        """Masks RTOFS sentinel values (>=500) and wraps [74.16, 434.16] -> [-180, 180)."""
        clean = np.where(np.abs(lons) >= 500.0, np.nan, lons)
        return ((clean + 180.0) % 360.0) - 180.0

    def _compute_slice_indices(
        self, ds: xr.Dataset, bounds: BoundingBox
    ) -> tuple[slice, slice]:
        """Computes (Y, X) grid index slices matching the bounding box."""
        if self._cached_lats is None or self._cached_lons is None:
            raw_lats = ds["Latitude"].values
            self._cached_lats = np.where(np.abs(raw_lats) > 90.0, np.nan, raw_lats)
            self._cached_lons = self._normalize_lons(ds["Longitude"].values)

        slice_mask = (
            (self._cached_lats >= bounds.min_lat)
            & (self._cached_lats <= bounds.max_lat)
            & (self._cached_lons >= bounds.min_lon)
            & (self._cached_lons <= bounds.max_lon)
        )

        y_idx, x_idx = np.where(slice_mask)
        if y_idx.size == 0 or x_idx.size == 0:
            raise ValueError(
                f"Bounding box ({bounds.min_lon}, {bounds.min_lat}, "
                f"{bounds.max_lon}, {bounds.max_lat}) falls outside the ocean grid coverage."
            )

        return (
            slice(int(y_idx.min()), int(y_idx.max()) + 1),
            slice(int(x_idx.min()), int(x_idx.max()) + 1),
        )

    def fetch(self, bounds: BoundingBox) -> xr.Dataset:
        """Fetches and returns an in-memory cropped ocean surface telemetry slice from NOMADS."""
        try:
            url = self._find_latest_url()

            with self.fs.open(url, "rb") as f:
                ds = xr.open_dataset(f, engine="h5netcdf", decode_times=False)

                missing = [v for v in VAR_RENAME_MAP if v not in ds.data_vars]
                if missing:
                    raise KeyError(
                        f"Missing expected variables {missing} in {url}. "
                        f"Available: {list(ds.data_vars)}"
                    )

                y_sl, x_sl = self._compute_slice_indices(ds, bounds)
                raw_vars = list(VAR_RENAME_MAP.keys())

                sub = ds[raw_vars].isel(MT=0, Y=y_sl, X=x_sl).load()

            if "Layer" in sub.dims:
                sub = sub.squeeze("Layer", drop=True)
            sub = sub.rename(VAR_RENAME_MAP).expand_dims(Depth=[0.0])

            if "Longitude" in sub.coords or "Longitude" in sub.data_vars:
                norm_lon = xr.apply_ufunc(self._normalize_lons, sub["Longitude"])
                sub = sub.assign_coords(Longitude=norm_lon)

            logger.info(
                "DataFetch: Loaded %.2f KB global surface slice (Depth=%d, Y=%d, X=%d)",
                sub.nbytes / 1024,
                sub.sizes["Depth"],
                sub.sizes["Y"],
                sub.sizes["X"],
            )
            return sub

        except Exception as e:
            logger.error("Failed to process Global RTOFS data: %s", e)
            raise RuntimeError(f"RTOFS data extraction failed: {e}") from e