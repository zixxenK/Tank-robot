class _Header:
    def __init__(self):
        self.frame_id = ""
        self.stamp = None


class _PosePosition:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0


class _Pose:
    def __init__(self):
        self.position = _PosePosition()


class _Scale:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0


class _Color:
    def __init__(self):
        self.a = 0.0
        self.r = 0.0
        self.g = 0.0
        self.b = 0.0


class Marker:
    ADD = 0
    ARROW = 0
    TEXT_VIEW_FACING = 9

    def __init__(self):
        self.header = _Header()
        self.ns = ""
        self.id = 0
        self.type = 0
        self.action = Marker.ADD
        self.points = []
        self.pose = _Pose()
        self.scale = _Scale()
        self.color = _Color()
        self.text = ""


class MarkerArray:
    def __init__(self):
        self.markers = []
