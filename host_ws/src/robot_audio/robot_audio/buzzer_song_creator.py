#!/usr/bin/env python3
"""buzzer_song_creator.py — Modular ROS 2 Buzzer Song Creator and Step Sequencer.

Maps PS5 DualSense controller's D-Pad and bumper modifiers (L1/R1) into
a real-time note player, step sequencer, and easter-egg song trigger.
"""

import os
import sys
import time
import threading
from pathlib import Path
from typing import List, Optional

try:
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import Joy
    from std_msgs.msg import Int32, Int32MultiArray, String
except ImportError:
    # Standalone / fallback mocks for testing outside ROS 2 environment
    class _MockMsg:
        pass

    class Joy(_MockMsg):  # type: ignore[no-redef]
        def __init__(self, axes=None, buttons=None):
            self.axes = axes or [0.0] * 8
            self.buttons = buttons or [0] * 16

    class Int32(_MockMsg):  # type: ignore[no-redef]
        def __init__(self, data=0):
            self.data = data

    class Int32MultiArray(_MockMsg):  # type: ignore[no-redef]
        def __init__(self, data=None):
            self.data = data or []

    class String(_MockMsg):  # type: ignore[no-redef]
        def __init__(self, data=""):
            self.data = data

    class Node:  # type: ignore[no-redef]
        def __init__(self, name: str):
            self._name = name

        def get_logger(self):
            node_name = self._name
            class _Logger:
                def info(self, msg):
                    pass
                def warn(self, msg):
                    pass
                def error(self, msg):
                    pass
            return _Logger()

        def create_subscription(self, msg_type, topic, callback, qos_profile):
            return None

        def create_publisher(self, msg_type, topic, qos_profile):
            class _Pub:
                def __init__(self):
                    self.last_msg = None
                def publish(self, msg):
                    self.last_msg = msg
            return _Pub()

        def declare_parameter(self, name, default_val):
            class _Param:
                def __init__(self, val):
                    self.value = val
            return _Param(default_val)

        def get_parameter(self, name):
            class _Param:
                def __init__(self, val):
                    self.value = val
            return _Param(None)

        def destroy_node(self):
            pass


from robot_audio.songs import NOTE_FREQ, SEA_SHANTY_2_SEQ
from robot_control.control_map import (
    ControlMap,
    default_control_map,
    load_control_map,
)


class BuzzerSongCreator(Node):
    """ROS 2 Node for interactive buzzer song creation and playback via gamepad."""

    def __init__(self):
        super().__init__('buzzer_song_creator')

        # Parameter Declarations
        self.declare_parameter('joy_topic', '/joy')
        self.declare_parameter('frequency_topic', '/buzzer/frequency')
        self.declare_parameter('play_sequence_topic', '/buzzer/play_sequence')
        self.declare_parameter('status_topic', '/buzzer/status')
        self.declare_parameter('control_map_path', '')
        # Negative values use the canonical robot_control map. These remain
        # parameters so a lab-specific accessory layout can be commissioned
        # without changing the node API.
        self.declare_parameter('l1_index', -1)
        self.declare_parameter('r1_index', -1)
        self.declare_parameter('hat_x_index', -1)
        self.declare_parameter('hat_y_index', -1)
        self.declare_parameter('triangle_index', -1)
        self.declare_parameter('step_duration_s', 0.25)
        self.declare_parameter('gap_duration_s', 0.05)
        self.declare_parameter('async_playback', True)

        # Retrieve Parameter Values
        joy_topic = self._get_param_val('joy_topic', '/joy')
        freq_topic = self._get_param_val('frequency_topic', '/buzzer/frequency')
        seq_topic = self._get_param_val('play_sequence_topic', '/buzzer/play_sequence')
        status_topic = self._get_param_val('status_topic', '/buzzer/status')

        control_map_path = str(
            self._get_param_val('control_map_path', '') or ''
        )
        self._control_map = self._load_control_map(control_map_path)
        profile = self._control_map.profile('ps5_bluetooth')
        self.L1_INDEX = self._map_index('l1_index', 'l1', 4)
        self.R1_INDEX = self._map_index('r1_index', 'r1', 5)
        self.HAT_X_INDEX = self._map_axis_index(
            'hat_x_index', profile, 'dpad_x_axis', 6
        )
        self.HAT_Y_INDEX = self._map_axis_index(
            'hat_y_index', profile, 'dpad_y_axis', 7
        )
        self.TRIANGLE_INDEX = self._map_index('triangle_index', 'triangle', 2)
        self.step_duration_s = float(self._get_param_val('step_duration_s', 0.25))
        self.gap_duration_s = float(self._get_param_val('gap_duration_s', 0.05))
        self.async_playback = bool(self._get_param_val('async_playback', True))

        # Publishers & Subscribers
        self.joy_sub = self.create_subscription(Joy, joy_topic, self.joy_callback, 10)
        self.freq_pub = self.create_publisher(Int32, freq_topic, 10)
        self.sequence_pub = self.create_publisher(Int32MultiArray, seq_topic, 10)
        self.status_pub = self.create_publisher(String, status_topic, 10)

        # Internal State
        self.song_sequence: List[int] = []
        self.prev_axes: List[float] = []
        self.prev_buttons: List[int] = []
        self._playback_thread: Optional[threading.Thread] = None

        self.get_logger().info("Buzzer Modular Song Creator Initialized.")
        self.get_logger().info("Use D-Pad to play notes. Hold L1 (Low), R1 (High), or L1+R1 (Commands/Easter Egg).")

    def _get_param_val(self, name: str, default):
        try:
            param = self.get_parameter(name)
            if param and param.value is not None:
                return param.value
        except Exception:
            pass
        return default

    def _load_control_map(self, configured_path: str) -> ControlMap:
        """Load the shared controller map for audio/operator inputs."""
        candidates = []
        if configured_path:
            candidates.append(Path(configured_path))
        candidates.append(
            Path(__file__).resolve().parents[2]
            / 'robot_control'
            / 'config'
            / 'control_map.yaml'
        )
        try:
            from ament_index_python.packages import get_package_share_directory

            candidates.append(
                Path(get_package_share_directory('robot_control'))
                / 'config'
                / 'control_map.yaml'
            )
        except (ImportError, LookupError, RuntimeError):
            pass
        for candidate in candidates:
            if not candidate.is_file():
                continue
            try:
                return load_control_map(candidate)
            except (OSError, ValueError, ImportError) as error:
                self.get_logger().warn(
                    f'Unable to load control map {candidate}: {error}'
                )
        self.get_logger().warn('Using built-in canonical audio control map')
        return default_control_map()

    def _map_index(self, parameter: str, map_key: str, fallback: int) -> int:
        """Use an explicit compatibility override or a mapped button index."""
        value = int(self._get_param_val(parameter, -1))
        return value if value >= 0 else int(
            self._control_map.button_indices.get(map_key, fallback)
        )

    def _map_axis_index(
        self,
        parameter: str,
        profile,
        map_key: str,
        fallback: int,
    ) -> int:
        """Use an explicit compatibility override or a mapped axis index."""
        value = int(self._get_param_val(parameter, -1))
        return value if value >= 0 else int(profile.get(map_key, fallback))

    def joy_callback(self, msg: Joy):
        """Process incoming joystick messages and handle modifier / note triggers."""
        # Ensure proper initialization of previous state tracking
        if not self.prev_axes or len(self.prev_axes) != len(msg.axes):
            self.prev_axes = list(msg.axes)
        if not self.prev_buttons or len(self.prev_buttons) != len(msg.buttons):
            self.prev_buttons = list(msg.buttons)
            return

        # Bound check indices
        max_btn_idx = max(self.L1_INDEX, self.R1_INDEX, self.TRIANGLE_INDEX)
        max_axis_idx = max(self.HAT_X_INDEX, self.HAT_Y_INDEX)
        if len(msg.buttons) <= max_btn_idx or len(msg.axes) <= max_axis_idx:
            return

        # Read Modifier States
        l1_held = bool(msg.buttons[self.L1_INDEX])
        r1_held = bool(msg.buttons[self.R1_INDEX])

        # Button and D-Pad Edge Triggers (Rising Edges Only)
        triangle_pressed = (msg.buttons[self.TRIANGLE_INDEX] == 1) and (self.prev_buttons[self.TRIANGLE_INDEX] == 0)

        dpad_up = (msg.axes[self.HAT_Y_INDEX] > 0.5) and not (self.prev_axes[self.HAT_Y_INDEX] > 0.5)
        dpad_down = (msg.axes[self.HAT_Y_INDEX] < -0.5) and not (self.prev_axes[self.HAT_Y_INDEX] < -0.5)
        dpad_left = (msg.axes[self.HAT_X_INDEX] > 0.5) and not (self.prev_axes[self.HAT_X_INDEX] > 0.5)
        dpad_right = (msg.axes[self.HAT_X_INDEX] < -0.5) and not (self.prev_axes[self.HAT_X_INDEX] < -0.5)

        # Update previous states
        self.prev_axes = list(msg.axes)
        self.prev_buttons = list(msg.buttons)

        # Mode Selection Logic
        if l1_held and r1_held:
            # === COMMAND MODE & EASTER EGG ===
            if triangle_pressed:
                self.play_sea_shanty()
            elif dpad_up:
                self.play_full_sequence()
            elif dpad_down:
                self.clear_sequence()
            elif dpad_left:
                self.undo_last_note()
            elif dpad_right:
                self.add_note('REST')
        else:
            # === NOTE PLAYING & RECORDING MODE ===
            octave = "4"
            if l1_held:
                octave = "3"
            elif r1_held:
                octave = "5"

            if dpad_up:
                self.add_note(f'C{octave}')
            elif dpad_right:
                self.add_note(f'D{octave}')
            elif dpad_down:
                self.add_note(f'E{octave}')
            elif dpad_left:
                self.add_note(f'F{octave}')

    def add_note(self, note_name: str):
        """Append a note to the song sequence and trigger immediate acoustic feedback."""
        freq = NOTE_FREQ.get(note_name, 0)
        self.song_sequence.append(freq)

        # Live feedback output to hardware
        self.publish_tone(freq)

        log_msg = f"Recorded Note: {note_name} ({freq} Hz) | Song Length: {len(self.song_sequence)}"
        self.get_logger().info(log_msg)
        self.publish_status(log_msg)

    def undo_last_note(self):
        """Remove the most recently added note from the sequence."""
        if self.song_sequence:
            removed = self.song_sequence.pop()
            log_msg = f"Removed last note ({removed} Hz). Remaining steps: {len(self.song_sequence)}"
        else:
            log_msg = "Sequence is already empty."
        self.get_logger().info(log_msg)
        self.publish_status(log_msg)

    def clear_sequence(self):
        """Clear the entire sequence and give acoustic confirmation."""
        self.song_sequence.clear()
        self.publish_tone(100)  # Short low chime for clear feedback
        time.sleep(0.1)
        self.publish_tone(0)
        log_msg = "Song sequence cleared."
        self.get_logger().info(log_msg)
        self.publish_status(log_msg)

    def play_full_sequence(self):
        """Publish the current song sequence and play it back."""
        if not self.song_sequence:
            self.get_logger().warn("Cannot play: Song sequence is empty!")
            self.publish_status("Cannot play: Song sequence is empty!")
            return

        log_msg = f"Playing sequence of {len(self.song_sequence)} notes..."
        self.get_logger().info(log_msg)
        self.publish_status(log_msg)

        # Publish sequence as array for low-level execution (STM32 / ESP32)
        seq_msg = Int32MultiArray()
        seq_msg.data = list(self.song_sequence)
        self.sequence_pub.publish(seq_msg)

        # Local audio playback
        self._execute_playback(list(self.song_sequence))

    def play_sea_shanty(self):
        """Easter Egg trigger: Play the Sea Shanty 2 theme from OSRS."""
        log_msg = "Easter Egg Triggered: Playing Sea Shanty 2!"
        self.get_logger().info(log_msg)
        self.publish_status(log_msg)

        seq_msg = Int32MultiArray()
        seq_msg.data = list(SEA_SHANTY_2_SEQ)
        self.sequence_pub.publish(seq_msg)

        # Local audio playback
        self._execute_playback(list(SEA_SHANTY_2_SEQ))

    def _execute_playback(self, sequence: List[int]):
        """Execute playback either asynchronously or synchronously based on config."""
        if self.async_playback:
            self._playback_thread = threading.Thread(
                target=self._play_tones_worker,
                args=(sequence, self.step_duration_s, self.gap_duration_s),
                daemon=True,
            )
            self._playback_thread.start()
        else:
            self._play_tones_worker(sequence, self.step_duration_s, self.gap_duration_s)

    def _play_tones_worker(self, sequence: List[int], step_dur: float, gap_dur: float):
        """Iterate through frequencies and publish tone and silence intervals."""
        for freq in sequence:
            self.publish_tone(freq)
            time.sleep(step_dur)
            self.publish_tone(0)
            time.sleep(gap_dur)

    def publish_tone(self, frequency: int):
        """Publish a single frequency tone (in Hz) to /buzzer/frequency."""
        msg = Int32()
        msg.data = int(frequency)
        self.freq_pub.publish(msg)

    def publish_status(self, text: str):
        """Publish status message string to /buzzer/status."""
        msg = String()
        msg.data = str(text)
        self.status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = BuzzerSongCreator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
