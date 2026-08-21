from geometry_msgs.msg import Pose2D
from std_msgs.msg import Header


class ObjectHypothesis:
    def __init__(self):
        self.class_id = ""
        self.score = 0.0


class ObjectHypothesisWithPose:
    def __init__(self):
        self.hypothesis = ObjectHypothesis()
        self.pose = Pose2D()


class _BoundingBox2D:
    def __init__(self):
        self.center = Pose2D()
        self.size_x = 0.0
        self.size_y = 0.0


class Detection2D:
    def __init__(self):
        self.header = Header()
        self.results = []
        self.bbox = _BoundingBox2D()


class Detection2DArray:
    def __init__(self):
        self.header = Header()
        self.detections = []
