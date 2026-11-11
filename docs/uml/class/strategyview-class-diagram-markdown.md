<!-- prettier-ignore -->
classDiagram
    %% Configuration Struct
    class SimConfig {
        <<Struct>>
        +str mode
        +str api_url
        +str cache_filepath
        +float default_temp_c
        +float default_salinity_psu
    }

    %% ROS 2 Entry & Exit Boundary
    class OceanTelemetryNode {
        -Subscription~UuvPoseMsg~ _pose_sub
        -Publisher~OceanEnvMsg~ _env_pub
        -SimulationContext _sim_context
        -MessageSerializer _serializer
        +on_pose_received(UuvPoseMsg msg)
    }

    %% State & Strategy Router
    class SimulationContext {
        -SimConfig _config
        -OceanDataStrategy _active_strategy
        +__init__(SimConfig config)
        +get_environment_at(float lat, float lon, float depth) LocalEnvironmentSample
        -_verify_connection() bool
        -_fallback_to_cache(str error_msg)
    }

    class OceanDataStrategy {
        <<Interface>>
        +get_environment_at(float lat, float lon, float depth)* LocalEnvironmentSample
    }

    class LiveGofsStrategy {
        -ChunkManager _chunk_manager
        +__init__(str api_url)
        +get_environment_at(float lat, float lon, float depth) LocalEnvironmentSample
    }

    class RepublishStrategy {

    }

    class CachedStrategy {
        -OceanGridChunk _offline_chunk
        +__init__(str filepath)
        +get_environment_at(float lat, float lon, float depth) LocalEnvironmentSample
    }

    class StaticStrategy {
        -LocalEnvironmentSample _static_sample
        +__init__(float temp, float salinity)
        +get_environment_at(float lat, float lon, float depth) LocalEnvironmentSample
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
    OceanTelemetryNode *-- SimulationContext : delegates lookup
    OceanTelemetryNode *-- MessageSerializer : formats ROS output
    SimulationContext *-- SimConfig : configured by
    SimulationContext o-- OceanDataStrategy : routes active mode

    LiveGofsStrategy ..|> OceanDataStrategy : implements
    RepublishStrategy ..|> OceanDataStrategy : implements
    StaticStrategy ..|> OceanDataStrategy : implements
    CachedStrategy ..|> OceanDataStrategy : implements


    OceanDataStrategy ..> LocalEnvironmentSample : returns
    MessageSerializer ..> LocalEnvironmentSample : consumes
