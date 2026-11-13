<!-- prettier-ignore -->
classDiagram
    %% ROS 2 Entry & Exit Boundary
    class OceanTelemetryNode {
        -Subscription _pose_sub
        -Publisher _env_pub
        -OceanDataContext _context
        -MessageSerializer _serializer
        +on_pose_received()
    }

    %% Context Controller
    class OceanDataContext {
        -OceanDataStrategy _active_strategy
        +__init__(OceanDataStrategy _intial_strategy)
        +set_strategy(OceanDataStrategy _new_strategy)
    }

    class OceanDataStrategy {
        <<Interface>>
        +get_environment_at(float lat, float lon, float depth)* LocalEnvironmentSample
    }

    class LiveGofsStrategy {
        -ChunkManager _chunk_manager
        -str _api_endpoint
        +__init__()
        +get_environment_at(float lat, float lon, float depth) LocalEnvironmentSample
    }

    class RepublishStrategy {
        +__init__()
        +get_environment_at(float lat, float lon, float depth) LocalEnvironmentSample
    }

    class CachedStrategy {
        -OceanGridChunk _offline_chunk
        -str _file_path
        +__init__()
        +get_environment_at(float lat, float lon, float depth) LocalEnvironmentSample
        -get_offline_chunk()
    }

    class StaticStrategy {
        -str _file_path
        +__init__(float temp, float salinity)
        +get_environment_at(float lat, float lon, float depth) LocalEnvironmentSample
        -get_static_data()
    }

    class MessageSerializer {
        +serialize(LocalEnvironmentSample sample) OceanEnvMsg
    }

    class LocalEnvironmentSample {
        <<Struct>>
        +float water_temp_c
        +float salinity_psu
        +float velocity_u_ms
        +float velocity_v_ms
    }

    %% Relationships
    OceanTelemetryNode *-- OceanDataContext : delegates lookup
    OceanTelemetryNode *-- MessageSerializer : formats ROS output
    OceanDataContext o-- OceanDataStrategy : routes active mode

    LiveGofsStrategy ..|> OceanDataStrategy : implements
    RepublishStrategy ..|> OceanDataStrategy : implements
    StaticStrategy ..|> OceanDataStrategy : implements
    CachedStrategy ..|> OceanDataStrategy : implements


    OceanDataStrategy ..> LocalEnvironmentSample : returns
    MessageSerializer ..> LocalEnvironmentSample : consumes
