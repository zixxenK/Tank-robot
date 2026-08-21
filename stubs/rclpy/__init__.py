"""Small deterministic ROS 2 runtime shim used by Windows unit tests.

The shim is intentionally not a ROS implementation. It provides enough of
the node API to instantiate the project's nodes, inspect published messages,
invoke callbacks, and validate launch contracts without requiring ROS on the
developer workstation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

__all__ = [
    "Node",
    "Logger",
    "Publisher",
    "Subscription",
    "Service",
    "Client",
    "Future",
    "Timer",
    "Parameter",
    "init",
    "shutdown",
    "spin",
    "spin_once",
    "ok",
]

_context_ok = False


class Logger:
    def __init__(self, name: str = "stub"):
        self.name = name
        self.records = []

    def _record(self, level: str, msg: Any) -> None:
        self.records.append((level, str(msg)))

    def info(self, msg):
        self._record("info", msg)

    def warn(self, msg):
        self._record("warn", msg)

    warning = warn

    def error(self, msg):
        self._record("error", msg)

    def debug(self, msg):
        self._record("debug", msg)


class Publisher:
    def __init__(self, msg_type=None, topic="", qos_profile=None):
        self.msg_type = msg_type
        self.topic = topic
        self.qos_profile = qos_profile
        self.messages = []
        self.last_msg = None

    def publish(self, msg):
        self.messages.append(msg)
        self.last_msg = msg


class Subscription:
    def __init__(self, msg_type=None, topic="", callback=None, qos_profile=None):
        self.msg_type = msg_type
        self.topic = topic
        self.callback = callback
        self.qos_profile = qos_profile

    def receive(self, msg):
        if self.callback is not None:
            return self.callback(msg)
        return None


class Service:
    def __init__(self, srv_type=None, name="", callback=None):
        self.srv_type = srv_type
        self.name = name
        self.callback = callback

    def call(self, request):
        response = self.srv_type.Response() if self.srv_type else None
        return self.callback(request, response) if self.callback else response


class Future:
    def __init__(self, result=None, exception=None):
        self._result = result
        self._exception = exception

    def done(self):
        return True

    def result(self):
        if self._exception is not None:
            raise self._exception
        return self._result


class Client:
    def __init__(self, srv_type=None, name="", available=True, response=None):
        self.srv_type = srv_type
        self.name = name
        self.available = available
        self.response = response

    def wait_for_service(self, timeout_sec=None):
        del timeout_sec
        return self.available

    def call_async(self, request):
        del request
        response = self.response
        if response is None and self.srv_type is not None:
            response = self.srv_type.Response()
            response.success = True
            response.message = "stub response"
        return Future(result=response)


class Timer:
    def __init__(self, period_sec=0.0, callback=None):
        self.period_sec = float(period_sec)
        self.callback = callback
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def trigger(self):
        if not self.cancelled and self.callback is not None:
            return self.callback()
        return None


class Parameter:
    def __init__(self, value=None, name=""):
        self.name = name
        self.value = value


def init(args=None):
    global _context_ok
    del args
    _context_ok = True


def shutdown():
    global _context_ok
    _context_ok = False


def spin(_node):
    # The shim never owns a real event loop. Tests invoke callbacks directly.
    return None


def spin_once(_node, _timeout_sec=None):
    del _timeout_sec
    return None


def ok():
    return _context_ok


from .node import Node  # noqa: E402
