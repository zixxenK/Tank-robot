from . import Client, Logger, Parameter, Publisher, Service, Subscription, Timer


class _ClockTime:
    def __init__(self, nanoseconds=1):
        self.nanoseconds = nanoseconds

    def to_msg(self):
        class _Time:
            sec = 0
            nanosec = 1
        return _Time()


class _Clock:
    def now(self):
        return _ClockTime()


class Node:
    def __init__(self, _name):
        self._name = _name
        self._parameters = {}
        self._logger = Logger(_name)
        self.publishers = []
        self.subscriptions = []
        self.services = []
        self.timers = []

    def get_logger(self):
        return self._logger

    def declare_parameter(self, _name, value=None):
        parameter = self._parameters.setdefault(
            _name, Parameter(value, _name)
        )
        return parameter

    def get_parameter(self, _name):
        return self._parameters.get(_name, Parameter(None, _name))

    def create_publisher(self, _msg_type, _topic, _qos_profile):
        publisher = Publisher(_msg_type, _topic, _qos_profile)
        self.publishers.append(publisher)
        return publisher

    def create_subscription(self, _msg_type, _topic, _callback, _qos_profile):
        subscription = Subscription(
            _msg_type, _topic, _callback, _qos_profile
        )
        self.subscriptions.append(subscription)
        return subscription

    def create_service(self, _srv_type, _service, _callback):
        service = Service(_srv_type, _service, _callback)
        self.services.append(service)
        return service

    def create_client(self, _srv_type, _service):
        client = Client(_srv_type, _service)
        return client

    def create_timer(self, _timer_period_sec, _callback):
        timer = Timer(_timer_period_sec, _callback)
        self.timers.append(timer)
        return timer

    def get_clock(self):
        return _Clock()

    def destroy_node(self):
        for timer in self.timers:
            timer.cancel()
