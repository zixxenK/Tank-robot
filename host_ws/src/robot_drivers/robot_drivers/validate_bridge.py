#!/usr/bin/env python3
"""Simple validation script for STM32 Hardened Bridge components."""

import struct
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from test_bridge_components import (
    CircularBuffer,
    FrameParser,
    crc8_ccitt,
    SYNC_1,
    SYNC_2,
    FUNC_HEARTBEAT,
    FUNC_MOTOR,
    MOTOR_SUBCMD_SET_SPEED,
)


def test_crc():
    """Test CRC implementation."""
    print("Testing CRC-8-CCITT...")
    
    # Test known values
    assert crc8_ccitt(b'') == 0x00, "Empty data CRC failed"
    assert crc8_ccitt(b'\x00') == 0x00, "Single zero CRC failed"
    
    # Test frame CRC
    func = FUNC_HEARTBEAT
    payload = b''
    body = bytes([func, len(payload)]) + payload
    crc = crc8_ccitt(body)
    
    frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])
    extracted_body = frame[2:4]
    extracted_crc = frame[4]
    calculated_crc = crc8_ccitt(extracted_body)
    
    assert extracted_crc == calculated_crc, "Frame CRC validation failed"
    print("[PASS] CRC tests passed")


def test_buffer():
    """Test circular buffer."""
    print("Testing Circular Buffer...")
    
    buf = CircularBuffer(10)
    
    # Basic write/read
    data = b'Hello'
    written = buf.write(data)
    assert written == 5, f"Write failed: expected 5, got {written}"
    assert buf.available() == 5, f"Available count wrong: expected 5, got {buf.available()}"
    
    read_data = buf.read(5)
    assert read_data == data, f"Read data mismatch: expected {data}, got {read_data}"
    assert buf.available() == 0, f"Buffer not empty after read"
    
    # Wraparound test
    buf.write(b'0123456789')
    buf.read(5)
    buf.write(b'ABCDE')
    read_data = buf.read(10)
    assert read_data == b'56789ABCDE', f"Wraparound failed: got {read_data}"
    
    # Overflow test - write more than buffer size
    buf.clear()
    written = buf.write(b'0123456789ABCDEF')  # 16 bytes into 10-byte buffer
    # Should only write 10 bytes (buffer size)
    assert written == 10, f"Overflow handling failed: expected 10, got {written}"
    
    print("[PASS] Buffer tests passed")


def test_frame_parser():
    """Test frame parser."""
    print("Testing Frame Parser...")
    
    parser = FrameParser()
    
    # Test heartbeat frame
    func = FUNC_HEARTBEAT
    payload = b''
    body = bytes([func, len(payload)]) + payload
    crc = crc8_ccitt(body)
    frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])
    
    result = None
    for byte in frame:
        result = parser.process_byte(byte)
    
    assert result is not None, "Frame parser returned None for valid frame"
    func_code, parsed_payload = result
    assert func_code == FUNC_HEARTBEAT, f"Function code mismatch: expected {FUNC_HEARTBEAT}, got {func_code}"
    assert parsed_payload == b'', f"Payload mismatch: expected empty, got {parsed_payload}"
    
    stats = parser.get_stats()
    assert stats['valid_frames'] == 1, f"Valid frame count wrong: expected 1, got {stats['valid_frames']}"
    
    # Test motor command frame
    parser.reset()
    motor_id = 0
    rps = 0.5
    payload = bytes([MOTOR_SUBCMD_SET_SPEED, 1]) + struct.pack('<Bf', motor_id, rps)
    body = bytes([FUNC_MOTOR, len(payload)]) + payload
    crc = crc8_ccitt(body)
    frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])
    
    result = None
    for byte in frame:
        result = parser.process_byte(byte)
    
    assert result is not None, "Motor frame parser returned None"
    func_code, parsed_payload = result
    assert func_code == FUNC_MOTOR, f"Motor function code wrong: expected {FUNC_MOTOR}, got {func_code}"
    assert len(parsed_payload) == len(payload), f"Motor payload length wrong"
    
    # Test invalid CRC
    parser.reset()
    func = FUNC_HEARTBEAT
    payload = b''
    body = bytes([func, len(payload)]) + payload
    frame = bytes([SYNC_1, SYNC_2]) + body + bytes([0xFF])  # Wrong CRC
    
    result = None
    for byte in frame:
        result = parser.process_byte(byte)
    
    assert result is None, "Invalid CRC frame should return None"
    stats = parser.get_stats()
    assert stats['parse_errors'] > 0, "Parse error count should be > 0 for invalid CRC"
    
    print("[PASS] Frame parser tests passed")


def test_integration():
    """Test buffer + parser integration."""
    print("Testing Buffer + Parser Integration...")
    
    buf = CircularBuffer(100)
    parser = FrameParser()
    
    # Build a frame
    func = FUNC_HEARTBEAT
    payload = b''
    body = bytes([func, len(payload)]) + payload
    crc = crc8_ccitt(body)
    frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])
    
    # Write to buffer
    buf.write(frame)
    
    # Read from buffer and feed to parser
    result = None
    while buf.available() > 0:
        data = buf.read(1)
        result = parser.process_byte(data[0])
        if result:
            break
    
    assert result is not None, "Integration test failed: no frame parsed"
    stats = parser.get_stats()
    assert stats['valid_frames'] == 1, f"Integration test: expected 1 valid frame, got {stats['valid_frames']}"
    
    print("[PASS] Integration tests passed")


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("STM32 Hardened Bridge Component Validation")
    print("=" * 60)
    
    try:
        test_crc()
        test_buffer()
        test_frame_parser()
        test_integration()
        
        print("=" * 60)
        print("[PASS] ALL VALIDATION TESTS PASSED")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n[ERROR] UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
