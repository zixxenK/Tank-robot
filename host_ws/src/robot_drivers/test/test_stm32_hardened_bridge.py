#!/usr/bin/env python3
"""Unit tests for STM32 Hardened Bridge components."""

import unittest
import struct
import threading

from robot_drivers.stm32_hardened_bridge import (
    CircularBuffer,
    FrameParser,
    CRC8_TABLE,
    crc8_ccitt,
    SYNC_1,
    SYNC_2,
    FUNC_MOTOR,
    FUNC_BUZZER,
    FUNC_SERVO,
    FUNC_HEARTBEAT,
    FUNC_GLOWY_ULTRASONIC,
    FUNC_IMU_DIAG,
    MOTOR_SUBCMD_SET_SPEED,
    SERVO_CHANNEL_J1,
    SERVO_SUBCMD_SET_POSITION,
    servo_angle_to_pulse_us,
    servo_pulse_to_angle_degrees,
    signed_int32_delta,
    TelemetryData,
    STM32HardenedBridge,
)


class TestCRC8(unittest.TestCase):
    """Test CRC-8-CCITT implementation."""

    def test_crc8_table(self):
        """Test CRC table is valid."""
        self.assertEqual(len(CRC8_TABLE), 256)
        # Check some known values
        self.assertEqual(CRC8_TABLE[0], 0)
        self.assertEqual(CRC8_TABLE[1], 94)

    def test_crc8_calculation(self):
        """Test CRC calculation with known values."""
        # Test empty data
        self.assertEqual(crc8_ccitt(b""), 0x00)

        # Test single byte
        self.assertEqual(crc8_ccitt(b"\x00"), 0x00)
        self.assertEqual(crc8_ccitt(b"\xff"), 0x35)

    def test_crc8_frame_validation(self):
        """Test CRC validation on complete frames."""
        # Build a simple frame
        func = FUNC_HEARTBEAT
        payload = b""
        body = bytes([func, len(payload)]) + payload
        crc = crc8_ccitt(body)

        # Rebuild and validate
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])

        # Extract and validate
        extracted_body = frame[2:4]  # func + len
        extracted_crc = frame[4]
        calculated_crc = crc8_ccitt(extracted_body)

        self.assertEqual(extracted_crc, calculated_crc)

    def test_buzzer_tone_frame_uses_protocol_extension(self):
        """A buzzer tone is encoded as subcommand + little-endian uint16 Hz."""
        payload = bytes([0x01]) + struct.pack("<H", 440)
        body = bytes([FUNC_BUZZER, len(payload)]) + payload
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc8_ccitt(body)])

        self.assertEqual(frame[2], FUNC_BUZZER)
        self.assertEqual(frame[3], 3)
        self.assertEqual(frame[4:], payload + bytes([crc8_ccitt(body)]))

    def test_servo_command_frame_and_round_trip(self):
        """J1 servo commands use the bounded packed protocol extension."""
        pulse_us = servo_angle_to_pulse_us(90.0)
        payload = bytes([SERVO_SUBCMD_SET_POSITION, SERVO_CHANNEL_J1])
        payload += struct.pack("<HH", pulse_us, 500)
        body = bytes([FUNC_SERVO, len(payload)]) + payload
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc8_ccitt(body)])

        self.assertEqual(pulse_us, 1500)
        self.assertEqual(servo_pulse_to_angle_degrees(pulse_us), 90)
        self.assertEqual(frame[2], FUNC_SERVO)
        self.assertEqual(frame[3], 6)

    def test_servo_angle_rejects_unsafe_values(self):
        """Non-finite and out-of-protocol commands are rejected."""
        for value in (-1.0, 181.0, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                servo_angle_to_pulse_us(value)

    def test_encoder_delta_handles_signed_int32_wrap(self):
        """Counter rollover must produce a small physical delta."""
        self.assertEqual(signed_int32_delta(-2147483648, 2147483647), 1)
        self.assertEqual(signed_int32_delta(2147483647, -2147483648), -1)


class TestCircularBuffer(unittest.TestCase):
    """Test circular buffer implementation."""

    def test_buffer_initialization(self):
        """Test buffer initialization."""
        buf = CircularBuffer(100)
        self.assertEqual(buf.size, 100)
        self.assertEqual(buf.available(), 0)

    def test_buffer_write_read(self):
        """Test basic write and read operations."""
        buf = CircularBuffer(10)

        # Write data
        data = b"Hello"
        written = buf.write(data)
        self.assertEqual(written, 5)
        self.assertEqual(buf.available(), 5)

        # Read data
        read_data = buf.read(5)
        self.assertEqual(read_data, data)
        self.assertEqual(buf.available(), 0)

    def test_buffer_wraparound(self):
        """Test buffer wraparound."""
        buf = CircularBuffer(10)

        # Fill buffer
        buf.write(b"0123456789")
        self.assertEqual(buf.available(), 10)

        # Read some data
        buf.read(5)
        self.assertEqual(buf.available(), 5)

        # Write more data (should wrap)
        written = buf.write(b"ABCDE")
        self.assertEqual(written, 5)
        self.assertEqual(buf.available(), 10)

        # Read all data
        read_data = buf.read(10)
        self.assertEqual(read_data, b"56789ABCDE")

    def test_buffer_overflow(self):
        """Test buffer overflow handling."""
        buf = CircularBuffer(5)

        # Try to write more than buffer size
        written = buf.write(b"0123456789")
        self.assertEqual(written, 5)  # Only 5 bytes written
        self.assertEqual(buf.available(), 5)

    def test_buffer_peek(self):
        """Test peek operation."""
        buf = CircularBuffer(10)
        buf.write(b"HelloWorld")

        # Peek should not consume data
        peeked = buf.peek(5)
        self.assertEqual(peeked, b"Hello")
        self.assertEqual(buf.available(), 10)

        # Read should consume data
        read = buf.read(5)
        self.assertEqual(read, b"Hello")
        self.assertEqual(buf.available(), 5)

    def test_buffer_clear(self):
        """Test buffer clear operation."""
        buf = CircularBuffer(10)
        buf.write(b"HelloWorld")
        self.assertEqual(buf.available(), 10)

        buf.clear()
        self.assertEqual(buf.available(), 0)

    def test_thread_safety(self):
        """Test basic thread safety (not comprehensive)."""
        import threading

        buf = CircularBuffer(1000)

        def writer():
            for i in range(100):
                buf.write(b"X" * 10)

        def reader():
            for i in range(100):
                buf.read(10)

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Should not crash
        self.assertTrue(True)


class TestFrameParser(unittest.TestCase):
    """Test frame parser implementation."""

    def test_parser_initialization(self):
        """Test parser initialization."""
        parser = FrameParser()
        stats = parser.get_stats()
        self.assertEqual(stats["valid_frames"], 0)
        self.assertEqual(stats["parse_errors"], 0)
        self.assertEqual(stats["sync_state"], 0)

    def test_sync_detection(self):
        """Test sync byte detection."""
        parser = FrameParser()

        # Send wrong byte
        result = parser.process_byte(0x00)
        self.assertIsNone(result)

        # Send first sync byte
        result = parser.process_byte(SYNC_1)
        self.assertIsNone(result)
        self.assertEqual(parser.get_stats()["sync_state"], 1)

        # Send second sync byte
        result = parser.process_byte(SYNC_2)
        self.assertIsNone(result)
        self.assertEqual(parser.get_stats()["sync_state"], 2)

    def test_heartbeat_frame(self):
        """Test heartbeat frame parsing."""
        parser = FrameParser()

        # Build heartbeat frame: 0xAA 0x55 0xF0 0x00 [CRC]
        func = FUNC_HEARTBEAT
        payload = b""
        body = bytes([func, len(payload)]) + payload
        crc = crc8_ccitt(body)
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])

        # Process frame byte by byte
        for byte in frame:
            result = parser.process_byte(byte)

        # Should return the frame
        self.assertIsNotNone(result)
        func_code, parsed_payload = result
        self.assertEqual(func_code, FUNC_HEARTBEAT)
        self.assertEqual(parsed_payload, b"")

        # Check stats
        stats = parser.get_stats()
        self.assertEqual(stats["valid_frames"], 1)
        self.assertEqual(stats["parse_errors"], 0)

    def test_motor_command_frame(self):
        """Test motor command frame parsing."""
        parser = FrameParser()

        # Build motor command frame
        func = FUNC_MOTOR
        motor_id = 0
        rps = 0.5
        payload = bytes([MOTOR_SUBCMD_SET_SPEED, 1]) + struct.pack(
            "<Bf", motor_id, rps
        )
        body = bytes([func, len(payload)]) + payload
        crc = crc8_ccitt(body)
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])

        # Process frame
        for byte in frame:
            result = parser.process_byte(byte)

        # Validate
        self.assertIsNotNone(result)
        func_code, parsed_payload = result
        self.assertEqual(func_code, FUNC_MOTOR)
        self.assertEqual(len(parsed_payload), len(payload))

        # Parse payload
        self.assertEqual(parsed_payload[0], MOTOR_SUBCMD_SET_SPEED)
        self.assertEqual(parsed_payload[1], 1)  # 1 motor

        # Check stats
        stats = parser.get_stats()
        self.assertEqual(stats["valid_frames"], 1)

    def test_glowy_ultrasonic_telemetry_frame(self):
        """Parse the four-byte Glowy I2C telemetry payload."""
        parser = FrameParser()
        payload = struct.pack("<HBB", 1234, 1, 1)
        body = bytes([FUNC_GLOWY_ULTRASONIC, len(payload)]) + payload
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([
            crc8_ccitt(body)
        ])

        result = None
        for byte in frame:
            result = parser.process_byte(byte)

        self.assertIsNotNone(result)
        function_code, parsed_payload = result
        self.assertEqual(function_code, FUNC_GLOWY_ULTRASONIC)
        self.assertEqual(struct.unpack("<HBB", parsed_payload),
                         (1234, 1, 1))

    def test_invalid_crc(self):
        """Test rejection of invalid CRC."""
        parser = FrameParser()

        # Build frame with wrong CRC
        func = FUNC_HEARTBEAT
        payload = b""
        body = bytes([func, len(payload)]) + payload
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([0xFF])  # Wrong CRC

        # Process frame
        for byte in frame:
            result = parser.process_byte(byte)

        # Should return None (invalid frame)
        self.assertIsNone(result)

        # Check stats
        stats = parser.get_stats()
        self.assertEqual(stats["valid_frames"], 0)
        self.assertEqual(stats["parse_errors"], 1)

    def test_false_sync_detection(self):
        """Test handling of false sync bytes."""
        parser = FrameParser()

        # Send data that looks like sync but isn't
        fake_frame = b"\xaa\x00\x55\x00"  # False sync patterns

        for byte in fake_frame:
            result = parser.process_byte(byte)
            self.assertIsNone(result)

        # Should not parse any valid frames
        stats = parser.get_stats()
        self.assertEqual(stats["valid_frames"], 0)

    def test_frame_reset(self):
        """Test parser reset functionality."""
        parser = FrameParser()

        # Get into middle of frame
        parser.process_byte(SYNC_1)
        self.assertEqual(parser.get_stats()["sync_state"], 1)

        # Reset
        parser.reset()
        self.assertEqual(parser.get_stats()["sync_state"], 0)

    def test_multiple_frames(self):
        """Test parsing multiple consecutive frames."""
        parser = FrameParser()

        # Build two heartbeat frames
        func = FUNC_HEARTBEAT
        payload = b""
        body = bytes([func, len(payload)]) + payload
        crc = crc8_ccitt(body)
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])
        double_frame = frame + frame

        # Process both frames
        frames_received = 0
        for byte in double_frame:
            result = parser.process_byte(byte)
            if result is not None:
                frames_received += 1

        self.assertEqual(frames_received, 2)
        self.assertEqual(parser.get_stats()["valid_frames"], 2)


class TestIntegration(unittest.TestCase):
    """Integration tests for combined components."""

    def test_buffer_to_parser(self):
        """Test feeding buffer output to parser."""
        buf = CircularBuffer(100)
        parser = FrameParser()

        # Build a frame
        func = FUNC_HEARTBEAT
        payload = b""
        body = bytes([func, len(payload)]) + payload
        crc = crc8_ccitt(body)
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])

        # Write to buffer
        buf.write(frame)

        # Read from buffer and feed to parser
        while buf.available() > 0:
            data = buf.read(1)
            result = parser.process_byte(data[0])
            if result:
                break

        # Should have parsed the frame
        self.assertIsNotNone(result)
        self.assertEqual(parser.get_stats()["valid_frames"], 1)

    def test_noisy_data(self):
        """Test handling of noisy/corrupted data."""
        buf = CircularBuffer(100)
        parser = FrameParser()

        # Mix of valid frames and noise
        func = FUNC_HEARTBEAT
        payload = b""
        body = bytes([func, len(payload)]) + payload
        crc = crc8_ccitt(body)
        valid_frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])

        # Create noisy data
        noisy_data = b"\x00\xff\xaa\x55" + valid_frame + b"\x55\xaa\x00\xff"

        # Write to buffer
        buf.write(noisy_data)

        # Process all data
        while buf.available() > 0:
            data = buf.read(1)
            parser.process_byte(data[0])

        # Should have parsed exactly one valid frame
        stats = parser.get_stats()
        self.assertEqual(stats["valid_frames"], 1)

    def test_imu_presence_is_not_inferred_from_acceleration_values(self):
        """A received all-zero frame must remain distinguishable from silence."""
        telemetry = TelemetryData()
        self.assertFalse(telemetry.imu_received)
        telemetry.imu_accel = (0.0, 0.0, 0.0)
        telemetry.imu_received = True
        self.assertTrue(telemetry.imu_received)

    def test_imu_diagnostics_frame_has_explicit_onboard_identity(self):
        """The host can distinguish a ready onboard IMU from zero placeholders."""
        parser = FrameParser()
        payload = struct.pack("<BBHIIl", 1, 0x6A, 0x05, 12, 0, 0)
        body = bytes([FUNC_IMU_DIAG, len(payload)]) + payload
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc8_ccitt(body)])

        result = None
        for byte in frame:
            result = parser.process_byte(byte)
        self.assertEqual(result, (FUNC_IMU_DIAG, payload))

        bridge = STM32HardenedBridge.__new__(STM32HardenedBridge)
        bridge._telemetry_lock = threading.Lock()
        bridge._telemetry = TelemetryData()
        bridge._parse_imu_diagnostics(payload)
        self.assertTrue(bridge._telemetry.imu_ready)
        self.assertEqual(bridge._telemetry.imu_address, 0x6A)
        self.assertEqual(bridge._telemetry.imu_who_am_i, 0x05)
        self.assertEqual(bridge._telemetry.imu_sample_count, 12)

    def test_imu_sample_is_published_only_after_ready_diagnostics(self):
        """A finite but placeholder telemetry frame cannot claim IMU presence."""
        bridge = STM32HardenedBridge.__new__(STM32HardenedBridge)
        bridge._telemetry_lock = threading.Lock()
        bridge._telemetry = TelemetryData()
        sample = struct.pack("<ffffff", 0.0, 0.0, 9.81, 0.0, 0.0, 0.0)
        bridge._parse_imu_telemetry(sample)
        self.assertTrue(bridge._telemetry.imu_sample_valid)
        self.assertFalse(bridge._telemetry.imu_received)

        bridge._parse_imu_diagnostics(
            struct.pack("<BBHIIl", 1, 0x6A, 0x05, 1, 0, 0)
        )
        self.assertTrue(bridge._telemetry.imu_received)


class TestSerialFailureHandling(unittest.TestCase):
    """Verify failed UART objects are made eligible for reconnection."""

    class FakeSerial:
        def __init__(self):
            self.is_open = True
            self.closed = False

        def close(self):
            self.closed = True
            self.is_open = False

    class FakeLogger:
        def error(self, message):
            pass

    def _bridge_without_ros_node(self):
        bridge = STM32HardenedBridge.__new__(STM32HardenedBridge)
        bridge._serial_lock = threading.Lock()
        bridge._state_lock = threading.Lock()
        bridge._connection_loss_time = 0.0
        bridge._motion_armed = True
        bridge.get_logger = lambda: self.FakeLogger()
        return bridge

    def test_failed_current_port_is_closed_and_cleared(self):
        bridge = self._bridge_without_ros_node()
        failed_port = self.FakeSerial()
        bridge._ser = failed_port

        bridge._close_serial_after_error(failed_port, "read", OSError("gone"))

        self.assertIsNone(bridge._ser)
        self.assertTrue(failed_port.closed)
        self.assertFalse(bridge._motion_armed)
        self.assertNotEqual(bridge._connection_loss_time, 0.0)

    def test_stale_port_error_cannot_close_replacement(self):
        bridge = self._bridge_without_ros_node()
        failed_port = self.FakeSerial()
        replacement = self.FakeSerial()
        bridge._ser = replacement

        bridge._close_serial_after_error(failed_port, "read", OSError("late"))

        self.assertIs(bridge._ser, replacement)
        self.assertFalse(failed_port.closed)
        self.assertTrue(bridge._motion_armed)


def run_tests():
    """Run all tests."""
    unittest.main(argv=[""], verbosity=2, exit=False)


if __name__ == "__main__":
    print("Running STM32 Hardened Bridge Unit Tests")
    print("=" * 50)
    run_tests()
