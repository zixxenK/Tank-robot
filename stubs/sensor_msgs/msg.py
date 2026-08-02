from std_msgs.msg import Header


class BatteryState:
    def __init__(self):
        self.header = Header()
        self.voltage = float("nan")
        self.current = float("nan")


class Image:
    def __init__(self):
        self.header = Header()


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
    def __init__(self):
        self.header = Header()


class JointState:
    def __init__(self):
        self.header = Header()
        self.name = []
        self.position = []
        self.velocity = []
        self.effort = []
