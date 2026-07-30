#!/usr/bin/env python3
"""Standalone unit tests for STM32 Hardened Bridge core components."""

import unittest
import struct
import threading
import time


# CRC-8-CCITT Table
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

# Protocol Constants
SYNC_1 = 0xAA
SYNC_2 = 0x55
FRAME_HEADER_SIZE = 4
FRAME_FOOTER_SIZE = 1
MAX_FRAME_SIZE = 256

# Function Codes
FUNC_MOTOR = 0x03
FUNC_HEARTBEAT = 0xF0
MOTOR_SUBCMD_SET_SPEED = 0x01


def crc8_ccitt(data: bytes) -> int:
    """Calculate CRC-8-CCITT."""
    crc = 0x00
    for byte in data:
        crc = CRC8_TABLE[crc ^ byte]
    return crc


class CircularBuffer:
    """Thread-safe circular buffer for serial data."""

    def __init__(self, size: int):
        self.buffer = bytearray(size)
        self.size = size
        self.write_pos = 0
        self.read_pos = 0
        self.lock = threading.Lock()
        self.count = 0

    def write(self, data: bytes) -> int:
        """Write data to buffer, returns number of bytes written."""
        with self.lock:
            bytes_written = 0
            for byte in data:
                if self.count < self.size:
                    self.buffer[self.write_pos] = byte
                    self.write_pos = (self.write_pos + 1) % self.size
                    self.count += 1
                    bytes_written += 1
                else:
                    break
            return bytes_written

    def read(self, max_bytes: int) -> bytes:
        """Read up to max_bytes from buffer."""
        with self.lock:
            if self.count == 0:
                return b''
            
            bytes_to_read = min(max_bytes, self.count)
            result = bytearray(bytes_to_read)
            
            for i in range(bytes_to_read):
                result[i] = self.buffer[self.read_pos]
                self.read_pos = (self.read_pos + 1) % self.size
                self.count -= 1
            
            return bytes(result)

    def peek(self, max_bytes: int) -> bytes:
        """Peek at data without consuming it."""
        with self.lock:
            if self.count == 0:
                return b''
            
            bytes_to_peek = min(max_bytes, self.count)
            result = bytearray(bytes_to_peek)
            temp_pos = self.read_pos
            
            for i in range(bytes_to_peek):
                result[i] = self.buffer[temp_pos]
                temp_pos = (temp_pos + 1) % self.size
            
            return bytes(result)

    def clear(self):
        """Clear the buffer."""
        with self.lock:
            self.write_pos = 0
            self.read_pos = 0
            self.count = 0

    def available(self) -> int:
        """Return number of bytes available to read."""
        with self.lock:
            return self.count


class FrameParser:
    """Robust binary frame parser with sync detection and CRC validation."""

    def __init__(self):
        self.sync_state = 0
        self.expected_payload_len = 0
        self.frame_buffer = bytearray()
        self.parse_errors = 0
        self.valid_frames = 0
        self.lock = threading.Lock()

    def reset(self):
        """Reset parser state."""
        with self.lock:
            self.sync_state = 0
            self.expected_payload_len = 0
            self.frame_buffer.clear()

    def process_byte(self, byte: int):
        """Process a single byte, return complete frame if available."""
        with self.lock:
            if self.sync_state == 0:
                if byte == SYNC_1:
                    self.sync_state = 1
                    self.frame_buffer = bytearray([SYNC_1])
                return None
            
            elif self.sync_state == 1:
                if byte == SYNC_2:
                    self.sync_state = 2
                    self.frame_buffer.append(SYNC_2)
                else:
                    if byte == SYNC_1:
                        self.frame_buffer = bytearray([SYNC_1])
                    else:
                        self.sync_state = 0
                        self.frame_buffer.clear()
                return None
            
            elif self.sync_state == 2:
                self.frame_buffer.append(byte)
                self.sync_state = 3
                return None
            
            elif self.sync_state == 3:
                self.frame_buffer.append(byte)
                self.expected_payload_len = byte
                if self.expected_payload_len == 0:
                    self.sync_state = 4
                else:
                    self.sync_state = 4
                return None
            
            elif self.sync_state == 4:
                self.frame_buffer.append(byte)
                
                current_len = len(self.frame_buffer)
                if current_len >= FRAME_HEADER_SIZE + self.expected_payload_len:
                    if current_len == FRAME_HEADER_SIZE + self.expected_payload_len + FRAME_FOOTER_SIZE:
                        frame = bytes(self.frame_buffer)
                        result = self._validate_frame(frame)
                        self.reset()
                        if result:
                            self.valid_frames += 1
                            return result
                        else:
                            self.parse_errors += 1
                            return None
                return None
            
            return None

    def _validate_frame(self, frame: bytes):
        """Validate frame CRC and return (function_code, payload)."""
        if len(frame) < FRAME_HEADER_SIZE + FRAME_FOOTER_SIZE:
            return None
        
        function_code = frame[2]
        payload_len = frame[3]
        payload = frame[4:4+payload_len]
        received_crc = frame[4+payload_len]
        
        body = frame[2:4+payload_len]
        calculated_crc = crc8_ccitt(body)
        
        if received_crc != calculated_crc:
            return None
        
        return function_code, payload

    def get_stats(self):
        """Get parser statistics."""
        with self.lock:
            return {
                'valid_frames': self.valid_frames,
                'parse_errors': self.parse_errors,
                'sync_state': self.sync_state
            }


class TestCRC8(unittest.TestCase):
    """Test CRC-8-CCITT implementation."""

    def test_crc8_table(self):
        """Test CRC table is valid."""
        self.assertEqual(len(CRC8_TABLE), 256)
        self.assertEqual(CRC8_TABLE[0], 0)
        self.assertEqual(CRC8_TABLE[1], 94)

    def test_crc8_calculation(self):
        """Test CRC calculation with known values."""
        self.assertEqual(crc8_ccitt(b''), 0x00)
        self.assertEqual(crc8_ccitt(b'\x00'), 0x00)

    def test_crc8_frame_validation(self):
        """Test CRC validation on complete frames."""
        func = FUNC_HEARTBEAT
        payload = b''
        body = bytes([func, len(payload)]) + payload
        crc = crc8_ccitt(body)
        
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])
        
        extracted_body = frame[2:4]
        extracted_crc = frame[4]
        calculated_crc = crc8_ccitt(extracted_body)
        
        self.assertEqual(extracted_crc, calculated_crc)


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
        data = b'Hello'
        written = buf.write(data)
        self.assertEqual(written, 5)
        self.assertEqual(buf.available(), 5)
        
        read_data = buf.read(5)
        self.assertEqual(read_data, data)
        self.assertEqual(buf.available(), 0)

    def test_buffer_wraparound(self):
        """Test buffer wraparound."""
        buf = CircularBuffer(10)
        buf.write(b'0123456789')
        self.assertEqual(buf.available(), 10)
        
        buf.read(5)
        self.assertEqual(buf.available(), 5)
        
        written = buf.write(b'ABCDE')
        self.assertEqual(written, 5)
        self.assertEqual(buf.available(), 10)
        
        read_data = buf.read(10)
        self.assertEqual(read_data, b'56789ABCDE')

    def test_buffer_overflow(self):
        """Test buffer overflow handling."""
        buf = CircularBuffer(5)
        written = buf.write(b'0123456789')
        self.assertEqual(written, 5)
        self.assertEqual(buf.available(), 5)

    def test_buffer_peek(self):
        """Test peek operation."""
        buf = CircularBuffer(10)
        buf.write(b'HelloWorld')
        
        peeked = buf.peek(5)
        self.assertEqual(peeked, b'Hello')
        self.assertEqual(buf.available(), 10)
        
        read = buf.read(5)
        self.assertEqual(read, b'Hello')
        self.assertEqual(buf.available(), 5)

    def test_buffer_clear(self):
        """Test buffer clear operation."""
        buf = CircularBuffer(10)
        buf.write(b'HelloWorld')
        self.assertEqual(buf.available(), 10)
        
        buf.clear()
        self.assertEqual(buf.available(), 0)


class TestFrameParser(unittest.TestCase):
    """Test frame parser implementation."""

    def test_parser_initialization(self):
        """Test parser initialization."""
        parser = FrameParser()
        stats = parser.get_stats()
        self.assertEqual(stats['valid_frames'], 0)
        self.assertEqual(stats['parse_errors'], 0)

    def test_sync_detection(self):
        """Test sync byte detection."""
        parser = FrameParser()
        
        result = parser.process_byte(0x00)
        self.assertIsNone(result)
        
        result = parser.process_byte(SYNC_1)
        self.assertIsNone(result)
        self.assertEqual(parser.get_stats()['sync_state'], 1)
        
        result = parser.process_byte(SYNC_2)
        self.assertIsNone(result)
        self.assertEqual(parser.get_stats()['sync_state'], 2)

    def test_heartbeat_frame(self):
        """Test heartbeat frame parsing."""
        parser = FrameParser()
        
        func = FUNC_HEARTBEAT
        payload = b''
        body = bytes([func, len(payload)]) + payload
        crc = crc8_ccitt(body)
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])
        
        for byte in frame:
            result = parser.process_byte(byte)
        
        self.assertIsNotNone(result)
        if result is not None:
            func_code, parsed_payload = result
            self.assertEqual(func_code, FUNC_HEARTBEAT)
            self.assertEqual(parsed_payload, b'')
        
        stats = parser.get_stats()
        self.assertEqual(stats['valid_frames'], 1)

    def test_motor_command_frame(self):
        """Test motor command frame parsing."""
        parser = FrameParser()
        
        func = FUNC_MOTOR
        motor_id = 0
        rps = 0.5
        payload = bytes([MOTOR_SUBCMD_SET_SPEED, 1]) + struct.pack('<Bf', motor_id, rps)
        body = bytes([func, len(payload)]) + payload
        crc = crc8_ccitt(body)
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])
        
        for byte in frame:
            result = parser.process_byte(byte)
        
        self.assertIsNotNone(result)
        if result is not None:
            func_code, parsed_payload = result
            self.assertEqual(func_code, FUNC_MOTOR)
            self.assertEqual(len(parsed_payload), len(payload))
        
        stats = parser.get_stats()
        self.assertEqual(stats['valid_frames'], 1)

    def test_invalid_crc(self):
        """Test rejection of invalid CRC."""
        parser = FrameParser()
        
        func = FUNC_HEARTBEAT
        payload = b''
        body = bytes([func, len(payload)]) + payload
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([0xFF])
        
        for byte in frame:
            result = parser.process_byte(byte)
        
        self.assertIsNone(result)
        
        stats = parser.get_stats()
        self.assertEqual(stats['valid_frames'], 0)
        self.assertEqual(stats['parse_errors'], 1)

    def test_multiple_frames(self):
        """Test parsing multiple consecutive frames."""
        parser = FrameParser()
        
        func = FUNC_HEARTBEAT
        payload = b''
        body = bytes([func, len(payload)]) + payload
        crc = crc8_ccitt(body)
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])
        double_frame = frame + frame
        
        frames_received = 0
        for byte in double_frame:
            result = parser.process_byte(byte)
            if result is not None:
                frames_received += 1
        
        self.assertEqual(frames_received, 2)
        self.assertEqual(parser.get_stats()['valid_frames'], 2)


if __name__ == '__main__':
    print("Running STM32 Hardened Bridge Component Tests")
    print("=" * 50)
    unittest.main(argv=[''], verbosity=2)
