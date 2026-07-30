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


def main():
    """Run simple validation tests."""
    print("=" * 60)
    print("STM32 Hardened Bridge Component Validation")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    # Test 1: CRC
    print("\n1. Testing CRC-8-CCITT...")
    try:
        assert crc8_ccitt(b'') == 0x00
        assert crc8_ccitt(b'\x00') == 0x00
        
        func = FUNC_HEARTBEAT
        payload = b''
        body = bytes([func, len(payload)]) + payload
        crc = crc8_ccitt(body)
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])
        extracted_body = frame[2:4]
        extracted_crc = frame[4]
        calculated_crc = crc8_ccitt(extracted_body)
        assert extracted_crc == calculated_crc
        
        print("   [PASS] CRC tests passed")
        passed += 1
    except Exception as e:
        print(f"   [FAIL] CRC tests failed: {e}")
        failed += 1
    
    # Test 2: Buffer
    print("\n2. Testing Circular Buffer...")
    try:
        buf = CircularBuffer(10)
        data = b'Hello'
        written = buf.write(data)
        assert written == 5
        assert buf.available() == 5
        read_data = buf.read(5)
        assert read_data == data
        assert buf.available() == 0
        
        print("   [PASS] Buffer tests passed")
        passed += 1
    except Exception as e:
        print(f"   [FAIL] Buffer tests failed: {e}")
        failed += 1
    
    # Test 3: Frame Parser
    print("\n3. Testing Frame Parser...")
    try:
        parser = FrameParser()
        
        func = FUNC_HEARTBEAT
        payload = b''
        body = bytes([func, len(payload)]) + payload
        crc = crc8_ccitt(body)
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])
        
        result = None
        for byte in frame:
            result = parser.process_byte(byte)
        
        assert result is not None
        func_code, parsed_payload = result
        assert func_code == FUNC_HEARTBEAT
        assert parsed_payload == b''
        
        stats = parser.get_stats()
        assert stats['valid_frames'] == 1
        
        print("   [PASS] Frame parser tests passed")
        passed += 1
    except Exception as e:
        print(f"   [FAIL] Frame parser tests failed: {e}")
        failed += 1
    
    # Test 4: Integration
    print("\n4. Testing Integration...")
    try:
        buf = CircularBuffer(100)
        parser = FrameParser()
        
        func = FUNC_HEARTBEAT
        payload = b''
        body = bytes([func, len(payload)]) + payload
        crc = crc8_ccitt(body)
        frame = bytes([SYNC_1, SYNC_2]) + body + bytes([crc])
        
        buf.write(frame)
        
        result = None
        while buf.available() > 0:
            data = buf.read(1)
            result = parser.process_byte(data[0])
            if result:
                break
        
        assert result is not None
        stats = parser.get_stats()
        assert stats['valid_frames'] == 1
        
        print("   [PASS] Integration tests passed")
        passed += 1
    except Exception as e:
        print(f"   [FAIL] Integration tests failed: {e}")
        failed += 1
    
    # Summary
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("[PASS] ALL VALIDATION TESTS PASSED")
    else:
        print("[FAIL] SOME TESTS FAILED")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
