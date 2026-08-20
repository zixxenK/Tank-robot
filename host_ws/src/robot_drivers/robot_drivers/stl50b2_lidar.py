"""ROS 2 driver for a directly connected LDROBOT STL-50B2."""

import importlib
import os
import queue
import select
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import rclpy
import serial
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import LaserScan

from .stl50b2_parser import (
    STL50B2StreamParser,
    SynchronizedScan,
    SynchronizedScanAssembler,
)


class SyncInputError(RuntimeError):
    """Required header-pin synchronization input is unavailable."""


class GpioSyncReader:
    """Read rising edges from ROCK64 GPIO2_A3 (header pin 12).

    libgpiod is preferred.  The sysfs fallback exists for older ROCK64 vendor
    kernels that expose GPIO events only through ``/sys/class/gpio``.
    """

    def __init__(
        self,
        chip_path: str,
        line_offset: int,
        global_number: int,
        callback: Callable[[int], None],
        allow_sysfs_fallback: bool = True,
    ) -> None:
        """Configure the sync line without opening it yet."""
        self._chip_path = chip_path
        self._line_offset = line_offset
        self._global_number = global_number
        self._callback = callback
        self._allow_sysfs_fallback = allow_sysfs_fallback
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._resource = None
        self._sysfs_fd: Optional[int] = None
        self._sysfs_exported = False

    def start(self) -> None:
        """Open the GPIO event source and start its reader thread."""
        if self._thread is not None:
            return
        if self._start_gpiod():
            target = self._read_gpiod
        elif self._allow_sysfs_fallback and self._start_sysfs():
            target = self._read_sysfs
        else:
            raise SyncInputError(
                "cannot open required sync GPIO2_A3/header pin 12; "
                "check GPIO pin mux, /dev/gpiochip2, and permissions"
            )
        self._thread = threading.Thread(
            target=target,
            name="stl50b2-sync",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the reader and release the GPIO line."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._thread = None
        if self._resource is not None:
            for method_name in ("release", "close"):
                method = getattr(self._resource, method_name, None)
                if method is not None:
                    method()
                    break
            self._resource = None
        if self._sysfs_fd is not None:
            os.close(self._sysfs_fd)
            self._sysfs_fd = None
        if self._sysfs_exported:
            try:
                Path("/sys/class/gpio/unexport").write_text(
                    str(self._global_number), encoding="ascii"
                )
            except OSError:
                pass
            self._sysfs_exported = False

    def _start_gpiod(self) -> bool:
        """Try libgpiod v1 and v2 APIs."""
        try:
            gpiod = importlib.import_module("gpiod")
        except ImportError:
            return False

        if hasattr(gpiod, "Chip"):
            try:
                chip = gpiod.Chip(self._chip_path)
                line = chip.get_line(self._line_offset)
                line.request(
                    consumer="stl50b2_lidar",
                    type=gpiod.LINE_REQ_EV_RISING_EDGE,
                )
                self._resource = line
                return True
            except (AttributeError, OSError, RuntimeError):
                try:
                    chip.close()
                except (AttributeError, OSError):
                    pass

        try:
            settings = gpiod.LineSettings(
                direction=gpiod.line.Direction.INPUT,
                edge_detection=gpiod.line.Edge.RISING,
            )
            request = gpiod.request_lines(
                self._chip_path,
                consumer="stl50b2_lidar",
                config={self._line_offset: settings},
            )
            self._resource = request
            return True
        except (AttributeError, OSError, RuntimeError):
            return False

    def _start_sysfs(self) -> bool:
        """Open the legacy sysfs GPIO event interface."""
        gpio_path = Path("/sys/class/gpio") / f"gpio{self._global_number}"
        try:
            if not gpio_path.exists():
                Path("/sys/class/gpio/export").write_text(
                    str(self._global_number), encoding="ascii"
                )
                self._sysfs_exported = True
            (gpio_path / "direction").write_text("in", encoding="ascii")
            fd = os.open(gpio_path / "value", os.O_RDONLY | os.O_NONBLOCK)
            os.lseek(fd, 0, os.SEEK_SET)
            os.read(fd, 1)
            self._sysfs_fd = fd
            return True
        except OSError:
            if self._sysfs_fd is not None:
                os.close(self._sysfs_fd)
                self._sysfs_fd = None
            return False

    def _read_gpiod(self) -> None:
        """Read events using whichever libgpiod API opened successfully."""
        resource = self._resource
        while not self._stop.is_set():
            try:
                if hasattr(resource, "event_wait"):
                    if not resource.event_wait(sec=1):
                        continue
                    resource.event_read()
                else:
                    if not resource.wait_edge_events(timeout=1.0):
                        continue
                    resource.read_edge_events()
                self._callback(time.time_ns())
            except (OSError, RuntimeError):
                break

    def _read_sysfs(self) -> None:
        """Read edge notifications using poll(2) on the sysfs value file."""
        poller = select.poll()
        poller.register(
            self._sysfs_fd,
            select.POLLPRI | select.POLLERR,
        )
        while not self._stop.is_set():
            if not poller.poll(1000):
                continue
            try:
                os.lseek(self._sysfs_fd, 0, os.SEEK_SET)
                value = os.read(self._sysfs_fd, 1)
            except OSError:
                break
            if value == b"1":
                self._callback(time.time_ns())


class STL50B2Lidar(Node):
    """Publish synchronized STL-50B2 packets as ``sensor_msgs/LaserScan``."""

    def __init__(self) -> None:
        """Declare parameters and start the serial and GPIO workers."""
        super().__init__("stl50b2_lidar")
        self._serial_port = self._parameter("serial_port", "/dev/ttyS2")
        self._baudrate = int(self._parameter("baudrate", 115200))
        self._frame_id = self._parameter("frame_id", "base_laser")
        self._scan_topic = self._parameter("scan_topic", "/scan")
        self._angle_increment_deg = float(
            self._parameter("angle_increment_deg", 0.1)
        )
        self._range_min = float(self._parameter("range_min_m", 0.05))
        self._range_max = float(self._parameter("range_max_m", 50.0))
        self._clockwise = bool(self._parameter("clockwise", False))
        chip = self._parameter("sync_gpiochip", "/dev/gpiochip2")
        line = int(self._parameter("sync_line_offset", 3))
        global_number = int(self._parameter("sync_global_number", 67))
        sync_fallback = bool(
            self._parameter("allow_sysfs_gpio_fallback", True)
        )

        bins = round(360.0 / self._angle_increment_deg)
        if bins < 1 or abs(bins * self._angle_increment_deg - 360.0) > 1e-6:
            raise ValueError("angle_increment_deg must divide 360 exactly")
        self._bin_count = bins
        self._angle_increment = 2.0 * 3.141592653589793 / bins
        qos = QoSProfile(
            depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
        )
        self._publisher = self.create_publisher(
            LaserScan, self._scan_topic, qos
        )

        self._parser = STL50B2StreamParser()
        self._assembler = SynchronizedScanAssembler()
        self._events = queue.Queue()
        self._stop = threading.Event()
        self._serial_thread = threading.Thread(
            target=self._serial_worker,
            name="stl50b2-serial",
            daemon=True,
        )
        self._sync = GpioSyncReader(
            chip,
            line,
            global_number,
            lambda stamp: self._events.put((stamp, 0, "sync", None)),
            sync_fallback,
        )
        self._last_sync_ns: Optional[int] = None
        self._sync.start()
        self._serial_thread.start()
        self._timer = self.create_timer(0.005, self._process_events)
        self.get_logger().info(
            "STL-50B2 on %s at %d baud; UART2 pins 8/10, sync pin 12",
            self._serial_port,
            self._baudrate,
        )

    def _parameter(self, name: str, default):
        """Declare and retrieve a ROS parameter."""
        return self.declare_parameter(name, default).value

    def _serial_worker(self) -> None:
        """Read and parse the UART with reconnect support."""
        while not self._stop.is_set():
            port = None
            try:
                port = serial.Serial(
                    self._serial_port,
                    self._baudrate,
                    timeout=0.2,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                )
                self.get_logger().info("STL-50B2 serial opened")
                while not self._stop.is_set():
                    data = port.read(4096)
                    if not data:
                        continue
                    received_ns = time.time_ns()
                    for packet in self._parser.feed(data):
                        self._events.put((received_ns, 1, "packet", packet))
            except (OSError, serial.SerialException) as error:
                self.get_logger().warn(
                    f"STL-50B2 serial unavailable: {error}"
                )
                self._stop.wait(2.0)
            finally:
                if port is not None:
                    port.close()

    def _process_events(self) -> None:
        """Apply GPIO and serial events in hardware-time order."""
        pending = []
        while True:
            try:
                pending.append(self._events.get_nowait())
            except queue.Empty:
                break
        for _stamp, _order, kind, payload in sorted(
            pending, key=lambda event: (event[0], event[1])
        ):
            if kind == "sync":
                scan = self._assembler.sync_edge(_stamp)
                self._last_sync_ns = _stamp
                if scan is not None:
                    self._publish_scan(scan)
            else:
                self._assembler.add_packet(payload)

    def _publish_scan(self, scan: SynchronizedScan) -> None:
        """Convert one synchronized revolution into a ROS LaserScan."""
        message = LaserScan()
        message.header.frame_id = self._frame_id
        message.header.stamp = self._time_message(scan.stamp_ns)
        message.angle_min = -3.141592653589793
        message.angle_max = 3.141592653589793 - self._angle_increment
        message.angle_increment = self._angle_increment
        message.time_increment = 0.0
        if self._last_sync_ns is None:
            message.scan_time = 0.0
        else:
            message.scan_time = max(
                0.0, (self._last_sync_ns - scan.stamp_ns) / 1e9
            )
        message.range_min = self._range_min
        message.range_max = self._range_max
        message.ranges = [float("inf")] * self._bin_count
        message.intensities = [0.0] * self._bin_count
        for point in scan.points:
            angle = point.angle_deg
            if self._clockwise:
                angle = (360.0 - angle) % 360.0
            index = int(((angle + 180.0) % 360.0) / self._angle_increment_deg)
            if index >= self._bin_count:
                continue
            distance = point.distance_mm / 1000.0
            if not self._range_min <= distance <= self._range_max:
                continue
            if message.ranges[index] == float("inf"):
                message.ranges[index] = distance
                message.intensities[index] = float(point.intensity)
            elif distance < message.ranges[index]:
                message.ranges[index] = distance
                message.intensities[index] = float(point.intensity)
        self._publisher.publish(message)

    @staticmethod
    def _time_message(stamp_ns: int):
        """Convert Unix nanoseconds to ``builtin_interfaces/Time``."""
        from builtin_interfaces.msg import Time

        message = Time()
        message.sec = stamp_ns // 1_000_000_000
        message.nanosec = stamp_ns % 1_000_000_000
        return message

    def destroy_node(self):
        """Stop hardware workers before destroying the ROS node."""
        self._stop.set()
        self._sync.stop()
        if self._serial_thread.is_alive():
            self._serial_thread.join(timeout=1.0)
        super().destroy_node()


def main(args=None) -> None:
    """Run the STL-50B2 ROS 2 driver."""
    rclpy.init(args=args)
    node = None
    try:
        node = STL50B2Lidar()
        rclpy.spin(node)
    except (RuntimeError, ValueError) as error:
        if node is not None:
            node.get_logger().error(str(error))
        else:
            print(f"stl50b2_lidar: {error}")
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()
