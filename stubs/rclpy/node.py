from . import Logger, Parameter, Publisher, Timer


class _ClockTime:
    def to_msg(self):
        return object()


class _Clock:
    def now(self):
        return _ClockTime()


class Node:
    def __init__(self, _name):
        self._name = _name

    def get_logger(self):
        return Logger()

    def declare_parameter(self, _name, value=None):
        return Parameter(value)

    def get_parameter(self, _name):
        return Parameter(None)

    def create_publisher(self, _msg_type, _topic, _qos_profile):
        return Publisher()

    def create_subscription(self, _msg_type, _topic, _callback, _qos_profile):
        return object()

    def create_service(self, _srv_type, _service, _callback):
        return object()

    def create_timer(self, _timer_period_sec, _callback):
        return Timer()

    def get_clock(self):
        return _Clock()

    def destroy_node(self):
        pass
