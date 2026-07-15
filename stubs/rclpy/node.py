from . import Logger, Parameter, Publisher, Timer

class Node:
    def __init__(self, name):
        self._name = name

    def get_logger(self):
        return Logger()

    def declare_parameter(self, name, value=None):
        return Parameter(value)

    def get_parameter(self, name):
        return Parameter(None)

    def create_publisher(self, msg_type, topic, qos_profile):
        return Publisher()

    def create_subscription(self, msg_type, topic, callback, qos_profile):
        return object()

    def create_timer(self, timer_period_sec, callback):
        return Timer()

    def destroy_node(self):
        pass