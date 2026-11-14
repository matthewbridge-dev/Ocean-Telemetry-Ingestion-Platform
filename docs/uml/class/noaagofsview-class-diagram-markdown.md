<!-- prettier-ignore -->
classDiagram
    %% Subsystem Entry Point (Replaces the ROS 2 Node)
    class LiveGofsStrategy {
        -ChunkManager _chunk_manager
        -str api_url
        +__init__()
        +get_environment_at(float lat, float lon, float depth) LocalEnvironmentSample
    }

    %% Core Request Handler
    class ChunkManager {
        -RefreshTracker _tracker
        -BoundingBoxCalculator _bounds_calc
        -OceanGridChunk _grid_chunk
        -IngestionPipeline _pipeline
        -check_data_refresh(float current_lat, float current_lon)
    }

    class RefreshTracker {
        -int _threshold_margin_km
        -int _max_age_sec
        +is_approaching_edge(float lat, float lon, BoundingBox current_box) bool
        +is_temporally_stale(datetime fetched_at) bool
    }

    class BoundingBoxCalculator {
        -float _default_radius_km
        +compute_box(float center_lat, float center_lon) BoundingBox
    }

    %% In-Memory Cache Store
    class OceanGridChunk {
        -NormalizedChunk _active_chunk
        +update_chunk(NormalizedChunk new_chunk)
        +query_chunk_at(float lat, float lon, float depth) LocalEnvironmentSample
    }

    %% Background Ingestion Pipeline
    class IngestionPipeline {
        -DataFetcher _fetcher
        -DataParser _parser
        +fetch_and_parse(BoundingBox target_box) NormalizedChunk
    }

    class DataFetcher {
        +__init__(str api_url)
        +fetch_subset(BoundingBox box) RawNetCDFData
    }

    class DataParser {
        +parse_to_grid(RawNetCDFData raw, BoundingBox box) NormalizedChunk
    }

    %% Data Transfer Objects (@dataclass)
    class NormalizedChunk {
        <<Struct>>
        +BoundingBox bounds
        +datetime timestamp
        +list~float~ depth_levels
        +SOMEKIND OF GRID STORE
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
    LiveGofsStrategy *-- ChunkManager : execute pipeline

    %% Internal Composition
    ChunkManager *-- RefreshTracker : evaluates data freshness
    ChunkManager *-- BoundingBoxCalculator : generates new bounds
    ChunkManager *-- OceanGridChunk : writes chunk
    ChunkManager *-- IngestionPipeline : request new data

    IngestionPipeline *-- DataFetcher : pulls raw data
    IngestionPipeline *-- DataParser : normalizes data

    %% Data Flow Dependencies
    OceanGridChunk o-- NormalizedChunk : holds in memory
    OceanGridChunk ..> LocalEnvironmentSample : extracts from local cache
    DataFetcher ..> DataParser : passes raw data
    DataParser ..> NormalizedChunk : produces

    %% Output Contract
    LiveGofsStrategy ..> LocalEnvironmentSample : returns
