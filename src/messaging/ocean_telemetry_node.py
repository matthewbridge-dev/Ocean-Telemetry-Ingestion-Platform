"""src/messaging/ocean_telemetry_node.py

ROS 2 node managing outbound /environment publishing (and future pose subscription).
"""

import rclpy
from rclpy.node import Node
from ocean_interfaces.msg import Environment

ENV_TOPIC: str = "/environment"
DEFAULT_QOS_DEPTH: int = 10
MVP_PUBLISH_PERIOD_SEC: float = 1.0


class OceanTelemetryNode(Node):
    """ROS 2 boundary node for the Ocean Telemetry Ingestion Platform."""

    def __init__(self, mvp_msg: Environment | None = None) -> None:
        super().__init__("ocean_telemetry_node")

        # Outbound environment publisher
        self._env_pub = self.create_publisher(
            Environment,
            ENV_TOPIC,
            DEFAULT_QOS_DEPTH,
        )

        # Future pose subscriber hook:
        # self._pose_sub = self.create_subscription(
        #     UuvPoseMsg,
        #     "/uuv_telemetry",
        #     self.on_pose_received,
        #     DEFAULT_QOS_DEPTH,
        # )

        # MVP heartbeat: republishes the single fetched message at 1 Hz so
        # `ros2 topic echo /environment` can observe it before shutdown.
        self._mvp_msg = mvp_msg
        self._mvp_timer = None
        if self._mvp_msg is not None:
            self._mvp_timer = self.create_timer(
                MVP_PUBLISH_PERIOD_SEC,
                self._publish_mvp_heartbeat,
            )
            self.get_logger().info(
                f"MVP publisher active on {ENV_TOPIC} at 1 Hz (Ctrl+C to stop)..."
            )

    def publish_environment(self, msg: Environment) -> None:
        """Publish a single Environment message onto the ROS 2 network."""
        self._env_pub.publish(msg)
        self.get_logger().info(
            f"Published {ENV_TOPIC} -> "
            f"xdot={msg.xdot_ms:.3f}m/s, "
            f"ydot={msg.ydot_ms:.3f}m/s, "
            f"sal={msg.salinity_ppt:.2f}ppt, "
            f"temp={msg.temperature_c:.2f}C"
        )

    def _publish_mvp_heartbeat(self) -> None:
        if self._mvp_msg is not None:
            self.publish_environment(self._mvp_msg)


def run_mvp_publisher(msg: Environment) -> None:
    """Initialize rclpy, spin OceanTelemetryNode for the MVP message, and clean up."""
    rclpy.init()
    node = OceanTelemetryNode(mvp_msg=msg)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()