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

# Short, named melodies used by the Foxglove command topic and the controller
# cycle button. Durations use the Arduino convention from the supplied
# examples: 4 is a quarter note, 8 is an eighth note, and the base tempo is
# 60 BPM (1000 / denominator milliseconds).
HAPPY_BIRTHDAY_BPM = 60
HAPPY_BIRTHDAY_NOTE_MELODY: List[Tuple[str, int]] = [
    ('C4', 4), ('C4', 8), ('D4', 4), ('C4', 4), ('F4', 4), ('E4', 2),
    ('C4', 4), ('C4', 8), ('D4', 4), ('C4', 4), ('G4', 4), ('F4', 2),
    ('C4', 4), ('C4', 8), ('C5', 4), ('A4', 4), ('F4', 4), ('E4', 4),
    ('D4', 4), ('A#4', 4), ('A#4', 8), ('A4', 4), ('F4', 4), ('G4', 4),
    ('F4', 2),
]

IMPERIAL_MARCH_BPM = 60
IMPERIAL_MARCH_NOTE_MELODY: List[Tuple[str, int]] = [
    ('A3', 4), ('A3', 4), ('A3', 4), ('F3', 8), ('C4', 32),
    ('A3', 4), ('F3', 8), ('C4', 32), ('A3', 2),
    ('E4', 4), ('E4', 4), ('E4', 4), ('F4', 8), ('C4', 32),
    ('G#3', 4), ('F3', 8), ('C4', 32), ('A3', 2),
]


def _parallel_melody_arrays(
    note_melody: List[Tuple[str, int]],
) -> Tuple[List[int], List[int]]:
    """Return the parallel frequency and duration arrays used by the player."""
    return (
        [NOTE_FREQ.get(note, 0) for note, _ in note_melody],
        [int(duration) for _, duration in note_melody],
    )


HAPPY_BIRTHDAY_FREQUENCIES, HAPPY_BIRTHDAY_DURATIONS = _parallel_melody_arrays(
    HAPPY_BIRTHDAY_NOTE_MELODY
)
IMPERIAL_MARCH_FREQUENCIES, IMPERIAL_MARCH_DURATIONS = _parallel_melody_arrays(
    IMPERIAL_MARCH_NOTE_MELODY
)
HAPPY_BIRTHDAY_MELODY: List[Tuple[int, int]] = list(
    zip(HAPPY_BIRTHDAY_FREQUENCIES, HAPPY_BIRTHDAY_DURATIONS)
)
IMPERIAL_MARCH_MELODY: List[Tuple[int, int]] = list(
    zip(IMPERIAL_MARCH_FREQUENCIES, IMPERIAL_MARCH_DURATIONS)
)

# OSRS Sea Shanty 2 (Port Sarim theme), using the operator-supplied Arduino
# transcription. Every duration is a count of 16th-note grid cells. Keeping
# this representation explicit prevents denominator conversions and timing
# drift between the host player and the STM32 player.
SEA_SHANTY_2_BPM = 105
SEA_SHANTY_2_SIXTEENTH_NOTE_MS = (60000 // SEA_SHANTY_2_BPM) // 4
SEA_SHANTY_2_ARTICULATION_PERCENT = 90
SEA_SHANTY_2_LOOP_DELAY_MS = 2000
# Compatibility value for callers that need the 10% gap of one grid cell.
# Actual playback derives the gap from each note's complete duration.
SEA_SHANTY_2_ARTICULATION_MS = (
    SEA_SHANTY_2_SIXTEENTH_NOTE_MS
    * (100 - SEA_SHANTY_2_ARTICULATION_PERCENT)
    // 100
)
SEA_SHANTY_2_NOTE_MELODY: List[Tuple[str, int]] = [
    # Pickup and measures 1-8
    ('A5', 2), ('E5', 2), ('D5', 2), ('C#5', 6),
    ('C#5', 2), ('D5', 2), ('E5', 2), ('F#5', 2), ('G#5', 2), ('E5', 6),
    ('REST', 4),
    ('F#5', 2), ('E5', 2), ('D5', 2), ('C#5', 6),
    ('C#5', 2), ('B4', 2), ('C#5', 2), ('D5', 8),
    ('REST', 4),
    ('A5', 2), ('E5', 2), ('D5', 2), ('C#5', 6),
    ('C#5', 2), ('D5', 2), ('E5', 2), ('F#5', 4), ('D5', 4),
    ('REST', 4),
    ('F#5', 2), ('E5', 2), ('D5', 2), ('C#5', 4), ('B4', 2),
    ('C#5', 2), ('D5', 4), ('F#5', 2), ('E5', 2), ('C#5', 2), ('B4', 2),
    ('A4', 8), ('REST', 8),

    # Measures 9-12: high section
    ('A5', 2), ('B5', 2), ('C#6', 4), ('C#6', 2), ('B5', 2),
    ('A5', 2), ('G#5', 4),
    ('E5', 2), ('F#5', 2), ('G#5', 4), ('G#5', 2), ('F#5', 2),
    ('E5', 2), ('D5', 4),
    ('C#5', 2), ('D5', 2), ('E5', 4), ('C#5', 2), ('D5', 2),
    ('E5', 2), ('F#5', 2),
    ('E5', 2), ('D5', 2), ('C#5', 2), ('B4', 4), ('A4', 8),
]


SEA_SHANTY_2_MELODY: List[Tuple[int, int]] = [
    (NOTE_FREQ[note], duration) for note, duration in SEA_SHANTY_2_NOTE_MELODY
]
SEA_SHANTY_2_DURATIONS_MS: List[int] = [
    duration * SEA_SHANTY_2_SIXTEENTH_NOTE_MS
    for _, duration in SEA_SHANTY_2_NOTE_MELODY
]

# Compatibility form for the existing ROS Int32MultiArray topic. Playback uses
# the timed melody above so rests and grid timing are retained locally.
SEA_SHANTY_2_SEQ: List[int] = [frequency for frequency, _ in SEA_SHANTY_2_MELODY]
SEA_SHANTY_2_FULL_MELODY: List[int] = list(SEA_SHANTY_2_SEQ)

# The value is ``(timed melody, BPM)``. Sea Shanty 2 is represented in 16th
# note grid cells and is handled separately by the player for compatibility.
PRESET_MELODIES = {
    'happy_birthday': (HAPPY_BIRTHDAY_MELODY, HAPPY_BIRTHDAY_BPM),
    'imperial_march': (IMPERIAL_MARCH_MELODY, IMPERIAL_MARCH_BPM),
    'sea_shanty_2': (SEA_SHANTY_2_MELODY, SEA_SHANTY_2_BPM),
}
PRESET_MELODY_NAMES = tuple(PRESET_MELODIES)


def notes_to_frequencies(notes: List[str]) -> List[int]:
    """Convert a list of note names into corresponding frequencies in Hz."""
    return [NOTE_FREQ.get(n.strip().upper(), 0) for n in notes]
