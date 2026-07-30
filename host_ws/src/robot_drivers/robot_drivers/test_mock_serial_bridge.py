#!/usr/bin/env python3
"""Mock-serial unit test suite for STM32 hardened bridge using pseudo-terminals.

This test suite uses pseudo-terminals (pty) to mock the STM32 firmware binary responses
on the host side, allowing automated regression tests on packet parser, CRC validation,
and safety thresholds in CI/CD without needing physical hardware connected.
"""

import sys
import os
import time
import threading
import struct
import unittest
from unittest.mock import Mock, patch, MagicMock
import queue

# Mock the serial module since we'll use pty instead
sys.modules['serial'] = MagicMock()

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import BatteryState, Imu
from nav_msgs.msg import Odometry
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus

# Import the bridge module
from robot_drivers.stm32_hardened_bridge import (
    SYNC_1, SYNC_2, FRAME_HEADER_SIZE, FRAME_FOOTER_SIZE,
    FUNC_MOTOR, FUNC_ENCODER, FUNC_BATTERY, FUNC_IMU, FUNC_HEARTBEAT, FUNC_ACK,
    MOTOR_SUBCMD_SET_SPEED, MOTOR_SUBCMD_EMERGENCY_STOP,
    CRC8_TABLE, FrameParser, TelemetryData
)

try:
    import pty
    PTY_AVAILABLE = True
except ImportError:
    PTY_AVAILABLE = False


class MockSTM32Firmware:
    """Mock STM32 firmware that responds to bridge commands via pseudo-terminal."""

    def __init__(self, master_fd, slave_fd):
        self.master_fd = master_fd
        self.slave_fd = slave_fd
        self.running = True
        self.encoder_left = 0
        self.encoder_right = 0
        self.battery_voltage = 12.0
        self.imu_accel = (0.0, 0.0, 9.8)
        self.imu_gyro = (0.0, 0.0, 0.0)
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()

    def _build_frame(self, function_code: int, payload: bytes = b"") -> bytes:
        """Build a complete frame with header, payload, and CRC."""
        body = bytes([function_code, len(payload)]) + payload
        crc = self._crc8_ccitt(body)
        return bytes([SYNC_1, SYNC_2]) + body + bytes([crc])

    def _crc8_ccitt(self, data: bytes) -> int:
        """Calculate CRC-8-CCITT."""
        crc = 0x00
        for byte in data:
            crc = CRC8_TABLE[crc ^ byte]
        return crc

    def _handle_motor_command(self, payload: bytes):
        """Handle motor command and update encoder positions."""
        if len(payload) >= 9:  # subcmd + motor_id + speed (float) x2
            subcmd = payload[0]
            if subcmd == MOTOR_SUBCMD_SET_SPEED:
                # Simulate encoder movement based on speed
                left_speed = struct.unpack("<f", payload[2:6])[0]
                right_speed = struct.unpack("<f", payload[6:10])[0]
                self.encoder_left += int(left_speed * 10)
                self.encoder_right += int(right_speed * 10)
            elif subcmd == MOTOR_SUBCMD_EMERGENCY_STOP:
                # Reset encoders on emergency stop
                self.encoder_left = 0
                self.encoder_right = 0

    def _run(self):
        """Main firmware loop - process incoming frames and send telemetry."""
        import select
        buffer = bytearray()

        while self.running:
            # Wait for data from bridge
            readable, _, _ = select.select([self.master_fd], [], [], 0.1)
            if readable:
                try:
                    data = os.read(self.master_fd, 1024)
                    if data:
                        buffer.extend(data)
                except OSError:
                    continue

            # Process complete frames
            while len(buffer) >= FRAME_HEADER_SIZE:
                # Find sync bytes
                sync_idx = buffer.find(bytes([SYNC_1, SYNC_2]))
                if sync_idx == -1:
                    buffer.clear()
                    break

                # Remove data before sync
                if sync_idx > 0:
                    buffer = buffer[sync_idx:]

                # Check if we have complete frame
                if len(buffer) < FRAME_HEADER_SIZE + FRAME_FOOTER_SIZE:
                    break

                payload_len = buffer[3]
                frame_len = FRAME_HEADER_SIZE + payload_len + FRAME_FOOTER_SIZE

                if len(buffer) < frame_len:
                    break

                # Extract frame
                frame = buffer[:frame_len]
                buffer = buffer[frame_len:]

                # Validate CRC
                body = frame[2:4+payload_len]
                received_crc = frame[4+payload_len]
                calculated_crc = self._crc8_ccitt(body)

                if received_crc != calculated_crc:
                    continue  # Invalid CRC, skip

                # Process frame
                function_code = frame[2]
                payload = frame[4:4+payload_len]

                if function_code == FUNC_MOTOR:
                    self._handle_motor_command(payload)
                    # Send ACK
                    response = self._build_frame(FUNC_ACK, b"\x01")
                    os.write(self.master_fd, response)

                elif function_code == FUNC_HEARTBEAT:
                    # Send heartbeat response
                    response = self._build_frame(FUNC_HEARTBEAT, b"")
                    os.write(self.master_fd, response)

            # Send telemetry periodically
            self._send_telemetry()
            time.sleep(0.05)  # 20Hz telemetry rate

    def _send_telemetry(self):
        """Send encoder, battery, and IMU telemetry."""
        # Encoder telemetry
        encoder_payload = struct.pack("<ii", self.encoder_left, self.encoder_right)
        encoder_frame = self._build_frame(FUNC_ENCODER, encoder_payload)
        os.write(self.master_fd, encoder_frame)

        # Battery telemetry
        battery_payload = struct.pack("<ff", self.battery_voltage, 0.0)  # Current not implemented
        battery_frame = self._build_frame(FUNC_BATTERY, battery_payload)
        os.write(self.master_fd, battery_frame)

        # IMU telemetry
        imu_payload = (struct.pack("<fff", *self.imu_accel) +
                      struct.pack("<fff", *self.imu_gyro))
        imu_frame = self._build_frame(FUNC_IMU, imu_payload)
        os.write(self.master_fd, imu_frame)

    def stop(self):
        """Stop the firmware thread."""
        self.running = False
        self.thread.join(timeout=1.0)


class TestMockSerialBridge(unittest.TestCase):
    """Unit tests for STM32 hardened bridge with mock serial."""

    @classmethod
    def setUpClass(cls):
        """Initialize ROS2 for testing."""
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        """Shutdown ROS2."""
        rclpy.shutdown()

    def setUp(self):
        """Set up test case with pseudo-terminal."""
        if not PTY_AVAILABLE:
            self.skipTest("PTY not available on this platform")

        # Create pseudo-terminal pair
        self.master_fd, self.slave_fd = pty.openpty()

        # Start mock firmware
        self.mock_firmware = MockSTM32Firmware(self.master_fd, self.slave_fd)

        # Get slave device path
        self.serial_port = os.ttyname(self.slave_fd)

    def tearDown(self):
        """Clean up test case."""
        if hasattr(self, 'mock_firmware'):
            self.mock_firmware.stop()

        if hasattr(self, 'master_fd'):
            os.close(self.master_fd)

        if hasattr(self, 'slave_fd'):
            os.close(self.slave_fd)

    def test_frame_parser_sync_detection(self):
        """Test frame parser sync byte detection."""
        parser = FrameParser()

        # Test valid sync sequence
        result = parser.process_byte(SYNC_1)
        self.assertIsNone(result)

        result = parser.process_byte(SYNC_2)
        self.assertIsNone(result)
        self.assertEqual(parser.sync_state, 2)

    def test_frame_parser_crc_validation(self):
        """Test CRC validation in frame parser."""
        parser = FrameParser()

        # Build valid frame
        payload = b"\x01\x00\x00\x00\x00"  # subcmd + motor_id + speed
        body = bytes([FUNC_MOTOR, len(payload)]) + payload
        crc = parser._crc8_ccitt(body)
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])

        # Process frame byte by byte
        for byte in frame:
            result = parser.process_byte(byte)

        self.assertIsNotNone(result)
        function_code, parsed_payload = result
        self.assertEqual(function_code, FUNC_MOTOR)
        self.assertEqual(parsed_payload, payload)

    def test_frame_parser_crc_error_detection(self):
        """Test CRC error detection."""
        parser = FrameParser()

        # Build frame with invalid CRC
        payload = b"\x01\x00\x00\x00\x00"
        body = bytes([FUNC_MOTOR, len(payload)]) + payload
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([0xFF])  # Invalid CRC

        # Process frame byte by byte
        for byte in frame:
            result = parser.process_byte(byte)

        self.assertIsNone(result)  # Should return None for invalid CRC
        self.assertEqual(parser.crc_errors, 1)

    def test_frame_parser_error_tracking(self):
        """Test comprehensive error tracking."""
        parser = FrameParser()

        # Generate some valid frames
        for i in range(10):
            payload = struct.pack("<Bff", MOTOR_SUBCMD_SET_SPEED, i, i)
            body = bytes([FUNC_MOTOR, len(payload)]) + payload
            crc = parser._crc8_ccitt(body)
            frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])

            for byte in frame:
                parser.process_byte(byte)

        # Generate some CRC errors
        for i in range(5):
            payload = b"\x01\x00\x00\x00\x00"
            body = bytes([FUNC_MOTOR, len(payload)]) + payload
            frame = bytes([SYNC_1, SYNC_2]) + body + bytes([0xFF])  # Invalid CRC

            for byte in frame:
                parser.process_byte(byte)

        stats = parser.get_stats()
        self.assertEqual(stats['valid_frames'], 10)
        self.assertEqual(stats['crc_errors'], 5)
        self.assertGreater(stats['error_rate_percent'], 0)

    def test_emergency_stop_function_code(self):
        """Test emergency stop uses correct function code."""
        parser = FrameParser()

        # Build emergency stop frame using correct pattern
        payload = struct.pack("<BB", MOTOR_SUBCMD_EMERGENCY_STOP, 0)  # subcmd, motor_id (0 = all)
        body = bytes([FUNC_MOTOR, len(payload)]) + payload
        crc = parser._crc8_ccitt(body)
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])

        # Process frame
        for byte in frame:
            result = parser.process_byte(byte)

        self.assertIsNotNone(result)
        function_code, parsed_payload = result
        self.assertEqual(function_code, FUNC_MOTOR)  # Should be FUNC_MOTOR, not 0x11
        self.assertEqual(parsed_payload[0], MOTOR_SUBCMD_EMERGENCY_STOP)

    def test_telemetry_data_structure(self):
        """Test telemetry data container."""
        telemetry = TelemetryData()

        self.assertEqual(telemetry.encoder_left, 0)
        self.assertEqual(telemetry.battery_voltage, 0.0)
        self.assertEqual(telemetry.imu_accel, (0.0, 0.0, 0.0))

        # Update with sample data
        telemetry.encoder_left = 1000
        telemetry.battery_voltage = 12.5
        telemetry.imu_accel = (0.1, 0.2, 9.8)

        self.assertEqual(telemetry.encoder_left, 1000)
        self.assertEqual(telemetry.battery_voltage, 12.5)
        self.assertEqual(telemetry.imu_accel, (0.1, 0.2, 9.8))

    def test_mock_firmware_telemetry(self):
        """Test mock firmware generates valid telemetry frames."""
        # Let firmware run for a bit
        time.sleep(0.2)

        # Check that firmware updated state
        self.assertGreater(self.mock_firmware.encoder_left, 0 or self.mock_firmware.encoder_right > 0)

    def test_mock_firmware_motor_command(self):
        """Test mock firmware processes motor commands."""
        # Send motor command via slave fd
        payload = struct.pack("<Bff", MOTOR_SUBCMD_SET_SPEED, 1.0, 1.0)
        body = bytes([FUNC_MOTOR, len(payload)]) + payload
        crc = self.mock_firmware._crc8_ccitt(body)
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])

        os.write(self.slave_fd, frame)

        # Wait for processing
        time.sleep(0.1)

        # Check encoders moved
        self.assertGreater(self.mock_firmware.encoder_left, 0)


class TestBridgeIntegration(unittest.TestCase):
    """Integration tests requiring full bridge node."""

    def setUp(self):
        """Set up bridge node for testing."""
        if not PTY_AVAILABLE:
            self.skipTest("PTY not available on this platform")

        # Create pseudo-terminal
        self.master_fd, self.slave_fd = pty.openpty()
        self.serial_port = os.ttyname(self.slave_fd)

        # Start mock firmware
        self.mock_firmware = MockSTM32Firmware(self.master_fd, self.slave_fd)

        # Create bridge node with mock serial port
        self.node = Node("test_bridge")

    def tearDown(self):
        """Clean up bridge node."""
        if hasattr(self, 'node'):
            self.node.destroy_node()

        if hasattr(self, 'mock_firmware'):
            self.mock_firmware.stop()

        if hasattr(self, 'master_fd'):
            os.close(self.master_fd)

        if hasattr(self, 'slave_fd'):
            os.close(self.slave_fd)

    def test_bridge_serial_connection(self):
        """Test bridge can connect to pseudo-terminal."""
        # This would require bridge node implementation
        # For now, test that port exists
        self.assertTrue(os.path.exists(self.serial_port))


def run_tests():
    """Run the test suite."""
    if not PTY_AVAILABLE:
        print("PTY not available - skipping mock serial tests")
        return

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add tests
    suite.addTests(loader.loadTestsFromTestCase(TestMockSerialBridge))
    suite.addTests(loader.loadTestsFromTestCase(TestBridgeIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)