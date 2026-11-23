"""Integration and performance test suite for DataFetcher across global coastal regions.

Tests 3D ocean telemetry ingestion against NOAA NOMADS for four geographically
diverse coastal locations:
1. Coast of Massachusetts (Northwest Atlantic / Western Hemisphere)
2. Coast of Peru (Southeast Pacific / Southern Hemisphere)
3. Coast of Britain (Northeast Atlantic / Prime Meridian crossing)
4. Coast of South Africa (Agulhas Current / Southern Hemisphere)

Validates both the complete 3D volumetric chunk retrieval and the ability
to extract single-point scalar environmental factors from the chunk.
"""

import time
import numpy as np
import pytest
from datapull.bounding_box import BoundingBox
from datapull.data_fetcher import DataFetcher

SLA_SECONDS = 30.0
REQUIRED_VARS = ("temperature", "salinity", "u", "v")


@pytest.fixture(scope="module")
def fetcher() -> DataFetcher:
    """Provides a shared module-scoped DataFetcher instance.

    Reusing the fetcher across test cases validates that coordinate and depth
    grid caching functions properly across repeated calls.

    Returns:
        DataFetcher: Initialized DataFetcher instance
    """
    return DataFetcher()


@pytest.mark.parametrize(
    "name, box",
    [
        (
            "Coast of Massachusetts",
            BoundingBox(min_lon=-71.0, min_lat=40.5, max_lon=-69.5, max_lat=42.0, max_depth_m=100.0),
        ),
        (
            "Coast of Peru",
            BoundingBox(min_lon=-79.0, min_lat=-13.5, max_lon=-77.0, max_lat=-11.5, max_depth_m=100.0),
        ),
        (
            "Coast of Britain (Prime Meridian)",
            BoundingBox(min_lon=-2.0, min_lat=50.0, max_lon=2.0, max_lat=52.0, max_depth_m=100.0),
        ),
        (
            "Coast of South Africa",
            BoundingBox(min_lon=17.5, min_lat=-35.5, max_lon=20.0, max_lat=-33.5, max_depth_m=100.0),
        ),
    ],
)
def test_global_location_fetch(fetcher: DataFetcher, name: str, box: BoundingBox) -> None:
    """Tests 3D telemetry fetching, coordinate alignment, and point extraction.

    Verifies that the retrieved dataset contains all required oceanographic
    variables (temperature, salinity, u, v), populates a valid 3D depth dimension
    not exceeding the requested depth limit, contains non-NaN ocean cells at the
    surface layer, completes within the SLA latency threshold, and confirms that
    scalar environmental factors can be extracted at a single vehicle coordinate.

    Args:
        fetcher (DataFetcher): Shared DataFetcher client instance from module fixture.
        name (str): Human-readable name of the test geographic region.
        box (BoundingBox): Spatial and vertical boundary specifications.

    Raises:
        AssertionError: If any required variable is missing, depth layer count is
            invalid, surface layer contains only NaN values, point extraction
            fails to return finite numbers, or fetch latency exceeds SLA_SECONDS.
    """
    t0 = time.perf_counter()
    ds = fetcher.fetch(box)
    elapsed = time.perf_counter() - t0

    # 1. Verify required oceanographic variables are present
    for var in REQUIRED_VARS:
        assert var in ds.data_vars, f"[{name}] Missing variable: {var}"

    # 2. Verify 3D depth dimension was populated
    assert "Depth" in ds.sizes and ds.sizes["Depth"] > 1, (
        f"[{name}] Expected multiple depth layers, got {ds.sizes.get('Depth')}"
    )
    assert float(ds["Depth"].max()) <= box.max_depth_m

    # 3. Verify surface layer has non-NaN ocean points (deeper layers naturally mask out on shallow shelves)
    surface_temp = ds["temperature"].isel(Depth=0).values
    valid_ratio = float(np.isfinite(surface_temp).mean())
    assert valid_ratio > 0.0, f"[{name}] Surface slice returned 100% NaN."

    # 4. Verify single-point scalar extraction from the pulled 3D chunk
    # Select target depth layer (e.g. 10m or first subsurface level)
    depth_idx = min(1, ds.sizes["Depth"] - 1)
    target_depth = float(ds["Depth"].values[depth_idx])
    depth_slice = ds.sel(Depth=target_depth, method="nearest")

    # Midpoint target inside the bounding box
    mid_lat = (box.min_lat + box.max_lat) / 2.0
    mid_lon = (box.min_lon + box.max_lon) / 2.0

    # Find the nearest valid ocean cell in the curvilinear grid
    dist_sq = (depth_slice["Latitude"] - mid_lat) ** 2 + (depth_slice["Longitude"] - mid_lon) ** 2
    valid_mask = np.isfinite(depth_slice["temperature"].values)
    assert np.any(valid_mask), f"[{name}] No valid ocean cells at depth {target_depth}m."

    masked_dist = np.where(valid_mask, dist_sq.values, np.inf)
    y_idx, x_idx = np.unravel_index(np.argmin(masked_dist), masked_dist.shape)

    point_temp = float(depth_slice["temperature"].isel(Y=y_idx, X=x_idx).values)
    point_sal = float(depth_slice["salinity"].isel(Y=y_idx, X=x_idx).values)
    point_u = float(depth_slice["u"].isel(Y=y_idx, X=x_idx).values)
    point_v = float(depth_slice["v"].isel(Y=y_idx, X=x_idx).values)

    assert np.isfinite(point_temp), f"[{name}] Extracted point temperature is not finite."
    assert np.isfinite(point_sal), f"[{name}] Extracted point salinity is not finite."
    assert np.isfinite(point_u), f"[{name}] Extracted point u velocity is not finite."
    assert np.isfinite(point_v), f"[{name}] Extracted point v velocity is not finite."

    point_lat = float(depth_slice["Latitude"].isel(Y=y_idx, X=x_idx).values)
    point_lon = float(depth_slice["Longitude"].isel(Y=y_idx, X=x_idx).values)

    print(
        f"\n[{name}] Grid=(D={ds.sizes['Depth']} [0..{float(ds['Depth'].max()):.0f}m], "
        f"Y={ds.sizes['Y']}, X={ds.sizes['X']}) | "
        f"SurfaceOcean={valid_ratio * 100:.1f}% | Pull={elapsed:.2f}s | "
        f"TempRange=[{float(np.nanmin(ds['temperature'].values)):.2f}C .. "
        f"{float(np.nanmax(ds['temperature'].values)):.2f}C]\n"
        f"  -> Single Point @ ({point_lat:.2f}°, {point_lon:.2f}°, {target_depth:.0f}m): "
        f"T={point_temp:.2f}°C, S={point_sal:.2f}psu, U={point_u:.2f}m/s, V={point_v:.2f}m/s"
    )

    assert elapsed <= SLA_SECONDS, f"[{name}] Pull took {elapsed:.2f}s (SLA: {SLA_SECONDS}s)"
