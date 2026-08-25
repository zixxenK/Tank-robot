"""Unit tests for BuzzerSongCreator node and PS5 D-Pad / modifier mapping."""

import pytest
from robot_audio.buzzer_song_creator import BuzzerSongCreator, Joy
from robot_audio.songs import NOTE_FREQ, SEA_SHANTY_2_MELODY, SEA_SHANTY_2_SEQ


@pytest.fixture
def song_creator():
    try:
        import rclpy
        if not rclpy.ok():
            rclpy.init()
    except Exception:
        pass
    node = BuzzerSongCreator()
    # Disable background threading in tests for deterministic execution
    node.async_playback = False
    node.step_duration_s = 0.001
    node.gap_duration_s = 0.001
    yield node
    try:
        node.destroy_node()
        import rclpy
        if rclpy.ok():
            rclpy.shutdown()
    except Exception:
        pass


def make_joy_msg(l1=0, r1=0, triangle=0, touchpad=0,
                 hat_x=0.0, hat_y=0.0, touch_x=None):
    """Helper to construct Joy message with PS5 mapping."""
    buttons = [0] * 16
    axes = [0.0] * 8

    buttons[4] = int(l1)        # L1_INDEX = 4
    buttons[5] = int(r1)        # R1_INDEX = 5
    buttons[2] = int(triangle)  # TRIANGLE_INDEX = 2
    buttons[13] = int(touchpad)  # TOUCHPAD_CLICK_INDEX = 13

    axes[6] = float(hat_x)      # Linux hat: Left -1.0, Right +1.0
    axes[7] = float(hat_y)      # Linux hat: Up -1.0, Down +1.0
    if touch_x is not None:
        axes.append(float(touch_x))

    return Joy(axes=axes, buttons=buttons)


def test_base_octave_note_playing(song_creator: BuzzerSongCreator):
    """Base mode (L1=0, R1=0) plays Octave 4 notes (C4, D4, E4, F4)."""
    # Prime initial state
    song_creator.joy_callback(make_joy_msg())

    # D-Pad Up -> C4 (262 Hz)
    song_creator.joy_callback(make_joy_msg(hat_y=-1.0))
    assert song_creator.song_sequence == [262]
    song_creator.joy_callback(make_joy_msg(hat_y=0.0))  # release

    # D-Pad Right -> D4 (294 Hz)
    song_creator.joy_callback(make_joy_msg(hat_x=1.0))
    assert song_creator.song_sequence == [262, 294]
    song_creator.joy_callback(make_joy_msg(hat_x=0.0))  # release

    # D-Pad Down -> E4 (330 Hz)
    song_creator.joy_callback(make_joy_msg(hat_y=1.0))
    assert song_creator.song_sequence == [262, 294, 330]
    song_creator.joy_callback(make_joy_y_neutral := make_joy_msg(hat_y=0.0))

    # D-Pad Left -> F4 (349 Hz)
    song_creator.joy_callback(make_joy_msg(hat_x=-1.0))
    assert song_creator.song_sequence == [262, 294, 330, 349]


def test_low_octave_note_playing_l1_held(song_creator: BuzzerSongCreator):
    """Low Octave mode (L1=1, R1=0) plays Octave 3 notes (C3, D3, E3, F3)."""
    song_creator.joy_callback(make_joy_msg())

    # D-Pad Up with L1 held -> C3 (131 Hz)
    song_creator.joy_callback(make_joy_msg(l1=1, hat_y=-1.0))
    assert song_creator.song_sequence == [131]
    song_creator.joy_callback(make_joy_msg(l1=1, hat_y=0.0))

    # D-Pad Right with L1 held -> D3 (147 Hz)
    song_creator.joy_callback(make_joy_msg(l1=1, hat_x=1.0))
    assert song_creator.song_sequence == [131, 147]


def test_high_octave_note_playing_r1_held(song_creator: BuzzerSongCreator):
    """High Octave mode (L1=0, R1=1) plays Octave 5 notes (C5, D5, E5, F5)."""
    song_creator.joy_callback(make_joy_msg())

    # D-Pad Up with R1 held -> C5 (523 Hz)
    song_creator.joy_callback(make_joy_msg(r1=1, hat_y=-1.0))
    assert song_creator.song_sequence == [523]
    song_creator.joy_callback(make_joy_msg(r1=1, hat_y=0.0))

    # D-Pad Down with R1 held -> E5 (659 Hz)
    song_creator.joy_callback(make_joy_msg(r1=1, hat_y=1.0))
    assert song_creator.song_sequence == [523, 659]


def test_command_mode_actions(song_creator: BuzzerSongCreator):
    """Command mode (L1=1, R1=1) handles REST, Undo, Clear, and Play Sequence."""
    song_creator.joy_callback(make_joy_msg())

    # Add 2 notes first
    song_creator.joy_callback(make_joy_msg(hat_y=-1.0))  # C4
    song_creator.joy_callback(make_joy_msg())
    song_creator.joy_callback(make_joy_msg(hat_x=1.0))  # D4
    song_creator.joy_callback(make_joy_msg())
    assert song_creator.song_sequence == [262, 294]

    # Command Mode: D-Pad Right -> Add REST (0 Hz)
    song_creator.joy_callback(make_joy_msg(l1=1, r1=1, hat_x=1.0))
    assert song_creator.song_sequence == [262, 294, 0]
    song_creator.joy_callback(make_joy_msg(l1=1, r1=1, hat_x=0.0))

    # Command Mode: D-Pad Left -> Undo Last Note
    song_creator.joy_callback(make_joy_msg(l1=1, r1=1, hat_x=-1.0))
    assert song_creator.song_sequence == [262, 294]
    song_creator.joy_callback(make_joy_msg(l1=1, r1=1, hat_x=0.0))

    # Command Mode: D-Pad Up -> Play Full Sequence
    song_creator.joy_callback(make_joy_msg(l1=1, r1=1, hat_y=-1.0))
    # Sequence remains intact after play
    assert song_creator.song_sequence == [262, 294]
    song_creator.joy_callback(make_joy_msg(l1=1, r1=1, hat_y=0.0))

    # Command Mode: D-Pad Down -> Clear Sequence
    song_creator.joy_callback(make_joy_msg(l1=1, r1=1, hat_y=1.0))
    assert song_creator.song_sequence == []


def test_sea_shanty_2_easter_egg(song_creator: BuzzerSongCreator):
    """Holding L1 + R1 and pressing Triangle triggers Sea Shanty 2 easter egg."""
    song_creator.joy_callback(make_joy_msg())

    last_pub = {}
    class MockPub:
        def publish(self, msg):
            last_pub['msg'] = msg
    song_creator.sequence_pub = MockPub()

    # Trigger L1 + R1 + Triangle
    song_creator.joy_callback(make_joy_msg(l1=1, r1=1, triangle=1))
    assert 'msg' in last_pub
    assert last_pub['msg'].data == list(SEA_SHANTY_2_SEQ)


def test_edge_triggering_no_duplicate_on_hold(song_creator: BuzzerSongCreator):
    """Holding down D-Pad button across multiple frames triggers exactly once."""
    song_creator.joy_callback(make_joy_msg())

    # Frame 1: D-Pad pressed
    song_creator.joy_callback(make_joy_msg(hat_y=-1.0))
    assert len(song_creator.song_sequence) == 1

    # Frame 2: D-Pad still pressed (held)
    song_creator.joy_callback(make_joy_msg(hat_y=-1.0))
    assert len(song_creator.song_sequence) == 1

    # Frame 3: Released
    song_creator.joy_callback(make_joy_msg(hat_y=0.0))
    assert len(song_creator.song_sequence) == 1

    # Frame 4: Pressed again
    song_creator.joy_callback(make_joy_msg(hat_y=1.0))
    assert len(song_creator.song_sequence) == 2


def test_touchpad_click_cycles_octave(song_creator: BuzzerSongCreator):
    """A short touchpad click advances the synth octave and wraps."""
    song_creator.joy_callback(make_joy_msg())
    assert song_creator.current_octave == 4

    song_creator.joy_callback(make_joy_msg(touchpad=1))
    song_creator.joy_callback(make_joy_msg())
    assert song_creator.current_octave == 5

    # Four more clicks: 6, then wrap to 3, 4, and 5.
    for expected in (6, 3, 4, 5):
        song_creator.joy_callback(make_joy_msg(touchpad=1))
        song_creator.joy_callback(make_joy_msg())
        assert song_creator.current_octave == expected


def test_touchpad_hold_starts_and_release_stops_loop(song_creator: BuzzerSongCreator):
    """Holding the touchpad starts a cancellable Sea Shanty loop."""
    song_creator._handle_touchpad(True, False, 10.0, [0.0] * 8)
    assert not song_creator._touchpad_loop_active

    song_creator._handle_touchpad(True, True, 10.36, [0.0] * 8)
    assert song_creator._touchpad_loop_active
    assert song_creator._playback_thread is not None

    song_creator._handle_touchpad(False, True, 10.40, [0.0] * 8)
    assert not song_creator._touchpad_loop_active
    assert song_creator._playback_thread is None


def test_touchpad_x_maps_to_chromatic_note(song_creator: BuzzerSongCreator):
    """A driver-provided touch X axis maps the pad to a chromatic octave."""
    song_creator.TOUCHPAD_X_AXIS = 8
    song_creator._handle_touchpad(True, False, 10.0,
                                  [0.0] * 8 + [-1.0])
    song_creator._handle_touchpad(True, True, 10.01,
                                  [0.0] * 8 + [-1.0])
    assert song_creator._last_touchpad_note == NOTE_FREQ['C4']
    song_creator._handle_touchpad(True, True, 10.01,
                                  [0.0] * 8 + [1.0])
    assert song_creator._last_touchpad_note == NOTE_FREQ['B4']
