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


class Quaternion:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.w = 1.0
