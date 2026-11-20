"""data_fetch.py

Data Fetch for NOAA Global RTOFS via NOMADS HTTPS
"""

from concurrent.futures import ThreadPoolExecutor
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

# NOMADS publishes global 3D daily z-level files starting at f024 / n024 / f048
CYCLE_PREFIXES: list[str] = [
    "rtofs_glo_3dz_f024_daily",
    "rtofs_glo_3dz_n024_daily",
    "rtofs_glo_3dz_f048_daily",
]

# Maps standardized output name -> (file_suffix, internal_nc_var_name)
VAR_FILE_MAP: dict[str, tuple[str, str]] = {
    "temperature": ("3ztio.nc", "temperature"),
    "salinity": ("3zsio.nc", "salinity"),
    "u": ("3zuio.nc", "u"),
    "v": ("3zvio.nc", "v"),
}


class DataFetch:
    
    def __init__(self, fallback_days: int = 2):
        """Initializes the HTTPS filesystem client for NOAA NOMADS 3D Global RTOFS."""
        self.fallback_days = fallback_days
        self._cached_base_prefix: str | None = None
        self._cached_lats: np.ndarray | None = None
        self._cached_lons: np.ndarray | None = None
        self._cached_depths: np.ndarray | None = None
        logger.info("DataFetch (3D) initialized for NOMADS: %s", NOMADS_BASE_URL)

    def _make_fs(self) -> fsspec.AbstractFileSystem:
        """Creates a thread-safe fsspec HTTPS client instance."""
        return fsspec.filesystem(
            "https",
            block_size=4 * 1024 * 1024,
            headers={"User-Agent": "OceanTelemetryIngestionPlatform/1.0"},
        )

    def _find_latest_cycle_prefix(self) -> str:
        """Finds the latest available 3D daily cycle prefix on NOMADS."""
        if self._cached_base_prefix is not None:
            return self._cached_base_prefix

        fs = self._make_fs()
        last_err: Exception | None = None
        for day_offset in range(self.fallback_days):
            date_str = (
                datetime.now(timezone.utc) - timedelta(days=day_offset)
            ).strftime("%Y%m%d")
            for prefix in CYCLE_PREFIXES:
                base_prefix = f"{NOMADS_BASE_URL}/rtofs.{date_str}/{prefix}"
                probe_url = f"{base_prefix}_3ztio.nc"
                try:
                    fs.info(probe_url)
                    logger.info("Found Global RTOFS 3D cycle: %s_*.nc", base_prefix)
                    self._cached_base_prefix = base_prefix
                    return base_prefix
                except Exception as exc:
                    last_err = exc
                    logger.debug("Probe failed for %s: %s", probe_url, exc)

        raise FileNotFoundError(
            f"No Global RTOFS 3D depth files found on NOMADS in the last "
            f"{self.fallback_days} days. Last error: {last_err}"
        )

    @staticmethod
    def _normalize_lons(lons: np.ndarray) -> np.ndarray:
        """Masks RTOFS sentinel values (>=500) and wraps [74.16, 434.16] -> [-180, 180)."""
        clean = np.where(np.abs(lons) >= 500.0, np.nan, lons)
        return ((clean + 180.0) % 360.0) - 180.0

    def _compute_slice_indices(
        self, ds: xr.Dataset, bounds: BoundingBox
    ) -> tuple[slice, slice, slice]:
        """Computes (Depth, Y, X) grid index slices matching the bounding box."""
        if (
            self._cached_lats is None
            or self._cached_lons is None
            or self._cached_depths is None
        ):
            raw_lats = ds["Latitude"].values
            self._cached_lats = np.where(np.abs(raw_lats) > 90.0, np.nan, raw_lats)
            self._cached_lons = self._normalize_lons(ds["Longitude"].values)
            self._cached_depths = ds["Depth"].values

        # 1. Depth slice (include surface 0m up to max_depth_m)
        depth_idx = np.where(self._cached_depths <= bounds.max_depth_m)[0]
        if depth_idx.size == 0:
            depth_idx = np.array([0])
        d_sl = slice(0, int(depth_idx.max()) + 1)

        # 2. Horizontal (Y, X) slice
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
            d_sl,
            slice(int(y_idx.min()), int(y_idx.max()) + 1),
            slice(int(x_idx.min()), int(x_idx.max()) + 1),
        )

    def _fetch_single_var(
        self,
        url: str,
        raw_var: str,
        out_var: str,
        d_sl: slice,
        y_sl: slice,
        x_sl: slice,
    ) -> xr.DataArray:
        """Opens one 3D RTOFS file and materializes the cropped DataArray."""
        fs = self._make_fs()
        with fs.open(url, "rb") as f:
            ds = xr.open_dataset(f, engine="h5netcdf", decode_times=False)
            if raw_var not in ds.data_vars:
                raise KeyError(
                    f"Missing '{raw_var}' in {url}. Available: {list(ds.data_vars)}"
                )
            da = ds[raw_var].isel(MT=0, Depth=d_sl, Y=y_sl, X=x_sl).load()
            da.name = out_var
            return da

    def fetch(self, bounds: BoundingBox) -> xr.Dataset:
        """Fetches and merges an in-memory 3D ocean telemetry slice across all 4 variables."""
        try:
            base_prefix = self._find_latest_cycle_prefix()

            # 1. Open temperature file once to prime coordinates AND slice temperature
            temp_suffix, temp_raw = VAR_FILE_MAP["temperature"]
            temp_url = f"{base_prefix}_{temp_suffix}"
            fs = self._make_fs()
            with fs.open(temp_url, "rb") as f:
                ds_temp = xr.open_dataset(f, engine="h5netcdf", decode_times=False)
                d_sl, y_sl, x_sl = self._compute_slice_indices(ds_temp, bounds)
                temp_da = ds_temp[temp_raw].isel(MT=0, Depth=d_sl, Y=y_sl, X=x_sl).load()
                temp_da.name = "temperature"

            # 2. Pull the remaining 3 3D variable slices concurrently
            arrays: list[xr.DataArray] = [temp_da]
            remaining_vars = {
                k: v for k, v in VAR_FILE_MAP.items() if k != "temperature"
            }
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = [
                    pool.submit(
                        self._fetch_single_var,
                        f"{base_prefix}_{suffix}",
                        raw_var,
                        out_var,
                        d_sl,
                        y_sl,
                        x_sl,
                    )
                    for out_var, (suffix, raw_var) in remaining_vars.items()
                ]
                for fut in futures:
                    arrays.append(fut.result())

            sub = xr.merge(arrays, compat="override")

            # Sanitize and normalize output Longitude coordinate to [-180, 180)
            if "Longitude" in sub.coords or "Longitude" in sub.data_vars:
                norm_lon = xr.apply_ufunc(self._normalize_lons, sub["Longitude"])
                sub = sub.assign_coords(Longitude=norm_lon)

            # Clean up stale encoding metadata to prevent to_netcdf() warnings
            sub.encoding.pop("unlimited_dims", None)

            logger.info(
                "DataFetch (3D): Loaded %.2f KB slice (Depth=%d [0..%.1fm], Y=%d, X=%d)",
                sub.nbytes / 1024,
                sub.sizes["Depth"],
                float(sub["Depth"].max()),
                sub.sizes["Y"],
                sub.sizes["X"],
            )
            return sub

        except Exception as e:
            logger.error("Failed to process 3D Global RTOFS data: %s", e)
            raise RuntimeError(f"3D RTOFS data extraction failed: {e}") from e