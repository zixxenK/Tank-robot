# flake8: noqa


class Vector3:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0


class Twist:
    def __init__(self):
        self.linear = Vector3()
        self.angular = Vector3()


class Point:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0


class Pose2D:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0


class _Pose:
    def __init__(self):
        self.position = Point()
        self.orientation = Quaternion()


class Pose:
    def __init__(self):
        self.position = Point()
        self.orientation = Quaternion()


class PoseStamped:
    def __init__(self):
        from std_msgs.msg import Header
        self.header = Header()
        self.pose = Pose()


class _Vector3Stamped:
    def __init__(self):
        from std_msgs.msg import Header
        self.header = Header()
        self.vector = Vector3()


class Transform:
    def __init__(self):
        self.translation = Vector3()
        self.rotation = Quaternion()


class TransformStamped:
    def __init__(self):
        from std_msgs.msg import Header
        self.header = Header()
        self.child_frame_id = ""
        self.transform = Transform()


class Quaternion:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.w = 1.0
