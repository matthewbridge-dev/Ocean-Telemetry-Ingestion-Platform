"""mvp_demo.py

End-to-end MVP pipeline:
    BoundingBox -> DataFetcher -> ChunkNormalizer -> [MVP Pose Lookup] -> MessageBuilder -> Print
"""

# PYTHONPATH=src python src/mvp_demo.py

import logging
import math
import numpy as np

from models import BoundingBox, NormalizedChunk, EnvironmentSample, OceanEnvMsg
from ingestion import DataFetcher, ChunkNormalizer
from messaging import MessageBuilder


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def _to_optional_float(value: np.floating | float) -> float | None:
    """Convert a NumPy scalar to a native Python float, mapping NaN to None."""
    val = float(value)
    return None if math.isnan(val) else val


# --- TEMPORARY MVP STUB (Replaced by OceanGridChunk.query_chunk_at() later) ---
def mvp_query_chunk(
    chunk: NormalizedChunk,
    lat: float,
    lon: float,
    depth_m: float = 0.0,
) -> EnvironmentSample:
    """Extract the nearest ocean telemetry sample from a NormalizedChunk."""
    # 1. Nearest vertical depth index: O(D)
    d_idx = int(np.argmin(np.abs(chunk.depth_levels - depth_m)))

    # 2. Nearest horizontal ocean cell: O(Y * X) vectorized in C
    dist_sq = (chunk.lats - lat) ** 2 + (chunk.lons - lon) ** 2
    if np.all(np.isnan(dist_sq)):
        raise ValueError(f"No valid ocean cells in chunk near ({lat}, {lon}).")

    y_idx, x_idx = np.unravel_index(int(np.nanargmin(dist_sq)), dist_sq.shape)
    y_idx, x_idx = int(y_idx), int(x_idx)

    return EnvironmentSample(
        water_temp_c=_to_optional_float(chunk.water_temp_c[d_idx, y_idx, x_idx]),
        salinity_psu=_to_optional_float(chunk.salinity_psu[d_idx, y_idx, x_idx]),
        velocity_u_ms=_to_optional_float(chunk.velocity_u_ms[d_idx, y_idx, x_idx]),
        velocity_v_ms=_to_optional_float(chunk.velocity_v_ms[d_idx, y_idx, x_idx]),
        matched_lat=_to_optional_float(chunk.lats[y_idx, x_idx]),
        matched_lon=_to_optional_float(chunk.lons[y_idx, x_idx]),
        matched_depth_m=_to_optional_float(chunk.depth_levels[d_idx]),
    )
# ------------------------------------------------------------------------------


def mock_publish(msg: OceanEnvMsg) -> None:
    """Dead-end publisher stand-in for MVP verification."""
    print("\n" + "=" * 55)
    print("PUBLISHED OceanEnvMsg")
    print("=" * 55)
    print(f"  water_temp_c  : {msg.water_temp_c:.4f} °C")
    print(f"  salinity_psu  : {msg.salinity_psu:.4f} PSU")
    print(f"  velocity_u_ms : {msg.velocity_u_ms:.4f} m/s")
    print(f"  velocity_v_ms : {msg.velocity_v_ms:.4f} m/s")
    print("=" * 55 + "\n")


def run_mvp_pipeline() -> None:
    # 1. Static demo bounding box (open ocean off Massachusetts) & demo pose
    demo_bbox = BoundingBox(
        min_lon=-71.0,
        min_lat=40.5,
        max_lon=-69.5,
        max_lat=42.0,
        max_depth_m=100.0,
    )
    demo_lat, demo_lon, demo_depth_m = 41.0, -70.2, 10.0

    # 2. Initialize pipeline stages
    fetcher = DataFetcher()
    normalizer = ChunkNormalizer()
    builder = MessageBuilder(fallback_value=math.nan)

    # 3. Execute: Fetch -> Normalize -> Query -> Build -> Publish
    logger.info("Fetching RTOFS slice for %s...", demo_bbox)
    raw_ds = fetcher.fetch(demo_bbox)

    logger.info("Normalizing dataset into NormalizedChunk...")
    chunk = normalizer.normalize(raw_ds, demo_bbox)

    logger.info(
        "Querying chunk at pose (lat=%.4f, lon=%.4f, depth=%.1fm)...",
        demo_lat,
        demo_lon,
        demo_depth_m,
    )
    sample = mvp_query_chunk(chunk, demo_lat, demo_lon, demo_depth_m)
    logger.info(
        "Matched grid cell: (lat=%.4f, lon=%.4f, depth=%.1fm)",
        sample.matched_lat,
        sample.matched_lon,
        sample.matched_depth_m,
    )

    env_msg = builder.build(sample)
    mock_publish(env_msg)


if __name__ == "__main__":
    run_mvp_pipeline()