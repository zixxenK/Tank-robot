"""Tests for the STL-50B2 wire parser and GPIO scan boundary logic."""

from robot_drivers.stl50b2_parser import (
    PACKET_SIZE,
    POINTS_PER_PACKET,
    STL50B2StreamParser,
    SynchronizedScanAssembler,
    crc8,
)


def _packet(start_angle, end_angle, distance=1000):
    """Build a valid LDROBOT packet for parser tests."""
    packet = bytearray(PACKET_SIZE)
    packet[0:2] = bytes((0x54, 0x2C))
    packet[2:4] = (36000).to_bytes(2, "little")
    packet[4:6] = int(start_angle * 100).to_bytes(2, "little")
    for index in range(POINTS_PER_PACKET):
        offset = 6 + index * 3
        packet[offset:offset + 2] = (distance + index).to_bytes(2, "little")
        packet[offset + 2] = index
    packet[42:44] = int(end_angle * 100).to_bytes(2, "little")
    packet[44:46] = (1234).to_bytes(2, "little")
    packet[-1] = crc8(packet[:-1])
    return bytes(packet)


def test_parser_handles_fragmentation_and_noise():
    """The stream parser recovers packets across arbitrary UART chunks."""
    raw = b"noise" + _packet(10.0, 20.0)
    parser = STL50B2StreamParser()
    packets = []
    for index in range(0, len(raw), 7):
        packets.extend(parser.feed(raw[index:index + 7]))

    assert len(packets) == 1
    assert packets[0].points[0].angle_deg == 10.0
    assert packets[0].points[-1].angle_deg == 20.0
    assert packets[0].points[0].distance_mm == 1000


def test_parser_rejects_bad_crc_and_resynchronizes():
    """A corrupt packet does not poison the following valid packet."""
    corrupt = bytearray(_packet(0.0, 10.0))
    corrupt[-1] ^= 0xFF
    parser = STL50B2StreamParser()
    packets = parser.feed(bytes(corrupt) + _packet(20.0, 30.0))

    assert parser.bad_packets == 1
    assert len(packets) == 1
    assert packets[0].start_angle_deg == 20.0


def test_sync_edges_are_required_for_scan_output():
    """Packets before the first edge are discarded and edges close scans."""
    parser = STL50B2StreamParser()
    packet = parser.feed(_packet(0.0, 10.0))[0]
    assembler = SynchronizedScanAssembler()
    assembler.add_packet(packet)
    assert assembler.sync_edge(100) is None
    assembler.add_packet(packet)

    scan = assembler.sync_edge(200)
    assert scan is not None
    assert scan.stamp_ns == 100
    assert len(scan.points) == POINTS_PER_PACKET


def test_packet_angle_rollover_closes_scan_without_gpio():
    """Packet rollover produces scans when GPIO sync is not used."""
    parser = STL50B2StreamParser()
    packets = parser.feed(
        _packet(350.0, 359.0)
        + _packet(0.0, 10.0)
    )
    assembler = SynchronizedScanAssembler(require_sync=False)
    assert assembler.add_packet(packets[0], 100) is None
    scan = assembler.add_packet(packets[1], 200)
    assert scan is not None
    assert scan.stamp_ns == 100
    assert len(scan.points) == POINTS_PER_PACKET
