from std_msgs.msg import Header


class BatteryState:
    def __init__(self):
        self.header = Header()
        self.voltage = float("nan")
        self.current = float("nan")
        self.percentage = float("nan")
        self.power_supply_status = 0


class Image:
    def __init__(self):
        self.header = Header()
        self.height = 0
        self.width = 0
        self.encoding = ""
        self.is_bigendian = 0
        self.step = 0
        self.data = b""


class CompressedImage:
    def __init__(self):
        self.header = Header()
        self.format = ""
        self.data = b""


class _Vector3:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0


class Imu:
    def __init__(self):
        self.header = Header()
        self.linear_acceleration = _Vector3()
        self.angular_velocity = _Vector3()


class Joy:
    def __init__(self, axes=None, buttons=None):
        self.header = Header()
        self.axes = list(axes) if axes is not None else []
        self.buttons = list(buttons) if buttons is not None else []


class JointState:
    def __init__(self):
        self.header = Header()
        self.name = []
        self.position = []
        self.velocity = []
        self.effort = []


class LaserScan:
    def __init__(self):
        self.header = Header()
        self.angle_min = 0.0
        self.angle_max = 0.0
        self.angle_increment = 0.0
        self.time_increment = 0.0
        self.scan_time = 0.0
        self.range_min = 0.0
        self.range_max = 0.0
        self.ranges = []
        self.intensities = []


class Range:
    ULTRASOUND = 0

    def __init__(self):
        self.header = Header()
        self.radiation_type = self.ULTRASOUND
        self.field_of_view = 0.0
        self.min_range = 0.0
        self.max_range = 0.0
        self.range = 0.0


class Float32MultiArray:
    def __init__(self, data=None):
        self.data = list(data) if data is not None else []
