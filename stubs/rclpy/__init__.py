from .node import Node

class Logger:
    def info(self, msg):
        pass

    def warn(self, msg):
        pass

    def error(self, msg):
        pass

    def debug(self, msg):
        pass

class Publisher:
    def publish(self, msg):
        pass

class Timer:
    pass

class Parameter:
    def __init__(self, value=None):
        self.value = value


def init(args=None):
    pass


def shutdown():
    pass


def spin(node):
    pass


def spin_once(node, timeout_sec=None):
    pass