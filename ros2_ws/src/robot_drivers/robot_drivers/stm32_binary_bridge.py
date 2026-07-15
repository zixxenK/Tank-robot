#!/usr/bin/env python3
"""stm32_binary_bridge.py - /cmd_vel to STM32 binary frame bridge.

Binary frame format:
  0xAA 0x55 [function_code] [payload_len] [payload...] [crc8]

CRC profile: CRC-8-CCITT (poly 0x07, init 0x00)
"""

import math
import struct
import time
from typing import List, Tuple

import rclpy
import serial
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Bool
from std_msgs.msg import Empty

try:
    from ros_robot_controller_msgs.msg import (
        BuzzerState,
        LedState,
        MotorsState,
        SetBusServoState,
        SetPWMServoState,
    )
    HAS_VENDOR_MSGS = True
except ImportError:
    MotorsState = None
    LedState = None
    BuzzerState = None
    SetPWMServoState = None
    SetBusServoState = None
    HAS_VENDOR_MSGS = False

SYNC_1 = 0xAA
SYNC_2 = 0x55
FUNC_SYS = 0x00
FUNC_LED = 0x01
FUNC_BUZZER = 0x02
FUNC_MOTOR = 0x03
FUNC_PWM_SERVO = 0x04
FUNC_BUS_SERVO = 0x05
FUNC_HEARTBEAT = 0xF0
FUNC_SELF_TEST = 0xF1
SELF_TEST_STATUS_STARTED = 0xA1
SELF_TEST_STATUS_FINISHED = 0xA2
FUNC_EMERGENCY_STOP = 0x11
MOTOR_SUBCMD_SET_SPEED = 0x01
PWM_SERVO_SUBCMD_SET_POSITION = 0x01
PWM_SERVO_SUBCMD_SET_OFFSET = 0x07
BUS_SERVO_SUBCMD_STOP = 0x03
BUS_SERVO_SUBCMD_SET_POSITION = 0x01
BUS_SERVO_SUBCMD_ENABLE_TORQUE = 0x0B
BUS_SERVO_SUBCMD_DISABLE_TORQUE = 0x0C
BUS_SERVO_SUBCMD_SET_ID = 0x10
BUS_SERVO_SUBCMD_SET_OFFSET = 0x20
BUS_SERVO_SUBCMD_SAVE_OFFSET = 0x24
BUS_SERVO_SUBCMD_SET_ANGLE_LIMIT = 0x30
BUS_SERVO_SUBCMD_SET_VIN_LIMIT = 0x34
BUS_SERVO_SUBCMD_SET_TEMP_LIMIT = 0x38

CRC8_TABLE = [
    0, 94, 188, 226, 97, 63, 221, 131, 194, 156, 126, 32, 163, 253, 31, 65,
    157, 195, 33, 127, 252, 162, 64, 30, 95, 1, 227, 189, 62, 96, 130, 220,
    35, 125, 159, 193, 66, 28, 254, 160, 225, 191, 93, 3, 128, 222, 60, 98,
    190, 224, 2, 92, 223, 129, 99, 61, 124, 34, 192, 158, 29, 67, 161, 255,
    70, 24, 250, 164, 39, 121, 155, 197, 132, 218, 56, 102, 229, 187, 89, 7,
    219, 133, 103, 57, 186, 228, 6, 88, 25, 71, 165, 251, 120, 38, 196, 154,
    101, 59, 217, 135, 4, 90, 184, 230, 167, 249, 27, 69, 198, 152, 122, 36,
    248, 166, 68, 26, 153, 199, 37, 123, 58, 100, 134, 216, 91, 5, 231, 185,
    140, 210, 48, 110, 237, 179, 81, 15, 78, 16, 242, 172, 47, 113, 147, 205,
    17, 79, 173, 243, 112, 46, 204, 146, 211, 141, 111, 49, 178, 236, 14, 80,
    175, 241, 19, 77, 206, 144, 114, 44, 109, 51, 209, 143, 12, 82, 176, 238,
    50, 108, 142, 208, 83, 13, 239, 177, 240, 174, 76, 18, 145, 207, 45, 115,
    202, 148, 118, 40, 171, 245, 23, 73, 8, 86, 180, 234, 105, 55, 213, 139,
    87, 9, 235, 181, 54, 104, 138, 212, 149, 203, 41, 119, 244, 170, 72, 22,
    233, 183, 85, 11, 136, 214, 52, 106, 43, 117, 151, 201, 74, 20, 246, 168,
    116, 42, 200, 150, 21, 75, 169, 247, 182, 232, 10, 84, 215, 137, 107, 53,
]


def _clamp_u8(value: int) -> int:
    return max(0, min(255, int(value)))


def _clamp_u16(value: int) -> int:
    return max(0, min(65535, int(value)))


def _clamp_i8(value: int) -> int:
    return max(-128, min(127, int(value)))


def crc8_ccitt(data: bytes) -> int:
    crc = 0x00
    for byte in data:
        crc = CRC8_TABLE[crc ^ byte]
    return crc


def build_frame(function_code: int, payload: bytes = b"") -> bytes:
    body = bytes([function_code, len(payload)]) + payload
    crc = crc8_ccitt(body)
    return bytes([SYNC_1, SYNC_2]) + body + bytes([crc])


class STM32BinaryBridge(Node):
    """Bridge /cmd_vel to STM32 binary UART protocol."""

    def __init__(self):
        super().__init__("stm32_binary_bridge")

        self.declare_parameter("serial_port", "/dev/rock64_stm32")
        self.declare_parameter("baud_rate", 115200)
        self.declare_parameter("max_speed", 255)
        self.declare_parameter("command_rate_hz", 50.0)
        self.declare_parameter("cmd_timeout", 0.25)
        self.declare_parameter("linear_slew_rate", 3.0)
        self.declare_parameter("angular_slew_rate", 6.0)
        self.declare_parameter("heartbeat_interval", 0.1)
        self.declare_parameter("self_test_ack_timeout", 10.0)

        port = self.get_parameter("serial_port").value
        baud = self.get_parameter("baud_rate").value
        self._max_speed = int(self.get_parameter("max_speed").value)
        self._cmd_timeout = float(self.get_parameter("cmd_timeout").value)
        self._linear_slew_rate = float(
            self.get_parameter("linear_slew_rate").value
        )
        self._angular_slew_rate = float(
            self.get_parameter("angular_slew_rate").value
        )
        command_rate_hz = float(self.get_parameter("command_rate_hz").value)
        heartbeat_interval = float(
            self.get_parameter("heartbeat_interval").value
        )
        self._self_test_ack_timeout = float(
            self.get_parameter("self_test_ack_timeout").value
        )

        self._target_lin = 0.0
        self._target_ang = 0.0
        self._vendor_motor_entries = []
        self._vendor_motor_timestamp = 0.0
        self._cmd_lin = 0.0
        self._cmd_ang = 0.0
        self._last_cmd_vel_time = time.time()
        self._last_send_time = time.time()
        self._last_sent_pair = (None, None)

        try:
            self._ser = serial.Serial(port, baud, timeout=0.1)
            self.get_logger().info(
                f"Binary bridge open on {port} @ {baud} baud"
            )
        except serial.SerialException as exc:
            self.get_logger().error(f"Cannot open {port}: {exc}")
            self._ser = None

        self._sub = self.create_subscription(
            Twist,
            "/cmd_vel",
            self._cmd_vel_cb,
            10,
        )

        self._self_test_sub = self.create_subscription(
            Empty,
            "/stm32/self_test",
            self._self_test_cb,
            10,
        )
        self._self_test_result_pub = self.create_publisher(
            Bool,
            "/stm32/self_test_result",
            10,
        )

        if HAS_VENDOR_MSGS:
            self._vendor_motor_sub = self.create_subscription(
                MotorsState,
                "/set_motor",
                self._vendor_motor_cb,
                10,
            )
            self._led_sub = self.create_subscription(
                LedState,
                "/set_led",
                self._vendor_led_cb,
                10,
            )
            self._buzzer_sub = self.create_subscription(
                BuzzerState,
                "/set_buzzer",
                self._vendor_buzzer_cb,
                10,
            )
            self._pwm_servo_sub = self.create_subscription(
                SetPWMServoState,
                "/pwm_servo/set_state",
                self._vendor_pwm_servo_cb,
                10,
            )
            self._bus_servo_sub = self.create_subscription(
                SetBusServoState,
                "/bus_servo/set_state",
                self._vendor_bus_servo_cb,
                10,
            )
            self.get_logger().info(
                "Vendor message bridge enabled "
                "(/set_motor, /set_led, /set_buzzer, "
                "/pwm_servo/set_state, /bus_servo/set_state)"
            )
        else:
            self.get_logger().warn(
                "ros_robot_controller_msgs not available; "
                "vendor topics disabled"
            )

        period = 1.0 / max(command_rate_hz, 1.0)
        self._drive_timer = self.create_timer(period, self._drive_loop)
        self._heartbeat_timer = self.create_timer(
            heartbeat_interval,
            self._send_heartbeat,
        )

    def _cmd_vel_cb(self, msg: Twist):
        self._target_lin = float(msg.linear.x)
        self._target_ang = float(msg.angular.z)
        self._last_cmd_vel_time = time.time()

    def _vendor_motor_cb(self, msg):
        entries = []
        for item in msg.data:
            motor_id = int(item.id)
            if motor_id > 0:
                motor_id -= 1
            if motor_id < 0:
                motor_id = 0
            if motor_id > 255:
                motor_id = 255

            rps = float(item.rps)
            if rps > 1.0:
                rps = 1.0
            if rps < -1.0:
                rps = -1.0
            entries.append((motor_id, rps))

        self._vendor_motor_entries = entries
        self._vendor_motor_timestamp = time.time()

    def _vendor_led_cb(self, msg):
        led_id = _clamp_u8(getattr(msg, "id", 0))
        on_ms = _clamp_u16(round(float(getattr(msg, "on_time", 0.0)) * 1000.0))
        off_ms = _clamp_u16(
            round(float(getattr(msg, "off_time", 0.0)) * 1000.0)
        )
        repeat = _clamp_u16(getattr(msg, "repeat", 1))
        payload = struct.pack("<BHHH", led_id, on_ms, off_ms, repeat)
        self._send_frame(FUNC_LED, payload)

    def _vendor_buzzer_cb(self, msg):
        freq = _clamp_u16(getattr(msg, "freq", 0))
        on_ms = _clamp_u16(round(float(getattr(msg, "on_time", 0.0)) * 1000.0))
        off_ms = _clamp_u16(
            round(float(getattr(msg, "off_time", 0.0)) * 1000.0)
        )
        repeat = _clamp_u16(getattr(msg, "repeat", 1))
        payload = struct.pack("<HHHH", freq, on_ms, off_ms, repeat)
        self._send_frame(FUNC_BUZZER, payload)

    def _vendor_pwm_servo_cb(self, msg):
        states = list(getattr(msg, "state", []))
        duration_ms = _clamp_u16(
            round(float(getattr(msg, "duration", 0.0)) * 1000.0)
        )
        set_positions: List[Tuple[int, int]] = []

        for item in states:
            ids = list(getattr(item, "id", []))
            positions = list(getattr(item, "position", []))
            offsets = list(getattr(item, "offset", []))

            if ids and positions:
                set_positions.append(
                    (_clamp_u8(ids[0]), _clamp_u16(positions[0]))
                )
            if ids and offsets:
                payload = struct.pack(
                    "<BBb",
                    PWM_SERVO_SUBCMD_SET_OFFSET,
                    _clamp_u8(ids[0]),
                    _clamp_i8(offsets[0]),
                )
                self._send_frame(FUNC_PWM_SERVO, payload)

        if set_positions:
            payload = bytearray()
            payload.append(PWM_SERVO_SUBCMD_SET_POSITION)
            payload.append(duration_ms & 0xFF)
            payload.append((duration_ms >> 8) & 0xFF)
            payload.append(_clamp_u8(len(set_positions)))
            for servo_id, position in set_positions:
                payload.extend(struct.pack("<BH", servo_id, position))
            self._send_frame(FUNC_PWM_SERVO, bytes(payload))

    def _vendor_bus_servo_cb(self, msg):
        states = list(getattr(msg, "state", []))
        duration_ms = _clamp_u16(
            round(float(getattr(msg, "duration", 0.0)) * 1000.0)
        )
        set_positions: List[Tuple[int, int]] = []
        stop_ids: List[int] = []

        for item in states:
            present_id = list(getattr(item, "present_id", []))
            target_id = list(getattr(item, "target_id", []))
            position = list(getattr(item, "position", []))
            offset = list(getattr(item, "offset", []))
            position_limit = list(getattr(item, "position_limit", []))
            voltage_limit = list(getattr(item, "voltage_limit", []))
            max_temperature_limit = list(
                getattr(item, "max_temperature_limit", [])
            )
            enable_torque = list(getattr(item, "enable_torque", []))
            save_offset = list(getattr(item, "save_offset", []))
            stop = list(getattr(item, "stop", []))

            if len(present_id) < 2 or not present_id[0]:
                continue

            servo_id = _clamp_u8(present_id[1])

            if len(target_id) >= 2 and target_id[0]:
                payload = struct.pack(
                    "<BBB",
                    BUS_SERVO_SUBCMD_SET_ID,
                    servo_id,
                    _clamp_u8(target_id[1]),
                )
                self._send_frame(FUNC_BUS_SERVO, payload)

            if len(position) >= 2 and position[0]:
                set_positions.append((servo_id, _clamp_u16(position[1])))

            if len(offset) >= 2 and offset[0]:
                payload = struct.pack(
                    "<BBb",
                    BUS_SERVO_SUBCMD_SET_OFFSET,
                    servo_id,
                    _clamp_i8(offset[1]),
                )
                self._send_frame(FUNC_BUS_SERVO, payload)

            if len(position_limit) >= 3 and position_limit[0]:
                payload = struct.pack(
                    "<BBHH",
                    BUS_SERVO_SUBCMD_SET_ANGLE_LIMIT,
                    servo_id,
                    _clamp_u16(position_limit[1]),
                    _clamp_u16(position_limit[2]),
                )
                self._send_frame(FUNC_BUS_SERVO, payload)

            if len(voltage_limit) >= 3 and voltage_limit[0]:
                payload = struct.pack(
                    "<BBHH",
                    BUS_SERVO_SUBCMD_SET_VIN_LIMIT,
                    servo_id,
                    _clamp_u16(voltage_limit[1]),
                    _clamp_u16(voltage_limit[2]),
                )
                self._send_frame(FUNC_BUS_SERVO, payload)

            if len(max_temperature_limit) >= 2 and max_temperature_limit[0]:
                payload = struct.pack(
                    "<BBb",
                    BUS_SERVO_SUBCMD_SET_TEMP_LIMIT,
                    servo_id,
                    _clamp_i8(max_temperature_limit[1]),
                )
                self._send_frame(FUNC_BUS_SERVO, payload)

            if len(enable_torque) >= 2 and enable_torque[0]:
                torque_cmd = (
                    BUS_SERVO_SUBCMD_ENABLE_TORQUE
                    if bool(enable_torque[1])
                    else BUS_SERVO_SUBCMD_DISABLE_TORQUE
                )
                payload = struct.pack("<BB", torque_cmd, servo_id)
                self._send_frame(FUNC_BUS_SERVO, payload)

            if len(save_offset) >= 1 and save_offset[0]:
                payload = struct.pack(
                    "<BB", BUS_SERVO_SUBCMD_SAVE_OFFSET, servo_id
                )
                self._send_frame(FUNC_BUS_SERVO, payload)

            if len(stop) >= 1 and stop[0]:
                stop_ids.append(servo_id)

        if set_positions:
            payload = bytearray()
            payload.append(BUS_SERVO_SUBCMD_SET_POSITION)
            payload.append(duration_ms & 0xFF)
            payload.append((duration_ms >> 8) & 0xFF)
            payload.append(_clamp_u8(len(set_positions)))
            for servo_id, target_position in set_positions:
                payload.extend(struct.pack("<BH", servo_id, target_position))
            self._send_frame(FUNC_BUS_SERVO, bytes(payload))

        if stop_ids:
            payload = bytearray()
            payload.append(BUS_SERVO_SUBCMD_STOP)
            payload.append(_clamp_u8(len(stop_ids)))
            payload.extend(stop_ids)
            self._send_frame(FUNC_BUS_SERVO, bytes(payload))

    def _slew(
        self,
        current: float,
        target: float,
        rate: float,
        dt: float,
    ) -> float:
        max_step = max(rate, 0.0) * max(dt, 0.0)
        delta = target - current
        if abs(delta) <= max_step:
            return target
        return current + math.copysign(max_step, delta)

    def _send_frame(self, function_code: int, payload: bytes = b""):
        if self._ser is None or not self._ser.is_open:
            return
        frame = build_frame(function_code, payload)
        try:
            self._ser.write(frame)
        except serial.SerialException as exc:
            self.get_logger().warn(f"Serial write failed: {exc}")

    def _send_heartbeat(self):
        self._send_frame(FUNC_HEARTBEAT)

    def _read_frame(self, timeout_s: float):
        if self._ser is None or not self._ser.is_open:
            return None

        deadline = time.monotonic() + max(timeout_s, 0.0)
        prev_timeout = self._ser.timeout

        try:
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                self._ser.timeout = max(0.01, min(0.1, remaining))

                sync1 = self._ser.read(1)
                if not sync1:
                    continue
                if sync1[0] != SYNC_1:
                    continue

                sync2 = self._ser.read(1)
                if not sync2:
                    continue
                if sync2[0] != SYNC_2:
                    continue

                header = self._ser.read(2)
                if len(header) != 2:
                    continue

                function_code = header[0]
                payload_len = header[1]
                payload = self._ser.read(payload_len)
                if len(payload) != payload_len:
                    continue

                crc = self._ser.read(1)
                if len(crc) != 1:
                    continue

                body = bytes([function_code, payload_len]) + payload
                if crc8_ccitt(body) != crc[0]:
                    continue

                return function_code, payload
        except serial.SerialException as exc:
            self.get_logger().warn(f"Serial read failed: {exc}")
            return None
        finally:
            self._ser.timeout = prev_timeout

        return None

    def _wait_for_self_test_status(self, status: int, deadline: float) -> bool:
        while time.monotonic() < deadline:
            frame = self._read_frame(deadline - time.monotonic())
            if frame is None:
                continue

            function_code, payload = frame
            if function_code != FUNC_SELF_TEST or len(payload) != 1:
                continue

            if payload[0] == status:
                return True

        return False

    def _self_test_cb(self, _msg: Empty):
        self.get_logger().warn(
            "Requesting firmware motor self-test. Keep robot lifted."
        )
        self._send_frame(FUNC_SELF_TEST)

        deadline = time.monotonic() + max(self._self_test_ack_timeout, 0.1)
        started = self._wait_for_self_test_status(
            SELF_TEST_STATUS_STARTED,
            deadline,
        )
        if not started:
            self.get_logger().warn("Timed out waiting for self-test start ack")
            self._self_test_result_pub.publish(Bool(data=False))
            return

        self.get_logger().info("Firmware self-test started")
        finished = self._wait_for_self_test_status(
            SELF_TEST_STATUS_FINISHED,
            deadline,
        )
        if not finished:
            self.get_logger().warn(
                "Timed out waiting for self-test finish ack"
            )
            self._self_test_result_pub.publish(Bool(data=False))
            return

        self.get_logger().info("Firmware self-test finished")
        self._self_test_result_pub.publish(Bool(data=True))

    def _drive_loop(self):
        if self._ser is None or not self._ser.is_open:
            return

        now = time.time()

        # Prefer direct vendor motor commands if present and fresh.
        if (
            self._vendor_motor_entries
            and (now - self._vendor_motor_timestamp) <= self._cmd_timeout
        ):
            payload = bytearray()
            payload.append(MOTOR_SUBCMD_SET_SPEED)
            payload.append(len(self._vendor_motor_entries))
            for motor_id, rps in self._vendor_motor_entries:
                payload.extend(struct.pack("<Bf", motor_id, rps))
            self._send_frame(FUNC_MOTOR, bytes(payload))
            return

        dt = now - self._last_send_time
        self._last_send_time = now

        stale = (now - self._last_cmd_vel_time) > self._cmd_timeout
        target_lin = 0.0 if stale else self._target_lin
        target_ang = 0.0 if stale else self._target_ang

        self._cmd_lin = self._slew(
            self._cmd_lin, target_lin, self._linear_slew_rate, dt
        )
        self._cmd_ang = self._slew(
            self._cmd_ang, target_ang, self._angular_slew_rate, dt
        )

        left_vel = self._cmd_lin - self._cmd_ang
        right_vel = self._cmd_lin + self._cmd_ang
        max_mag = max(1.0, abs(left_vel), abs(right_vel))
        left_vel /= max_mag
        right_vel /= max_mag

        left_speed = int(
            max(
                -self._max_speed,
                min(self._max_speed, left_vel * self._max_speed),
            )
        )
        right_speed = int(
            max(
                -self._max_speed,
                min(self._max_speed, right_vel * self._max_speed),
            )
        )

        if (left_speed, right_speed) == self._last_sent_pair and not stale:
            return

        left_rps = float(left_speed) / float(self._max_speed)
        right_rps = float(right_speed) / float(self._max_speed)
        payload = bytearray()
        payload.append(MOTOR_SUBCMD_SET_SPEED)
        payload.append(2)
        payload.extend(struct.pack("<Bf", 0, left_rps))
        payload.extend(struct.pack("<Bf", 1, right_rps))
        self._send_frame(FUNC_MOTOR, bytes(payload))
        self._last_sent_pair = (left_speed, right_speed)

    def destroy_node(self):
        self._send_frame(FUNC_EMERGENCY_STOP)
        if self._ser and self._ser.is_open:
            self._ser.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = STM32BinaryBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
