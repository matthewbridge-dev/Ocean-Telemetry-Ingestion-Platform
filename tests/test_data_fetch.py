"""test_data_fetch.py

Integration test verifying Global RTOFS 3D data retrieval across four global regions:
- Massachusetts Coast (North Atlantic)
- Peru Coast (Southeast Pacific)
- South Africa Coast (Agulhas / South Atlantic-Indian)
- Britain Coast (Northeast Atlantic / North Sea — tests tripolar latitude > 47°N)
"""

from datetime import datetime, timedelta, timezone
import logging
import numpy as np
import pytest
from datapull.bounding_box import BoundingBox
from datapull.data_fetch import DataFetch

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

TEST_REGIONS: dict[str, BoundingBox] = {
    "massachusetts": BoundingBox(
        min_lon=-70.8,
        min_lat=40.5,
        max_lon=-68.0,
        max_lat=42.5,
        max_depth_m=150.0,
    ),
    "peru": BoundingBox(
        min_lon=-81.0,
        min_lat=-14.0,
        max_lon=-76.5,
        max_lat=-10.0,
        max_depth_m=150.0,
    ),
    "south_africa": BoundingBox(
        min_lon=16.5,
        min_lat=-36.0,
        max_lon=21.0,
        max_lat=-33.0,
        max_depth_m=150.0,
    ),
    "britain": BoundingBox(
        min_lon=-6.5,
        min_lat=49.5,
        max_lon=1.5,
        max_lat=55.5,
        max_depth_m=150.0,
    ),
}

REQUIRED_VARS = {"temperature", "salinity", "u", "v"}
MAX_AGE = timedelta(days=2)


@pytest.fixture(scope="module")
def fetcher() -> DataFetch:
  return DataFetch(fallback_days=3)


@pytest.mark.parametrize("region_name,bbox", list(TEST_REGIONS.items()))
def test_region_fetch_and_freshness(
    fetcher: DataFetch, region_name: str, bbox: BoundingBox
) -> None:
  ds = fetcher.fetch(bbox)

  # 1. Verify all required 3D variables exist
  assert REQUIRED_VARS.issubset(
      set(ds.data_vars)
  ), f"[{region_name}] Missing variables: {REQUIRED_VARS - set(ds.data_vars)}"

  # 2. Verify spatial and depth dimensions are non-empty and within requested max_depth_m
  assert (
      ds.sizes["Y"] > 0 and ds.sizes["X"] > 0
  ), f"[{region_name}] Empty spatial grid."
  assert ds.sizes["Depth"] > 1, f"[{region_name}] Expected multiple depth layers."
  assert float(ds["Depth"].max()) <= bbox.max_depth_m, (
      f"[{region_name}] Max depth {float(ds['Depth'].max())}m exceeded"
      f" {bbox.max_depth_m}m."
  )

  # 3. Verify each variable contains actual non-NaN ocean values
  for var in REQUIRED_VARS:
    arr = ds[var].values
    valid_count = int(np.count_nonzero(~np.isnan(arr)))
    assert valid_count > 0, f"[{region_name}] Variable '{var}' is 100% NaN."

  # 4. Verify model timestamp (MT) is within 2 days of current UTC time
  mt_val = ds["MT"].values
  # Handle scalar or 1-element datetime64 array
  mt_np = np.asarray(mt_val).reshape(-1)[0]
  model_time = datetime.fromtimestamp(
      mt_np.astype("datetime64[s]").astype("int64"), tz=timezone.utc
  )
  now_utc = datetime.now(timezone.utc)
  age = abs(now_utc - model_time)

  assert age <= MAX_AGE, (
      f"[{region_name}] Model data is stale: timestamp {model_time.isoformat()}"
      f" (age {age} > {MAX_AGE})."
  )

  print(
      f"PASS [{region_name}]: shape=(Depth={ds.sizes['Depth']},"
      f" Y={ds.sizes['Y']}, X={ds.sizes['X']}),"
      f" model_time={model_time.isoformat()}, temp_surface_mean={float(np.nanmean(ds['temperature'].isel(Depth=0).values)):.2f}°C"
  )


if __name__ == "__main__":
  # Allows running directly without pytest: `python test_data_fetch.py`
  df = DataFetch(fallback_days=3)
  for name, box in TEST_REGIONS.items():
    test_region_fetch_and_freshness(df, name, box)