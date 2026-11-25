"""Generates and exports sample 3D ocean telemetry slices for reference regions.

Fetches 3D global ocean test regions (Massachusetts, Peru, Britain, South Africa)
from NOAA NOMADS via DataFetch and saves cropped slices to <repo_root>/output/samples/
in both native NetCDF format (for offline cached testing) and flattened CSV format
(for tabular inspection and manual validation).
"""
# PYTHONPATH=src python3 src/utils/inspect_samples.py

from pathlib import Path
from models.bounding_box import BoundingBox
from ingestion.data_fetcher import DataFetcher

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "output" / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

LOCATIONS: dict[str, BoundingBox] = {
    "massachusetts": BoundingBox(
        min_lon=-71.0, min_lat=40.5, max_lon=-69.5, max_lat=42.0, max_depth_m=100.0
    ),
    "peru": BoundingBox(
        min_lon=-79.0, min_lat=-13.5, max_lon=-77.0, max_lat=-11.5, max_depth_m=100.0
    ),
    "britain": BoundingBox(
        min_lon=-2.0, min_lat=50.0, max_lon=2.0, max_lat=52.0, max_depth_m=100.0
    ),
    "south_africa": BoundingBox(
        min_lon=17.5, min_lat=-35.5, max_lon=20.0, max_lat=-33.5, max_depth_m=100.0
    ),
}


def main() -> None:
    """Extracts, inspects, and exports sample telemetry slices for global test locations.

    Iterates through predefined geographic test regions, invokes DataFetcher to retrieve
    3D oceanographic datasets, writes NetCDF files, and generates cleaned CSV summaries
    with ocean-only points.
    """
    fetcher = DataFetcher()

    for name, box in LOCATIONS.items():
        ds = fetcher.fetch(box)

        # 1. Save native 3D NetCDF
        nc_path = SAMPLES_DIR / f"{name}_3d.nc"
        ds.to_netcdf(nc_path)

        # 2. Flatten to DataFrame, drop land/seabed NaNs, and export CSV
        df = ds.to_dataframe().reset_index()
        ocean_df = df.dropna(subset=["temperature", "salinity", "u", "v"])

        csv_path = SAMPLES_DIR / f"{name}_3d.csv"
        ocean_df.to_csv(csv_path, index=False)

        depths = sorted(ocean_df["Depth"].unique())
        print(
            f"\n=== {name.upper()} ({len(ocean_df)} valid 3D ocean cells across "
            f"{len(depths)} depth levels: {depths[0]}m..{depths[-1]}m) ==="
        )
        print(f"Saved: {csv_path.relative_to(REPO_ROOT)} & {nc_path.relative_to(REPO_ROOT)}")
        print(
            ocean_df[["Depth", "Latitude", "Longitude", "temperature", "salinity", "u", "v"]]
            .describe()
            .loc[["min", "mean", "max"]]
            .round(3)
        )


if __name__ == "__main__":
    main()
