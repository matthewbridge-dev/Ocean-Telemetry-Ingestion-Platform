"""this file takes in the xarray data set and converts it into a dictionary file
"""

import numpy as np
import xarray as xr

# Create a sample xarray Dataset for testing
ds = xr.Dataset(
    data_vars={
        "temperature": (["x", "y"], [[20.5, 21.0], [19.8, 20.2]]),
        "humidity": (["x", "y"], [[65, 60], [70, 68]]),
    },
    coords={"x": [0, 1], "y": [10, 20]},
    attrs={"location": "Boston"},
)

# Convert to dictionary (includes metadata, coords, dims, and data)
# Will be changed to take in data from NOAA RTOFS
full_dict = ds.to_dict()