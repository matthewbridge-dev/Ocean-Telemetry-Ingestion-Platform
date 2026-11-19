import rclpy
from rclpy.node import Node
from std_msgs.msg import String


from telemetry_ingest.data_serializer import DataStatic


from telemetry_ingest.data_dict import get_data_dict

class TelemetryPublisher(Node):
    def _init_(self):
        super()._init_('telemetry_publisher')