"""Parse ocean telemetry xarray Datasets into Python dictionaries.

Generates a sample xarray Dataset for prototype testing and loads a local
NOAA Real-Time Ocean Forecasting System (RTOFS) NetCDF file to parse its
data variables, coordinates, dimensions, and attributes into dictionaries
and JSON output.
"""

import json
import pprint
from pathlib import Path
from typing import Any
import xarray as xr


def dataset_to_dict(ds: xr.Dataset, include_data: bool = True) -> dict[str, Any]:
    """Converts an xarray Dataset into a structured Python dictionary.

    Args:
        ds: Input xarray Dataset (e.g., ocean model output from NOAA RTOFS).
        include_data: Whether to include the underlying array values in the
            output. If False, returns only metadata, dimensions, and
            coordinates. Defaults to True.

    Returns:
        A dictionary containing ``dims``, ``attrs``, ``data_vars``, and
        ``coords`` keys mapped to their respective dataset components.
    """
    if include_data:
        ds = ds.astype(object).where(ds.notnull(), None)
    return ds.to_dict(data=include_data)


if __name__ == "__main__":
    # 1. Prototype test using a synthetic sample xarray Dataset
    sample_ds = xr.Dataset(
        data_vars={
            "temperature": (["x", "y"], [[20.5, 21.0], [19.8, 20.2]]),
            "humidity": (["x", "y"], [[65, 60], [70, 68]]),
        },
        coords={"x": [0, 1], "y": [10, 20]},
        attrs={"location": "Boston"},
    )
    sample_dict = dataset_to_dict(sample_ds)
    print("--- Sample Dataset Dictionary ---")
    pprint.pprint(sample_dict)

    # 2. Load the real RTOFS sample NetCDF file and export full_dict to JSON
    project_root = Path(__file__).resolve().parents[2]
    nc_path = project_root / "output" / "samples" / "massachusetts_3d.nc"
    json_out_path = project_root / "output" / "samples" / "massachusetts_3d.json"

    with xr.open_dataset(nc_path, engine="h5netcdf", decode_times=False) as mass_ds:
        # Convert to dictionary (includes metadata, coords, dims, and data)
        # TODO: Replace file load with live NOAA RTOFS ingestion
        full_dict = dataset_to_dict(mass_ds)

    # Ensure output directory exists, then write full_dict to JSON
    json_out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_out_path, "w", encoding="utf-8") as f:
        json.dump(full_dict, f, indent=2, default=str)

    print(f"\n--- RTOFS Dataset Exported ---")
    print("Dimensions:", full_dict["dims"])
    print("Variables:", list(full_dict["data_vars"].keys()))
    print(f"Full dictionary saved to: {json_out_path}")