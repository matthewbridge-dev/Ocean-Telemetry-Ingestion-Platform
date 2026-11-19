"""dump_samples.py

Fetches the 4 global test regions and saves cropped slices to <repo_root>/output/samples/
as both CSV (for manual inspection) and NetCDF (for offline CachedStrategy testing).
"""

# Run from Root
# PYTHONPATH=src python src/datapull/inspect_samples.py

from pathlib import Path
from datapull.bounding_box import BoundingBox
from datapull.data_fetch import DataFetch

# Resolve <repo_root>/output/samples/ from src/datapull/dump_samples.py
REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "output" / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

LOCATIONS: dict[str, BoundingBox] = {
    "massachusetts": BoundingBox(min_lon=-71.0, min_lat=40.5, max_lon=-69.5, max_lat=42.0),
    "peru": BoundingBox(min_lon=-79.0, min_lat=-13.5, max_lon=-77.0, max_lat=-11.5),
    "britain": BoundingBox(min_lon=-2.0, min_lat=50.0, max_lon=2.0, max_lat=52.0),
    "south_africa": BoundingBox(min_lon=17.5, min_lat=-35.5, max_lon=20.0, max_lat=-33.5),
}


def main() -> None:
    fetcher = DataFetch(fallback_days=2)

    for name, box in LOCATIONS.items():
        ds = fetcher.fetch(box)

        # 1. Save native NetCDF (useful later for CachedStrategy)
        nc_path = SAMPLES_DIR / f"{name}.nc"
        ds.to_netcdf(nc_path)

        # 2. Flatten to DataFrame, drop land-masked NaNs, and export CSV for eyeballing
        df = ds.to_dataframe().reset_index()
        ocean_df = df.dropna(subset=["temperature", "salinity", "u", "v"])

        csv_path = SAMPLES_DIR / f"{name}.csv"
        ocean_df.to_csv(csv_path, index=False)

        print(f"\n=== {name.upper()} ({len(ocean_df)} valid ocean points) ===")
        print(f"Saved: {csv_path.relative_to(REPO_ROOT)} & {nc_path.relative_to(REPO_ROOT)}")
        print(
            ocean_df[["Latitude", "Longitude", "temperature", "salinity", "u", "v"]]
            .describe()
            .loc[["min", "mean", "max"]]
            .round(3)
        )


if __name__ == "__main__":
    main()