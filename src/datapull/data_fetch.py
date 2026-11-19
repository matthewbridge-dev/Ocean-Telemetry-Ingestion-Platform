"""data_fetch.py

Data Fetch for grabbing global ocean surface telemetry slices from NOAA RTOFS via AWS Open Data.
Streams global 2D prognostic NetCDF files (sst, sss, u_velocity, v_velocity) hosted on S3.
"""

from datetime import datetime, timedelta, timezone
import logging
import numpy as np
import s3fs
import xarray as xr
from datapull.bounding_box import BoundingBox

logger = logging.getLogger(__name__)

BUCKET_NAME = "noaa-nws-rtofs-pds"

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

  def __init__(self, fallback_days: int = 3):
    """Initializes the S3 filesystem client for NOAA Global RTOFS.

        Args:
            fallback_days: Number of days to check for available model runs on S3.
        """
    self.fallback_days = fallback_days
    self.fs = s3fs.S3FileSystem(
        anon=True, default_block_size=2 * 1024 * 1024
    )
    logger.info("DataFetch initialized for S3 bucket: %s", BUCKET_NAME)

  def _find_latest_file(self) -> str:
    """Finds the latest available global 2D prognostic NetCDF file on S3."""
    for day_offset in range(self.fallback_days):
      date_str = (
          datetime.now(timezone.utc) - timedelta(days=day_offset)
      ).strftime("%Y%m%d")
      for filename in CANDIDATE_2D_FILES:
        s3_key = f"{BUCKET_NAME}/rtofs.{date_str}/{filename}"
        if self.fs.exists(s3_key):
          logger.info("Found Global RTOFS surface file: s3://%s", s3_key)
          return s3_key

    raise FileNotFoundError(
        "No Global RTOFS 2D surface file found in the last"
        f" {self.fallback_days} days."
    )

  def _compute_slice_indices(
      self, ds: xr.Dataset, bounds: BoundingBox
  ) -> tuple[slice, slice]:
    """Computes (Y, X) grid index slices matching the bounding box."""
    lats = ds["Latitude"].values
    lons = ds["Longitude"].values

    # Clean junk sentinel values (>=500) and normalize RTOFS [74.16, 434.16] -> [-180, 180)
    lons = np.where(lons >= 500.0, np.nan, lons)
    lons = ((lons + 180.0) % 360.0) - 180.0

    slice_mask = (
        (lats >= bounds.min_lat)
        & (lats <= bounds.max_lat)
        & (lons >= bounds.min_lon)
        & (lons <= bounds.max_lon)
    )

    y_idx, x_idx = np.where(slice_mask)
    if y_idx.size == 0 or x_idx.size == 0:
      raise ValueError(
          f"Bounding box ({bounds.min_lon}, {bounds.min_lat},"
          f" {bounds.max_lon}, {bounds.max_lat}) falls outside the ocean grid"
          " coverage area."
      )

    return (
        slice(int(y_idx.min()), int(y_idx.max()) + 1),
        slice(int(x_idx.min()), int(x_idx.max()) + 1),
    )

  def fetch(self, bounds: BoundingBox) -> xr.Dataset:
    """Fetches and returns an in-memory cropped ocean surface telemetry slice from S3.

        Args:
            bounds: BoundingBox dataclass (min_lon, min_lat, max_lon, max_lat, max_depth_m).

        Returns:
            xr.Dataset: Cropped dataset containing temperature, salinity, u, and v at Depth=0.0m.
        """
    try:
      s3_key = self._find_latest_file()

      with self.fs.open(s3_key, "rb") as f:
        ds = xr.open_dataset(f, engine="h5netcdf")
        y_sl, x_sl = self._compute_slice_indices(ds, bounds)

        raw_vars = list(VAR_RENAME_MAP.keys())
        sub = ds[raw_vars].isel(MT=0, Y=y_sl, X=x_sl).load()

      # Squeeze singleton 'Layer' dim if present and standardize to Depth=[0.0]
      if "Layer" in sub.dims:
        sub = sub.squeeze("Layer", drop=True)
      sub = sub.rename(VAR_RENAME_MAP).expand_dims(Depth=[0.0])

      # Normalize output Longitude coordinate to [-180, 180)
      if "Longitude" in sub.coords or "Longitude" in sub.data_vars:
        norm_lon = ((sub["Longitude"] + 180.0) % 360.0) - 180.0
        sub = sub.assign_coords(Longitude=norm_lon)

      logger.info(
          "DataFetch: Loaded %.2f KB global surface slice (Depth=%d, Y=%d,"
          " X=%d)",
          sub.nbytes / 1024,
          sub.sizes["Depth"],
          sub.sizes["Y"],
          sub.sizes["X"],
      )
      return sub

    except Exception as e:
      logger.error("Failed to process Global RTOFS data: %s", e)
      raise RuntimeError(f"RTOFS data extraction failed: {e}") from e
