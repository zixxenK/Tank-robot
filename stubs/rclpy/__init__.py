__all__ = [
    "Node",
    "Logger",
    "Publisher",
    "Timer",
    "Parameter",
    "init",
    "shutdown",
    "spin",
    "spin_once",
    "ok",
]


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
    _ = args


def shutdown():
    pass


def spin(_node):
    pass


def spin_once(_node, _timeout_sec=None):
    pass


def ok():
    return True


from .node import Node  # noqa: E402
