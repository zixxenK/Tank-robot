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

# OSRS Sea Shanty 2 (Port Sarim theme), in the note/duration arrangement used
# by the original transcription.  One duration slot is one eighth note at
# 100 BPM (300 ms).  Keeping the rests and durations is important: a flat
# frequency list turns this into a different tune.
SEA_SHANTY_2_SLOT_MS = 300
SEA_SHANTY_2_MELODY: List[Tuple[int, int]] = [
    # Phrase 1 (measures 1-2)
    (880, 1), (659, 1), (587, 1), (554, 2), (554, 1), (587, 1),
    (659, 1), (740, 1), (831, 1), (659, 2), (0, 4),
    # Phrase 2 (measures 3-4)
    (740, 1), (659, 1), (587, 1), (554, 2), (554, 1), (494, 1),
    (554, 1), (587, 4), (0, 4),
    # Phrase 3 (measures 5-6)
    (880, 1), (659, 1), (587, 1), (554, 2), (554, 1), (587, 1),
    (659, 1), (740, 2), (587, 2), (0, 4),
    # Phrase 4 (measures 7-8)
    (740, 1), (659, 1), (587, 1), (554, 2), (494, 1), (554, 1),
    (587, 2), (740, 1), (659, 1), (554, 1), (494, 1), (440, 3),
]

# Compatibility form for the existing ROS Int32MultiArray topic.  Playback
# uses SEA_SHANTY_2_MELODY so the timing is retained locally.
SEA_SHANTY_2_SEQ: List[int] = [frequency for frequency, _ in SEA_SHANTY_2_MELODY]
SEA_SHANTY_2_FULL_MELODY: List[int] = list(SEA_SHANTY_2_SEQ)


def notes_to_frequencies(notes: List[str]) -> List[int]:
    """Convert a list of note names into corresponding frequencies in Hz."""
    return [NOTE_FREQ.get(n.strip().upper(), 0) for n in notes]
