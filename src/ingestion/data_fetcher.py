"""Data Fetcher for NOAA Global RTOFS through NOMADS HTTPS
"""

# Used for concurrent variable file downloads
from concurrent.futures import ThreadPoolExecutor
# Used for UTC date resolution
from datetime import date, datetime, timedelta, timezone
# Used for runtime logging
import logging
# Used to build the SSLContext, required for HTTPS requests
import ssl
# Used for high-resolution fetch timing
import time

# Provides Mozilla's Certificate Authority bundle so HTTPS works reliably across Operating Systems
import certifi
# Allows pulling using partial HTTP range requests
import fsspec
# NumPy library
import numpy as np
# Reads NetCDF/HDF5 files, slices 3D ocean grids by dimension name, and merges variables
import xarray as xr

# Bounding Box models
from models.bounding_box import BoundingBox

logger = logging.getLogger(__name__)

# NOMADS directory hosting daily Global RTOFS uploads.
NOMADS_URL: str = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/rtofs/prod"

# Filename prefix for nowcast files
NOWCAST_PREFIX: str = "rtofs_glo_3dz_n024_daily"

# HTTP range-request read block size (4 mb)
HTTP_CHUNK_SIZE_BYTES: int = 4 * 1024 * 1024

# Upper bound for valid raw RTOFS longitudes, land values are > 500
RTOFS_MAX_VALID_LONGITUDE: float = 500.0

# Latitude Limit
RTOFS_MAX_VALID_LATITUDE: float = 90.0

# Maps variable names to NOAA's filename suffixes
VAR_FILENAME_SUFFIXES: dict[str, str] = {
    "temperature": "3ztio.nc",
    "salinity": "3zsio.nc",
    "u": "3zuio.nc",
    "v": "3zvio.nc",
}


class DataFetcher:
    """Data Fetcher for cropped 3D ocean telemetry slices from NOAA Global RTOFS via NOMADS HTTPS server.
    """

    def __init__(self) -> None:
        self._http_filesystem: fsspec.AbstractFileSystem = self._build_http_filesystem()
        self._cached_base_prefix: str | None = None
        self._cached_prefix_date: date | None = None
        self._cached_coordinates: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None
        logger.info("DataFetcher initialized for NOMADS: %s", NOMADS_URL)

    @staticmethod
    def _build_http_filesystem() -> fsspec.AbstractFileSystem:
        """Build a fsspec HTTPS filesystem with a valid SSLContext.

        Returns:
            Configured HTTPS filesystem instance.
        """
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        return fsspec.filesystem(
            "https",
            block_size=HTTP_CHUNK_SIZE_BYTES,
            ssl=ssl_context,
        )

    @staticmethod
    def _build_variable_url(base_prefix: str, variable_name: str) -> str:
        """Constructs the full NOMADS URL for a specific telemetry variable."""
        suffix = VAR_FILENAME_SUFFIXES[variable_name]
        return f"{base_prefix}_{suffix}"

    def _is_dates_current(self, date_str: str) -> bool:
        """Probe whether the 3D nowcast files are available for a given UTC date.

        Args:
            date_str: Target UTC date formatted as ``YYYYMMDD``.

        Returns:
            True if the remote file exists, False if the server returns HTTP 404.
        """
        # Assemble the prefix
        base_prefix = f"{NOMADS_URL}/rtofs.{date_str}/{NOWCAST_PREFIX}"
        # Probe the url with temperature as the example
        probe_url = self._build_variable_url(base_prefix, "temperature")
        try:
            self._http_filesystem.info(probe_url)
            logger.info("Found Global RTOFS 3D nowcast for %s: %s", date_str, probe_url)
            return True
        except FileNotFoundError:
            logger.debug("Nowcast not found at %s", probe_url)
            return False

    def _get_active_date_prefix(self) -> str:
        """Resolve and cache the active NOMADS base URL prefix for today or yesterday's UTC cycle.

        Returns:
            Base URL prefix for the active cycle.

        Raises:
            FileNotFoundError: If neither today's nor yesterday's 3D nowcast files are available on NOMADS.
        """
        today_date = datetime.now(timezone.utc).date()

        # Check if there is a cached prefix
        if (
            self._cached_base_prefix is not None
            and self._cached_prefix_date == today_date
        ):
            return self._cached_base_prefix

        # Get the candidate dates (today and yesterday)
        candidate_dates = [
            today_date.strftime("%Y%m%d"),
            (today_date - timedelta(days=1)).strftime("%Y%m%d"),
        ]

        # Check if the candidate dates are available
        for date_str in candidate_dates:
            logger.info("Probing NOMADS for RTOFS 3D nowcast (%s)...", date_str)
            if self._is_dates_current(date_str):
                base_prefix = f"{NOMADS_URL}/rtofs.{date_str}/{NOWCAST_PREFIX}"
                # Cache prefix and date
                self._cached_base_prefix = base_prefix
                self._cached_prefix_date = today_date
                # Return the base prefix
                return base_prefix

        raise FileNotFoundError(
            f"No Global RTOFS 3D nowcasts found on NOMADS for "
            f"{candidate_dates[0]} or {candidate_dates[1]}."
        )

    @staticmethod
    def _normalize_longitudes(raw_longitudes: np.ndarray) -> np.ndarray:
        """Mask land values and wrap longitudes into [-180.0, 180.0)."""
        cleaned = np.where(
            np.abs(raw_longitudes) >= RTOFS_MAX_VALID_LONGITUDE,
            np.nan,
            raw_longitudes,
        )
        return ((cleaned + 180.0) % 360.0) - 180.0

    def _get_grid_coordinates(
        self, base_prefix: str
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return cached (latitudes, longitudes, depths), fetching once if empty.

        Args:
            base_prefix: Active NOMADS cycle URL prefix.

        Returns:
            Tuple of ``(latitudes, longitudes, depths)`` as NumPy arrays, with
            invalid land sentinels masked to NaN and longitudes in [-180, 180).

        Raises:
            RuntimeError: If the remote coordinate arrays cannot be read.
        """
        # Check if coordinates are already cached
        if self._cached_coordinates is not None:
            return self._cached_coordinates

        # Build Coordinate Url
        coord_url = self._build_variable_url(base_prefix, "temperature")
        try:
            with self._http_filesystem.open(coord_url, "rb") as remote_file:
                with xr.open_dataset(
                    remote_file, engine="h5netcdf", decode_times=False
                ) as dataset:
                    raw_lats = dataset["Latitude"].values
                    latitudes = np.where(
                        np.abs(raw_lats) > RTOFS_MAX_VALID_LATITUDE, np.nan, raw_lats
                    )
                    longitudes = self._normalize_longitudes(dataset["Longitude"].values)
                    depths = dataset["Depth"].values
        except Exception as exc:
            logger.error("Failed to load grid coordinates from %s: %s", coord_url, exc)
            raise RuntimeError(
                f"Failed to load grid coordinates from {coord_url}: {exc}"
            ) from exc

        # Cache Coordinates
        self._cached_coordinates = (latitudes, longitudes, depths)
        # Return the coordinates
        return self._cached_coordinates

    @staticmethod
    def _compute_grid_slices(
        bounds: BoundingBox,
        latitudes: np.ndarray,
        longitudes: np.ndarray,
        depths: np.ndarray,
    ) -> tuple[slice, slice, slice]:
        """Convert geographic bounds into contiguous (Depth, Y, X) index slices.

        Args:
            bounds: Target spatial and depth boundaries.
            latitudes: 2D array of sanitized grid latitudes.
            longitudes: 2D array of normalized grid longitudes in [-180, 180).
            depths: 1D array of depth levels in meters.

        Returns:
            Tuple of ``(depth_slice, y_slice, x_slice)`` for ``xarray.isel()``.

        Raises:
            ValueError: If ``bounds`` does not intersect any valid ocean cells.
        """
        depth_indices = np.where(depths <= bounds.max_depth_m)[0]
        max_depth_idx = int(depth_indices.max()) if depth_indices.size > 0 else 0
        depth_slice = slice(0, max_depth_idx + 1)

        inside_box_mask = (
            (latitudes >= bounds.min_lat)
            & (latitudes <= bounds.max_lat)
            & (longitudes >= bounds.min_lon)
            & (longitudes <= bounds.max_lon)
        )
        y_indices, x_indices = np.where(inside_box_mask)
        if y_indices.size == 0 or x_indices.size == 0:
            raise ValueError(
                f"Bounding box ({bounds.min_lon}, {bounds.min_lat}, "
                f"{bounds.max_lon}, {bounds.max_lat}) falls outside ocean grid coverage."
            )

        y_slice = slice(int(y_indices.min()), int(y_indices.max()) + 1)
        x_slice = slice(int(x_indices.min()), int(x_indices.max()) + 1)
        return depth_slice, y_slice, x_slice

    def _fetch_variable_slice(
        self,
        url: str,
        variable_name: str,
        depth_slice: slice,
        y_slice: slice,
        x_slice: slice,
    ) -> xr.DataArray:
        """Download and crop a single 3D variable from a remote NetCDF file.

        Args:
            url: Full NOMADS HTTPS URL for the target variable's NetCDF file.
            variable_name: Internal NetCDF variable key (e.g., ``"temperature"``).
            depth_slice: Index slice along the ``Depth`` dimension.
            y_slice: Index slice along the ``Y`` (latitude) dimension.
            x_slice: Index slice along the ``X`` (longitude) dimension.

        Returns:
            In-memory cropped ``DataArray`` for the requested variable.

        Raises:
            KeyError: If ``variable_name`` is missing from the remote dataset.
            RuntimeError: If the remote file cannot be opened or transferred.
        """
        try:
            with self._http_filesystem.open(url, "rb") as remote_file:
                with xr.open_dataset(
                    remote_file, engine="h5netcdf", decode_times=False
                ) as remote_dataset:
                    if variable_name not in remote_dataset.data_vars:
                        raise KeyError(
                            f"Missing '{variable_name}' in {url}. "
                            f"Available: {list(remote_dataset.data_vars)}"
                        )
                    data_array = (
                        remote_dataset[variable_name]
                        .isel(MT=0, Depth=depth_slice, Y=y_slice, X=x_slice)
                        .load()
                    )
                    data_array.name = variable_name
                    return data_array
        except KeyError:
            raise
        except Exception as exc:
            logger.error("Failed to download %s from %s: %s", variable_name, url, exc)
            raise RuntimeError(
                f"Failed to download {variable_name} from {url}: {exc}"
            ) from exc

    def fetch(self, bounds: BoundingBox) -> xr.Dataset:
        """Fetch and merge a 3D ocean telemetry volume for the given bounds.

        Args:
            bounds: Spatial coordinates and maximum depth defining the volume.

        Returns:
            In-memory ``xarray.Dataset`` containing ``temperature``,
            ``salinity``, ``u``, and ``v`` over dimensions ``(Depth, Y, X)``.

        Raises:
            FileNotFoundError: If no active RTOFS nowcast cycle is available.
            ValueError: If ``bounds`` falls outside the ocean grid.
            RuntimeError: If remote file reads or network transfers fail.
        """
        fetch_start = time.perf_counter()

        # 1. Resolve active cycle
        base_prefix = self._get_active_date_prefix()

        # 2. Retrieve grid coordinates (cached after first call)
        coords_start = time.perf_counter()
        latitudes, longitudes, depths = self._get_grid_coordinates(base_prefix)
        coords_elapsed = time.perf_counter() - coords_start

        # 3. Compute index slices for the requested bounding box
        depth_slice, y_slice, x_slice = self._compute_grid_slices(
            bounds, latitudes, longitudes, depths
        )

        # 4. Download all variable slices concurrently
        download_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=len(VAR_FILENAME_SUFFIXES)) as executor:
            futures = [
                executor.submit(
                    self._fetch_variable_slice,
                    self._build_variable_url(base_prefix, var_name),
                    var_name,
                    depth_slice,
                    y_slice,
                    x_slice,
                )
                for var_name in VAR_FILENAME_SUFFIXES
            ]
            data_arrays: list[xr.DataArray] = [future.result() for future in futures]
        download_elapsed = time.perf_counter() - download_start

        # 5. Merge the final dataset
        merged_dataset = xr.merge(data_arrays, compat="override")
        total_elapsed = time.perf_counter() - fetch_start

        logger.info(
            "DataFetcher (3D): Loaded %.2f KB slice (Depth=%d [0..%.1fm], Y=%d, X=%d) "
            "in %.2fs (coords=%.2fs, download=%.2fs)",
            merged_dataset.nbytes / 1024,
            merged_dataset.sizes["Depth"],
            float(merged_dataset["Depth"].max()),
            merged_dataset.sizes["Y"],
            merged_dataset.sizes["X"],
            total_elapsed,
            coords_elapsed,
            download_elapsed,
        )
        return merged_dataset