"""src/mvp_demo.py

End-to-end MVP pipeline:
    BoundingBox -> DataFetcher -> ChunkNormalizer -> [MVP Pose Lookup] -> MessageBuilder -> OceanTelemetryNode
"""

import logging
import math
import numpy as np

from ingestion.chunk_normalizer import ChunkNormalizer
from ingestion.data_fetcher import DataFetcher
from messaging.message_builder import MessageBuilder
from messaging.ocean_telemetry_node import run_mvp_publisher
from models.bounding_box import BoundingBox
from models.environment_sample import EnvironmentSample
from models.normalized_chunk import NormalizedChunk

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
    d_idx = int(np.argmin(np.abs(chunk.depth_levels - depth_m)))

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


def run_mvp_pipeline() -> None:
    demo_bbox = BoundingBox(
        min_lon=-71.0,
        min_lat=40.5,
        max_lon=-69.5,
        max_lat=42.0,
        max_depth_m=100.0,
    )
    demo_lat, demo_lon, demo_depth_m = 41.0, -70.2, 10.0

    fetcher = DataFetcher()
    normalizer = ChunkNormalizer()
    builder = MessageBuilder(fallback_value=math.nan)

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
    run_mvp_publisher(env_msg)


if __name__ == "__main__":
    run_mvp_pipeline()