"""data_fetch.py

Data Fetch for grabbing raw 3D sub-volumes from NOAA Global RTOFS via AWS Open Data.
Uses the global daily 3D volumes (one file per variable) for uniform worldwide coverage.
"""

# Note:
# This currently uses only the global dataset.
# It could be made to use American regional datasets,
# if there was a check for whether the current bounds fall in that area.
from datetime import datetime, timedelta, timezone
import logging
import numpy as np
import s3fs
import xarray as xr
from bounding_box import BoundingBox

logger = logging.getLogger(__name__)

BUCKET_NAME: str = "noaa-nws-rtofs-pds/rtofs"

# NOAA splits global 3D output into one file per variable
SUFFIXES: dict[str, str] = {
    "temperature": "3ztio",
    "salinity": "3zsio",
    "u": "3zuio",
    "v": "3zvio",
}


class DataFetch:
    def __init__(self, fallback_days: int = 2):
        """Initializes the S3 filesystem client for NOAA Global RTOFS.

        Args:
            fallback_days: Number of days to check for available data (2 = today and yesterday).
        """
        self.fallback_days = fallback_days
        # Create anonymous S3FileSystem instance
        self.fs = s3fs.S3FileSystem(anon=True)
        logger.info("DataFetch initialized for bucket: %s", BUCKET_NAME)

    def _find_latest_data(self) -> dict[str, str]:
        """Finds the latest operational keys."""
        # For each day in fallback days...
        for day_offset in range(self.fallback_days):
            # Find the date to check
            check_date = (datetime.now(timezone.utc) - timedelta(days=day_offset)).strftime("%Y%m%d")

            # Build the folder path for that date in the bucket
            folder = f"{BUCKET_NAME}.{check_date}"

            # If not found, skip to the previous day
            if not self.fs.exists(folder):
                continue

            # Grab the folder files
            files = self.fs.ls(folder)

            # Create a dictionary to store matched file keys
            access_keys: dict[str, str] = {}

            # For each suffix, find a matching file (preferring the _n024_ nowcast)
            for var_name, suffix in SUFFIXES.items():
                matches = [f for f in files if f"daily_{suffix}.nc" in f]
                if matches:
                    nowcasts = [f for f in matches if "_n024_" in f]
                    access_keys[var_name] = nowcasts[0] if nowcasts else matches[0]

            # Return once we have a file for every variable
            if len(access_keys) == len(SUFFIXES):
                return access_keys

        # If not enough matching keys, raise error
        raise FileNotFoundError(
            f"No complete global RTOFS dataset found in the last {self.fallback_days} days."
        )

    def _compute_slice_indices(
        self, ds: xr.Dataset, bounds: BoundingBox
    ) -> tuple[slice, slice, slice]:
        """Computes (Depth, Y, X) integer slices on the global grid."""
        # Get the dataset's coordinate values
        lats = ds["Latitude"].values
        lons = ds["Longitude"].values
        depths = ds["Depth"].values

        # Clean junk values and wrap longitude into [-180, 180)
        lons = np.where(lons >= 500.0, np.nan, lons)
        lons = ((lons + 180.0) % 360.0) - 180.0

        # Build the boolean mask for our bounding box
        slice_mask = (
            (lats >= bounds.min_lat) & (lats <= bounds.max_lat) &
            (lons >= bounds.min_lon) & (lons <= bounds.max_lon)
        )

        # Find the Y and X grid indices inside the mask
        y_idx, x_idx = np.where(slice_mask)
        if y_idx.size == 0 or x_idx.size == 0:
            raise ValueError("Bounding box falls outside the global RTOFS grid.")

        # Find the depth indices within max_depth_m
        depth_idx = np.where(depths <= bounds.max_depth_m)[0]
        if depth_idx.size == 0:
            raise ValueError(
                f"max_depth_m ({bounds.max_depth_m}) is shallower than minimum grid depth."
            )

        # Return the (Depth, Y, X) slice ranges
        return (
            slice(int(depth_idx.min()), int(depth_idx.max()) + 1),
            slice(int(y_idx.min()), int(y_idx.max()) + 1),
            slice(int(x_idx.min()), int(x_idx.max()) + 1),
        )

    def fetch(self, bounds: BoundingBox) -> xr.Dataset:
        """Fetches and returns a raw, in-memory global RTOFS sub-volume.

        Args:
            bounds: BoundingBox dataclass (min_lon, min_lat, max_lon, max_lat, max_depth_m).

        Returns:
            xr.Dataset: Raw cropped RTOFS dataset containing temperature, salinity, u, and v.

        Raises:
            ConnectionError: If S3 is unreachable or no recent global files exist.
            RuntimeError: If the bounding box is out of grid range or slicing fails.
        """
        try:
            # Find the latest S3 file keys for all 4 variables
            s3_keys = self._find_latest_data()
            loaded_parts: list[xr.Dataset] = []
            slices: tuple[slice, slice, slice] | None = None

            # Stream and slice each variable file one by one
            for var_name, s3_key in s3_keys.items():
                logger.info("Streaming global %s: s3://%s", var_name, s3_key)

                with self.fs.open(s3_key, "rb") as f:
                    ds = xr.open_dataset(f, engine="h5netcdf")

                    # Compute slice indices once on the first file (all 4 share the same grid)
                    if slices is None:
                        slices = self._compute_slice_indices(ds, bounds)

                    depth_sl, y_sl, x_sl = slices

                    # Slice the variable and pull the data into memory
                    part = ds[[var_name]].isel(MT=0, Depth=depth_sl, Y=y_sl, X=x_sl).load()
                    loaded_parts.append(part)

            # Combine all 4 variables into one dataset
            merged = xr.merge(loaded_parts)
            logger.info("DataFetch: Merged %.2f KB global sub-volume", merged.nbytes / 1024)
            return merged

        # Catch S3 network or missing-file errors
        except OSError as e:
            logger.error("S3 connection or file access error: %s", e)
            raise ConnectionError(f"Failed to fetch from S3: {e}") from e

        # Catch slicing, bounds, or dataset parsing errors
        except Exception as e:
            logger.error("Failed to process RTOFS data: %s", e)
            raise RuntimeError(f"RTOFS data extraction failed: {e}") from e