"""songs.py — Musical note frequencies and preset song sequences for buzzer audio."""

from typing import Dict, List, Tuple

# Musical note frequencies in Hertz (standard tuning A4 = 440Hz)
NOTE_FREQ: Dict[str, int] = {
    'REST': 0,
    '_': 0,
    'SILENCE': 0,

    # Octave 2
    'C2': 65, 'C#2': 69, 'Db2': 69, 'D2': 73, 'D#2': 78, 'Eb2': 78,
    'E2': 82, 'F2': 87, 'F#2': 92, 'Gb2': 92, 'G2': 98, 'G#2': 104,
    'Ab2': 104, 'A2': 110, 'A#2': 117, 'Bb2': 117, 'B2': 123,

    # Octave 3 (L1 Held modifier in standard D-Pad layout)
    'C3': 131, 'C#3': 139, 'Db3': 139, 'D3': 147, 'D#3': 156, 'Eb3': 156,
    'E3': 165, 'F3': 175, 'F#3': 185, 'Gb3': 185, 'G3': 196, 'G#3': 208,
    'Ab3': 208, 'A3': 220, 'A#3': 233, 'Bb3': 233, 'B3': 247,

    # Octave 4 (Base modifier in standard D-Pad layout)
    'C4': 262, 'C#4': 277, 'Db4': 277, 'D4': 294, 'D#4': 311, 'Eb4': 311,
    'E4': 330, 'F4': 349, 'F#4': 370, 'Gb4': 370, 'G4': 392, 'G#4': 415,
    'Ab4': 415, 'A4': 440, 'A#4': 466, 'Bb4': 466, 'B4': 494,

    # Octave 5 (R1 Held modifier in standard D-Pad layout)
    'C5': 523, 'C#5': 554, 'Db5': 554, 'D5': 587, 'D#5': 622, 'Eb5': 622,
    'E5': 659, 'F5': 698, 'F#5': 740, 'Gb5': 740, 'G5': 784, 'G#5': 831,
    'Ab5': 831, 'A5': 880, 'A#5': 932, 'Bb5': 932, 'B5': 988,

    # Octave 6
    'C6': 1047, 'C#6': 1109, 'D6': 1175, 'D#6': 1245, 'E6': 1319,
    'F6': 1397, 'F#6': 1480, 'G6': 1568, 'A6': 1760, 'B6': 1976,
}

# OSRS Sea Shanty 2 (Port Sarim theme), full A-D transcription supplied for
# this robot. Duration values use the Arduino convention: 2=half, 4=quarter,
# 8=eighth, 16=sixteenth, and a negative denominator is dotted.
SEA_SHANTY_2_BPM = 102
SEA_SHANTY_2_WHOLE_NOTE_MS = (60000 * 4) // SEA_SHANTY_2_BPM
SEA_SHANTY_2_ARTICULATION_MS = 12
SEA_SHANTY_2_NOTE_MELODY: List[Tuple[str, int]] = [
    # Section A: main theme
    ('A5', 8), ('E5', 8), ('D5', 8), ('C#5', -4),
    ('C#5', 8), ('D5', 8), ('E5', 8), ('F#5', 8), ('G#5', 8), ('E5', -4),
    ('REST', 4),
    ('F#5', 8), ('E5', 8), ('D5', 8), ('C#5', -4),
    ('C#5', 8), ('B4', 8), ('C#5', 8), ('D5', 2), ('REST', 4),
    ('A5', 8), ('E5', 8), ('D5', 8), ('C#5', -4),
    ('C#5', 8), ('D5', 8), ('E5', 8), ('F#5', 4), ('D5', 4), ('REST', 4),
    ('F#5', 8), ('E5', 8), ('D5', 8), ('C#5', 4), ('B4', 8),
    ('C#5', 8), ('D5', 4), ('F#5', 8), ('E5', 8), ('C#5', 8), ('B4', 8),
    ('A4', 2), ('REST', 4),

    # Section B: high synth lead counter-melody
    ('A5', 8), ('B5', 8), ('C#6', 4), ('C#6', 8), ('B5', 8), ('A5', 8), ('G#5', 4),
    ('E5', 8), ('F#5', 8), ('G#5', 4), ('G#5', 8), ('F#5', 8), ('E5', 8), ('D5', 4),
    ('C#5', 8), ('D5', 8), ('E5', 4), ('C#5', 8), ('D5', 8), ('E5', 8), ('F#5', 8),
    ('E5', 8), ('D5', 8), ('C#5', 8), ('B4', 4), ('A4', 2), ('REST', 4),
    ('A5', 8), ('B5', 8), ('C#6', 4), ('C#6', 8), ('B5', 8), ('A5', 8), ('G#5', 4),
    ('E5', 8), ('F#5', 8), ('G#5', 4), ('G#5', 8), ('F#5', 8), ('E5', 8), ('D5', 4),
    ('C#5', 8), ('D5', 8), ('E5', 8), ('F#5', 8), ('G#5', 8), ('A5', 8), ('B5', 8), ('C#6', 8),
    ('D6', 4), ('C#6', 4), ('A5', 2), ('REST', 4),

    # Section C: accordion solo and breakdown
    ('F#5', 16), ('G#5', 16), ('A5', 8), ('A5', 8), ('G#5', 8), ('F#5', 8), ('E5', 8),
    ('C#5', 8), ('D5', 8), ('E5', 8), ('E5', 8), ('D5', 8), ('C#5', 8), ('B4', 8),
    ('D5', 8), ('D5', 8), ('C#5', 8), ('B4', 8), ('A4', 8), ('B4', 8),
    ('C#5', 8), ('D5', 8), ('E5', 8), ('F#5', 8), ('G#5', 8), ('A5', 4),
    ('F#5', 16), ('G#5', 16), ('A5', 8), ('A5', 8), ('G#5', 8), ('F#5', 8), ('E5', 8),
    ('C#5', 8), ('D5', 8), ('E5', 8), ('E5', 8), ('D5', 8), ('C#5', 8), ('B4', 8),
    ('C#5', 8), ('D5', 8), ('E5', 8), ('F#5', 8), ('G#5', 8), ('A5', 8),
    ('B5', 8), ('C#6', 8), ('D6', 4), ('C#6', 4), ('A5', 2), ('REST', 4),

    # Section D: high flute climax run
    ('C#6', 8), ('D6', 8), ('E6', 4), ('E6', 8), ('D6', 8), ('C#6', 8), ('B5', 4),
    ('G#5', 8), ('A5', 8), ('B5', 4), ('B5', 8), ('A5', 8), ('G#5', 8), ('F#5', 4),
    ('E5', 8), ('F#5', 8), ('G#5', 8), ('A5', 8), ('B5', 8), ('C#6', 8), ('D6', 8), ('E6', 8),
    ('F#6', 4), ('E6', 4), ('C#6', 4), ('B5', 4), ('A5', 2), ('REST', 2),
]


def _duration_ms(duration_value: int) -> int:
    """Convert the supplied Arduino duration denominator to milliseconds."""
    denominator = abs(int(duration_value))
    duration = SEA_SHANTY_2_WHOLE_NOTE_MS // denominator
    return (duration * 3) // 2 if duration_value < 0 else duration


SEA_SHANTY_2_MELODY: List[Tuple[int, int]] = [
    (NOTE_FREQ[note], duration) for note, duration in SEA_SHANTY_2_NOTE_MELODY
]
SEA_SHANTY_2_DURATIONS_MS: List[int] = [
    _duration_ms(duration) for _, duration in SEA_SHANTY_2_NOTE_MELODY
]

# Compatibility form for the existing ROS Int32MultiArray topic. Playback uses
# the timed melody above so rests and legato timing are retained locally.
SEA_SHANTY_2_SEQ: List[int] = [frequency for frequency, _ in SEA_SHANTY_2_MELODY]
SEA_SHANTY_2_FULL_MELODY: List[int] = list(SEA_SHANTY_2_SEQ)


def notes_to_frequencies(notes: List[str]) -> List[int]:
    """Convert a list of note names into corresponding frequencies in Hz."""
    return [NOTE_FREQ.get(n.strip().upper(), 0) for n in notes]
