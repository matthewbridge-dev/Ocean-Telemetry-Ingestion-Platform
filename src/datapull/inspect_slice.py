"""inspect_slice.py

Pulls a live RTOFS 2D surface slice off the coast of Massachusetts, displays it as a
Pandas DataFrame, and exports both CSV and NetCDF files for inspection.
"""

import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bounding_box import BoundingBox
from data_fetch import DataFetch

# Configure root logging so DataFetch's logger.info() calls appear in the terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

OUTPUT_DIR = Path("output")


def main() -> None:
    # 1x1 degree surface chunk off the Massachusetts coast (Cape Cod / Stellwagen Bank)
    ma_bounds = BoundingBox(
        min_lon=-70.5,
        min_lat=41.5,
        max_lon=-69.5,
        max_lat=42.5,
    )

    fetcher = DataFetch(fallback_days=3)
    ds = fetcher.fetch(ma_bounds)

    # Flatten the 2D xarray.Dataset (Y, X) into a tabular Pandas DataFrame
    df = ds.to_dataframe().reset_index()

    # Separate valid ocean surface cells from NaN land-mask cells for cleaner inspection
    ocean_df = df.dropna(subset=["temperature"])

    print("\n" + "=" * 65)
    print("RTOFS 2D SURFACE SLICE SUMMARY (MASSACHUSETTS COAST)")
    print("=" * 65)
    print(f"Dataset Dimensions : {dict(ds.sizes)}")
    print(f"Total Grid Cells   : {len(df):,}")
    print(f"Valid Ocean Cells  : {len(ocean_df):,} ({len(df) - len(ocean_df):,} NaN land cells)")
    print(f"Columns            : {list(df.columns)}")
    print("\n--- First 10 Valid Ocean Surface Rows ---")
    print(ocean_df.head(10).to_string(index=False))

    # Export to disk
    OUTPUT_DIR.mkdir(exist_ok=True)
    csv_path = OUTPUT_DIR / "ma_coast_surface.csv"
    nc_path = OUTPUT_DIR / "ma_coast_surface.nc"

    ocean_df.to_csv(csv_path, index=False)
    ds.to_netcdf(nc_path)

    print("\n--- Exported Files ---")
    print(f"CSV (valid ocean rows) : {csv_path} ({csv_path.stat().st_size / 1024:.1f} KB)")
    print(f"NetCDF (raw xarray)    : {nc_path} ({nc_path.stat().st_size / 1024:.1f} KB)")
    print("=" * 65)


if __name__ == "__main__":
    main()
