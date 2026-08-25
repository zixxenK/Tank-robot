"""Unit tests for songs module and musical frequency mappings."""

import pytest
from robot_audio.songs import (
    NOTE_FREQ,
    SEA_SHANTY_2_FULL_MELODY,
    SEA_SHANTY_2_MELODY,
    SEA_SHANTY_2_SEQ,
    SEA_SHANTY_2_SLOT_MS,
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
    assert SEA_SHANTY_2_SLOT_MS == 300
    assert SEA_SHANTY_2_SEQ == [frequency for frequency, _ in SEA_SHANTY_2_MELODY]
    assert SEA_SHANTY_2_MELODY[:5] == [
        (880, 1), (659, 1), (587, 1), (554, 2), (554, 1)
    ]
    assert (0, 4) in SEA_SHANTY_2_MELODY
    assert SEA_SHANTY_2_FULL_MELODY == SEA_SHANTY_2_SEQ


def test_notes_to_frequencies_conversion():
    """Verify string note list conversion to Hertz list."""
    notes = ['C4', 'E4', 'G4', 'REST', 'A4']
    freqs = notes_to_frequencies(notes)
    assert freqs == [262, 330, 392, 0, 440]
