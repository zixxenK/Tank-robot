"""Unit tests for songs module and musical frequency mappings."""

import pytest
from robot_audio.songs import (
    HAPPY_BIRTHDAY_DURATIONS,
    HAPPY_BIRTHDAY_FREQUENCIES,
    IMPERIAL_MARCH_DURATIONS,
    IMPERIAL_MARCH_FREQUENCIES,
    NOTE_FREQ,
    SEA_SHANTY_2_FULL_MELODY,
    SEA_SHANTY_2_MELODY,
    SEA_SHANTY_2_NOTE_MELODY,
    SEA_SHANTY_2_SEQ,
    SEA_SHANTY_2_BPM,
    SEA_SHANTY_2_DURATIONS_MS,
    SEA_SHANTY_2_SIXTEENTH_NOTE_MS,
    notes_to_frequencies,
)


def test_note_frequencies_octaves():
    """Verify standard frequency definitions for octaves 3, 4, 5 and rest."""
    assert NOTE_FREQ['REST'] == 0
    assert NOTE_FREQ['C3'] == 131
    assert NOTE_FREQ['D3'] == 147
    assert NOTE_FREQ['E3'] == 165
    assert NOTE_FREQ['F3'] == 175

    assert NOTE_FREQ['C4'] == 262
    assert NOTE_FREQ['D4'] == 294
    assert NOTE_FREQ['E4'] == 330
    assert NOTE_FREQ['F4'] == 349

    assert NOTE_FREQ['C5'] == 523
    assert NOTE_FREQ['D5'] == 587
    assert NOTE_FREQ['E5'] == 659
    assert NOTE_FREQ['F5'] == 698


def test_sea_shanty_2_sequence():
    """Verify the supplied Sea Shanty transcription, including rests."""
    assert SEA_SHANTY_2_BPM == 105
    assert SEA_SHANTY_2_SIXTEENTH_NOTE_MS == 142
    assert SEA_SHANTY_2_SEQ == [frequency for frequency, _ in SEA_SHANTY_2_MELODY]
    assert SEA_SHANTY_2_NOTE_MELODY[:5] == [
        ('A5', 2), ('E5', 2), ('D5', 2), ('C#5', 6), ('C#5', 2)
    ]
    assert SEA_SHANTY_2_MELODY[:5] == [
        (880, 2), (659, 2), (587, 2), (554, 6), (554, 2)
    ]
    assert SEA_SHANTY_2_DURATIONS_MS[:4] == [284, 284, 284, 852]
    assert (0, 4) in SEA_SHANTY_2_MELODY
    assert all(duration in (2, 4, 6, 8)
               for _, duration in SEA_SHANTY_2_NOTE_MELODY)
    assert all(duration == grid * SEA_SHANTY_2_SIXTEENTH_NOTE_MS
               for duration, (_, grid) in zip(
                   SEA_SHANTY_2_DURATIONS_MS, SEA_SHANTY_2_NOTE_MELODY))
    assert SEA_SHANTY_2_FULL_MELODY == SEA_SHANTY_2_SEQ


def test_notes_to_frequencies_conversion():
    """Verify string note list conversion to Hertz list."""
    notes = ['C4', 'E4', 'G4', 'REST', 'A4']
    freqs = notes_to_frequencies(notes)
    assert freqs == [262, 330, 392, 0, 440]


def test_preset_melodies_keep_parallel_frequency_and_duration_arrays():
    """The Arduino-style presets preserve one duration per frequency."""
    assert len(HAPPY_BIRTHDAY_FREQUENCIES) == len(HAPPY_BIRTHDAY_DURATIONS)
    assert HAPPY_BIRTHDAY_FREQUENCIES[:3] == [262, 262, 294]
    assert HAPPY_BIRTHDAY_DURATIONS[:3] == [4, 8, 4]
    assert len(IMPERIAL_MARCH_FREQUENCIES) == len(IMPERIAL_MARCH_DURATIONS)
    assert IMPERIAL_MARCH_FREQUENCIES[:3] == [220, 220, 220]
    assert IMPERIAL_MARCH_DURATIONS[:5] == [4, 4, 4, 8, 32]
