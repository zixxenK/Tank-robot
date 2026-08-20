"""Streaming parser and synchronized scan assembly for the STL-50B2.

The STL family uses the LDROBOT 0x54/0x2c packet format.  A packet contains
12 evenly spaced samples, with distance in millimetres and angle in hundredths
of a degree.  The parser deliberately has no ROS or hardware dependencies so
captured serial data can be tested on a development machine.
"""

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

PACKET_HEADER = 0x54
PACKET_VERSION_LENGTH = 0x2C
POINTS_PER_PACKET = 12
PACKET_SIZE = 47

# This is the CRC table published in LDROBOT's ldlidar_stl_ros2 SDK.
_CRC8_TABLE = (
    0x00, 0x4D, 0x9A, 0xD7, 0x79, 0x34, 0xE3, 0xAE, 0xF2, 0xBF, 0x68,
    0x25, 0x8B, 0xC6, 0x11, 0x5C, 0xA9, 0xE4, 0x33, 0x7E, 0xD0, 0x9D,
    0x4A, 0x07, 0x5B, 0x16, 0xC1, 0x8C, 0x22, 0x6F, 0xB8, 0xF5, 0x1F,
    0x52, 0x85, 0xC8, 0x66, 0x2B, 0xFC, 0xB1, 0xED, 0xA0, 0x77, 0x3A,
    0x94, 0xD9, 0x0E, 0x43, 0xB6, 0xFB, 0x2C, 0x61, 0xCF, 0x82, 0x55,
    0x18, 0x44, 0x09, 0xDE, 0x93, 0x3D, 0x70, 0xA7, 0xEA, 0x3E, 0x73,
    0xA4, 0xE9, 0x47, 0x0A, 0xDD, 0x90, 0xCC, 0x81, 0x56, 0x1B, 0xB5,
    0xF8, 0x2F, 0x62, 0x97, 0xDA, 0x0D, 0x40, 0xEE, 0xA3, 0x74, 0x39,
    0x65, 0x28, 0xFF, 0xB2, 0x1C, 0x51, 0x86, 0xCB, 0x21, 0x6C, 0xBB,
    0xF6, 0x58, 0x15, 0xC2, 0x8F, 0xD3, 0x9E, 0x49, 0x04, 0xAA, 0xE7,
    0x30, 0x7D, 0x88, 0xC5, 0x12, 0x5F, 0xF1, 0xBC, 0x6B, 0x26, 0x7A,
    0x37, 0xE0, 0xAD, 0x03, 0x4E, 0x99, 0xD4, 0x7C, 0x31, 0xE6, 0xAB,
    0x05, 0x48, 0x9F, 0xD2, 0x8E, 0xC3, 0x14, 0x59, 0xF7, 0xBA, 0x6D,
    0x20, 0xD5, 0x98, 0x4F, 0x02, 0xAC, 0xE1, 0x36, 0x7B, 0x27, 0x6A,
    0xBD, 0xF0, 0x5E, 0x13, 0xC4, 0x89, 0x63, 0x2E, 0xF9, 0xB4, 0x1A,
    0x57, 0x80, 0xCD, 0x91, 0xDC, 0x0B, 0x46, 0xE8, 0xA5, 0x72, 0x3F,
    0xCA, 0x87, 0x50, 0x1D, 0xB3, 0xFE, 0x29, 0x64, 0x38, 0x75, 0xA2,
    0xEF, 0x41, 0x0C, 0xDB, 0x96, 0x42, 0x0F, 0xD8, 0x95, 0x3B, 0x76,
    0xA1, 0xEC, 0xB0, 0xFD, 0x2A, 0x67, 0xC9, 0x84, 0x53, 0x1E, 0xEB,
    0xA6, 0x71, 0x3C, 0x92, 0xDF, 0x08, 0x45, 0x19, 0x54, 0x83, 0xCE,
    0x60, 0x2D, 0xFA, 0xB7, 0x5D, 0x10, 0xC7, 0x8A, 0x24, 0x69, 0xBE,
    0xF3, 0xAF, 0xE2, 0x35, 0x78, 0xD6, 0x9B, 0x4C, 0x01, 0xF4, 0xB9,
    0x6E, 0x23, 0x8D, 0xC0, 0x17, 0x5A, 0x06, 0x4B, 0x9C, 0xD1, 0x7F,
    0x32, 0xE5, 0xA8,
)


def crc8(data: Sequence[int]) -> int:
    """Return the LDROBOT CRC-8 for ``data``."""
    value = 0
    for byte in data:
        value = _CRC8_TABLE[value ^ byte]
    return value


@dataclass(frozen=True)
class STL50B2Point:
    """One interpolated point from an STL-50B2 packet."""

    angle_deg: float
    distance_mm: int
    intensity: int


@dataclass(frozen=True)
class STL50B2Packet:
    """Decoded STL-50B2 packet."""

    speed_dps: int
    start_angle_deg: float
    end_angle_deg: float
    timestamp_ms: int
    points: Tuple[STL50B2Point, ...]


@dataclass(frozen=True)
class SynchronizedScan:
    """Points collected between two hardware synchronization edges."""

    stamp_ns: int
    points: Tuple[STL50B2Point, ...]


def decode_packet(packet: bytes) -> STL50B2Packet:
    """Decode and CRC-check one complete 47-byte packet."""
    if len(packet) != PACKET_SIZE:
        raise ValueError("STL-50B2 packet must be 47 bytes")
    if packet[0] != PACKET_HEADER or packet[1] != PACKET_VERSION_LENGTH:
        raise ValueError("invalid STL-50B2 packet header")
    if crc8(packet[:-1]) != packet[-1]:
        raise ValueError("invalid STL-50B2 packet CRC")

    speed_dps = int.from_bytes(packet[2:4], "little")
    start_hundredths = int.from_bytes(packet[4:6], "little")
    end_hundredths = int.from_bytes(packet[42:44], "little")
    delta = (end_hundredths - start_hundredths) % 36000
    step = delta / (POINTS_PER_PACKET - 1) / 100.0
    start_angle = start_hundredths / 100.0

    points = []
    for index in range(POINTS_PER_PACKET):
        offset = 6 + index * 3
        distance = int.from_bytes(packet[offset:offset + 2], "little")
        angle = (start_angle + index * step) % 360.0
        points.append(STL50B2Point(angle, distance, packet[offset + 2]))

    return STL50B2Packet(
        speed_dps=speed_dps,
        start_angle_deg=start_angle,
        end_angle_deg=end_hundredths / 100.0,
        timestamp_ms=int.from_bytes(packet[44:46], "little"),
        points=tuple(points),
    )


class STL50B2StreamParser:
    """Recover valid STL-50B2 packets from arbitrarily chunked UART data."""

    def __init__(self) -> None:
        """Create an empty stream parser."""
        self._buffer = bytearray()
        self.bad_packets = 0

    def feed(self, data: bytes) -> List[STL50B2Packet]:
        """Append serial bytes and return all newly decoded packets."""
        self._buffer.extend(data)
        packets = []
        while len(self._buffer) >= 2:
            header_index = self._buffer.find(
                bytes((PACKET_HEADER, PACKET_VERSION_LENGTH))
            )
            if header_index < 0:
                del self._buffer[:-1]
                break
            if header_index:
                del self._buffer[:header_index]
            if len(self._buffer) < PACKET_SIZE:
                break
            candidate = bytes(self._buffer[:PACKET_SIZE])
            try:
                packets.append(decode_packet(candidate))
            except ValueError:
                self.bad_packets += 1
                del self._buffer[0]
                continue
            del self._buffer[:PACKET_SIZE]
        return packets


class SynchronizedScanAssembler:
    """Use GPIO edges as mandatory scan boundaries."""

    def __init__(self, max_points: int = 10000) -> None:
        """Create an assembler that waits for the first sync edge."""
        self._max_points = max_points
        self._synchronized = False
        self._stamp_ns: Optional[int] = None
        self._points: List[STL50B2Point] = []

    @property
    def synchronized(self) -> bool:
        """Whether a valid synchronization edge has been received."""
        return self._synchronized

    def add_packet(self, packet: STL50B2Packet) -> None:
        """Add a packet, discarding data received before synchronization."""
        if not self._synchronized:
            return
        self._points.extend(packet.points)
        if len(self._points) > self._max_points:
            # A missing edge must never create an unbounded memory growth.
            self._points.clear()

    def sync_edge(self, stamp_ns: int) -> Optional[SynchronizedScan]:
        """Close the previous scan and begin a new synchronized scan."""
        completed = None
        if self._synchronized and self._points and self._stamp_ns is not None:
            completed = SynchronizedScan(
                stamp_ns=self._stamp_ns,
                points=tuple(self._points),
            )
        self._synchronized = True
        self._stamp_ns = stamp_ns
        self._points = []
        return completed
