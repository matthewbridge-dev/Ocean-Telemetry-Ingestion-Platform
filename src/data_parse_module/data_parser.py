"""Parse ocean telemetry xarray Datasets into Python dictionaries.

generates a sample xarray Dataset for prototype testing. Intended to
ingest NOAA Real-Time Ocean Forecasting System (RTOFS) datasets and parse
their data variables, coordinates, dimensions, and attributes into dictionaries.
"""

from typing import Any
import numpy as np
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
    return ds.to_dict(data=include_data)


if __name__ == "__main__":
    # Create a sample xarray Dataset for testing
    sample_ds = xr.Dataset(
        data_vars={
            "temperature": (["x", "y"], [[20.5, 21.0], [19.8, 20.2]]),
            "humidity": (["x", "y"], [[65, 60], [70, 68]]),
        },
        coords={"x": [0, 1], "y": [10, 20]},
        attrs={"location": "Boston"},
    )

    # Convert to dictionary (includes metadata, coords, dims, and data)
    # TODO: Replace sample_ds with live NOAA RTOFS ingestion
    full_dict = dataset_to_dict(sample_ds)