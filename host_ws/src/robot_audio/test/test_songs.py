"""Unit tests for songs module and musical frequency mappings."""

import pytest
from robot_audio.songs import NOTE_FREQ, SEA_SHANTY_2_SEQ, SEA_SHANTY_2_FULL_MELODY, notes_to_frequencies


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
    """Verify Sea Shanty 2 sequence contains correct note frequencies for A Major melody."""
    assert len(SEA_SHANTY_2_SEQ) >= 16
    # First phrase: A4 (440), C#5 (554), E5 (659), F#5 (740), E5 (659), C#5 (554), A4 (440), C#5 (554)
    expected_intro = [440, 554, 659, 740, 659, 554, 440, 554]
    assert SEA_SHANTY_2_SEQ[:8] == expected_intro


def test_notes_to_frequencies_conversion():
    """Verify string note list conversion to Hertz list."""
    notes = ['C4', 'E4', 'G4', 'REST', 'A4']
    freqs = notes_to_frequencies(notes)
    assert freqs == [262, 330, 392, 0, 440]
