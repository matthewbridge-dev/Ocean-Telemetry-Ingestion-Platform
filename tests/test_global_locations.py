"""test_global_locations.py

Pytest smoke and latency suite for 3D DataFetch across four global coastal regions.
"""

import time
import numpy as np
import pytest
from datapull.bounding_box import BoundingBox
from datapull.data_fetch import DataFetch

SLA_SECONDS = 30.0
REQUIRED_VARS = ("temperature", "salinity", "u", "v")


@pytest.fixture(scope="module")
def fetcher() -> DataFetch:
    """Single shared DataFetch instance so coordinate/depth caching is tested."""
    return DataFetch(fallback_days=2)


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
def test_global_location_fetch(fetcher: DataFetch, name: str, box: BoundingBox) -> None:
    t0 = time.perf_counter()
    ds = fetcher.fetch(box)
    elapsed = time.perf_counter() - t0

    for var in REQUIRED_VARS:
        assert var in ds.data_vars, f"[{name}] Missing variable: {var}"

    # Verify 3D depth dimension was populated
    assert "Depth" in ds.sizes and ds.sizes["Depth"] > 1, (
        f"[{name}] Expected multiple depth layers, got {ds.sizes.get('Depth')}"
    )
    assert float(ds["Depth"].max()) <= box.max_depth_m

    # Verify surface layer has non-NaN ocean points (deeper layers naturally mask out on shallow shelves)
    surface_temp = ds["temperature"].isel(Depth=0).values
    valid_ratio = float(np.isfinite(surface_temp).mean())
    assert valid_ratio > 0.0, f"[{name}] Surface slice returned 100% NaN."

    print(
        f"\n[{name}] Grid=(D={ds.sizes['Depth']} [0..{float(ds['Depth'].max()):.0f}m], "
        f"Y={ds.sizes['Y']}, X={ds.sizes['X']}) | "
        f"SurfaceOcean={valid_ratio * 100:.1f}% | Pull={elapsed:.2f}s | "
        f"TempRange=[{float(np.nanmin(ds['temperature'].values)):.2f}C .. "
        f"{float(np.nanmax(ds['temperature'].values)):.2f}C]"
    )

    assert elapsed <= SLA_SECONDS, f"[{name}] Pull took {elapsed:.2f}s (SLA: {SLA_SECONDS}s)"