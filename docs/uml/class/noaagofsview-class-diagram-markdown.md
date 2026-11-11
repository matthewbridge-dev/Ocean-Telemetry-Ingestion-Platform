<!-- prettier-ignore -->
classDiagram
    %% Subsystem Entry Point (Replaces the ROS 2 Node)
    class LiveGofsStrategy {
        -ChunkManager _chunk_manager
        +__init__(str api_url)
        +get_environment_at(float lat, float lon, float depth) LocalEnvironmentSample
    }

    %% Core Request Handler
    class ChunkManager {
        -RefreshTracker _tracker
        -BoundingBoxCalculator _bbox_calc
        -OceanGridChunk _grid_chunk
        -IngestionPipeline _pipeline
        -bool _is_fetching
        +__init__(str api_url)
        +get_environment_at(float lat, float lon, float depth) LocalEnvironmentSample
        -_trigger_async_refresh(float center_lat, float center_lon)
    }

    class RefreshTracker {
        -float _margin_threshold_km
        -float _max_age_sec
        +is_approaching_edge(float lat, float lon, BoundingBox current_box) bool
        +is_temporally_stale(datetime fetched_at) bool
    }

    class BoundingBoxCalculator {
        -float _default_radius_km
        +compute_box(float center_lat, float center_lon) BoundingBox
    }

    %% In-Memory Cache Store
    class OceanGridChunk {
        -RWLock _rw_lock
        -NormalizedGridChunk _active_chunk
        +update_chunk(NormalizedGridChunk new_chunk)
        +query_point(float lat, float lon, float depth) LocalEnvironmentSample
        +get_current_bounds() BoundingBox
        -_trilinear_interpolate(float lat, float lon, float depth) LocalEnvironmentSample
    }

    %% Background Ingestion Pipeline
    class IngestionPipeline {
        -DataFetcher _fetcher
        -DataParser _parser
        +fetch_and_parse(BoundingBox target_box) NormalizedGridChunk
    }

    class DataFetcher {
        -str _gofs_endpoint
        +fetch_subset(BoundingBox box) RawNetCDFData
    }

    class DataParser {
        +parse_to_grid(RawNetCDFData raw, BoundingBox box) NormalizedGridChunk
    }

    %% Data Transfer Objects (@dataclass)
    class NormalizedGridChunk {
        <<Struct>>
        +BoundingBox bounds
        +datetime timestamp
        +float grid_resolution_deg
        +list~float~ depth_levels
        +ndarray~OceanVoxel~ data_grid
    }

    class LocalEnvironmentSample {
        <<Struct>>
        +float water_temp_c
        +float salinity_psu
        +float velocity_u_ms
        +float velocity_v_ms
    }

    class BoundingBox {
        <<Struct>>
        +float min_lat
        +float max_lat
        +float min_lon
        +float max_lon
    }

    %% Subsystem Orchestration
    LiveGofsStrategy *-- ChunkManager : encapsulates pipeline

    %% Internal Composition
    ChunkManager *-- RefreshTracker : evaluates bounds
    ChunkManager *-- BoundingBoxCalculator : generates new bounds
    ChunkManager *-- OceanGridChunk : reads/writes chunk
    ChunkManager *-- IngestionPipeline : dispatches async pulls

    IngestionPipeline *-- DataFetcher : pulls raw subset
    IngestionPipeline *-- DataParser : normalizes array

    %% Data Flow Dependencies
    OceanGridChunk o-- NormalizedGridChunk : holds in RAM
    OceanGridChunk ..> LocalEnvironmentSample : extracts in O(1)
    DataFetcher ..> DataParser : passes RawNetCDFData
    DataParser ..> NormalizedGridChunk : produces

    %% Output Contract
    LiveGofsStrategy ..> LocalEnvironmentSample : returns
