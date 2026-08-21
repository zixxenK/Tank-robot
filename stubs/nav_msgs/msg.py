from geometry_msgs.msg import Point, Quaternion, Twist
from std_msgs.msg import Header


class _Pose:
    def __init__(self):
        self.position = Point()
        self.orientation = Quaternion()


class _PoseWithCovariance:
    def __init__(self):
        self.pose = _Pose()


class _TwistWithCovariance:
    def __init__(self):
        self.twist = Twist()


class Odometry:
    def __init__(self, x=0.0, y=0.0):
        self.header = Header()
        self.child_frame_id = ""
        self.pose = _PoseWithCovariance()
        self.twist = _TwistWithCovariance()
        self.pose.pose.position.x = float(x)
        self.pose.pose.position.y = float(y)


class MapMetaData:
    def __init__(self):
        self.width = 0
        self.height = 0
        self.resolution = 0.0
        self.origin = type("Origin", (), {"position": Point()})()


class OccupancyGrid:
    def __init__(self):
        self.header = Header()
        self.info = MapMetaData()
        self.data = []


class Path:
    def __init__(self):
        self.header = Header()
        self.poses = []
