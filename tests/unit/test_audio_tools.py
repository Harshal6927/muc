# Copyright (c) 2025. All rights reserved.
"""Unit tests for audio_tools module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.audio_tools import AudioNormalizer, AudioTrimmer


class TestAudioTrimmerParseTimeToSeconds:
    """Tests for AudioTrimmer.parse_time_to_seconds method."""

    def test_parses_seconds_only(self) -> None:
        """Should parse seconds-only format."""
        assert AudioTrimmer.parse_time_to_seconds("30") == 30.0
        assert AudioTrimmer.parse_time_to_seconds("0") == 0.0
        assert AudioTrimmer.parse_time_to_seconds("120") == 120.0

    def test_parses_seconds_with_decimal(self) -> None:
        """Should parse seconds with decimal."""
        assert AudioTrimmer.parse_time_to_seconds("30.5") == 30.5
        assert AudioTrimmer.parse_time_to_seconds("0.25") == 0.25

    def test_parses_minutes_seconds(self) -> None:
        """Should parse MM:SS format."""
        assert AudioTrimmer.parse_time_to_seconds("1:30") == 90.0
        assert AudioTrimmer.parse_time_to_seconds("2:00") == 120.0
        assert AudioTrimmer.parse_time_to_seconds("0:45") == 45.0

    def test_parses_minutes_seconds_with_decimal(self) -> None:
        """Should parse MM:SS.ms format."""
        assert AudioTrimmer.parse_time_to_seconds("1:30.5") == 90.5
        assert AudioTrimmer.parse_time_to_seconds("0:00.25") == 0.25

    def test_parses_hours_minutes_seconds(self) -> None:
        """Should parse HH:MM:SS format."""
        assert AudioTrimmer.parse_time_to_seconds("1:00:00") == 3600.0
        assert AudioTrimmer.parse_time_to_seconds("0:01:30") == 90.0
        assert AudioTrimmer.parse_time_to_seconds("1:30:45") == 5445.0

    def test_handles_whitespace(self) -> None:
        """Should handle leading/trailing whitespace."""
        assert AudioTrimmer.parse_time_to_seconds("  30  ") == 30.0
        assert AudioTrimmer.parse_time_to_seconds("  1:30  ") == 90.0

    def test_raises_on_invalid_format(self) -> None:
        """Should raise ValueError for invalid format."""
        with pytest.raises(ValueError):
            AudioTrimmer.parse_time_to_seconds("1:2:3:4")


class TestAudioTrimmerFormatSeconds:
    """Tests for AudioTrimmer.format_seconds method."""

    def test_formats_seconds(self) -> None:
        """Should format seconds to M:SS.ms format."""
        assert AudioTrimmer.format_seconds(30) == "0:30.00"
        assert AudioTrimmer.format_seconds(90) == "1:30.00"
        assert AudioTrimmer.format_seconds(0) == "0:00.00"

    def test_formats_with_milliseconds(self) -> None:
        """Should include milliseconds."""
        assert AudioTrimmer.format_seconds(30.5) == "0:30.50"
        assert AudioTrimmer.format_seconds(90.25) == "1:30.25"

    def test_formats_large_values(self) -> None:
        """Should handle large values."""
        assert AudioTrimmer.format_seconds(3600) == "60:00.00"  # 1 hour


class TestAudioTrimmerGetDuration:
    """Tests for AudioTrimmer.get_duration method."""

    def test_returns_duration(self, temp_dir: Path) -> None:
        """Should return file duration."""
        trimmer = AudioTrimmer()
        test_file = temp_dir / "test.wav"
        test_file.touch()

        mock_info = MagicMock()
        mock_info.duration = 5.5

        with patch("src.audio_tools.sf.info", return_value=mock_info):
            result = trimmer.get_duration(test_file)

        assert result == 5.5


class TestAudioTrimmerTrim:
    """Tests for AudioTrimmer.trim method."""

    @pytest.fixture
    def mock_audio_data(self) -> tuple[np.ndarray, int]:
        """Create mock stereo audio data (5 seconds at 44100Hz).

        Returns:
            Tuple of (audio data array, sample rate).

        """
        samplerate = 44100
        duration = 5  # seconds
        samples = samplerate * duration
        rng = np.random.default_rng(42)
        data = rng.random((samples, 2), dtype=np.float32)
        return data, samplerate

    def test_trims_audio(self, temp_dir: Path, mock_audio_data: tuple[np.ndarray, int]) -> None:
        """Should trim audio to specified range."""
        trimmer = AudioTrimmer()
        input_file = temp_dir / "input.wav"
        input_file.touch()

        data, samplerate = mock_audio_data

        with (
            patch("src.audio_tools.sf.read", return_value=(data, samplerate)),
            patch("src.audio_tools.sf.write") as mock_write,
        ):
            result = trimmer.trim(input_file, start=1.0, end=3.0)

        assert result.name == "input_trimmed.wav"
        # Check that sf.write was called
        mock_write.assert_called_once()
        # Check trimmed data length (2 seconds = 88200 samples)
        written_data = mock_write.call_args[0][1]
        assert len(written_data) == 88200

    def test_trims_with_custom_output(self, temp_dir: Path, mock_audio_data: tuple[np.ndarray, int]) -> None:
        """Should use custom output path when provided."""
        trimmer = AudioTrimmer()
        input_file = temp_dir / "input.wav"
        output_file = temp_dir / "output.wav"
        input_file.touch()

        data, samplerate = mock_audio_data

        with (
            patch("src.audio_tools.sf.read", return_value=(data, samplerate)),
            patch("src.audio_tools.sf.write"),
        ):
            result = trimmer.trim(input_file, output_path=output_file, start=0, end=1.0)

        assert result == output_file

    def test_trims_to_end_when_no_end_specified(self, temp_dir: Path, mock_audio_data: tuple[np.ndarray, int]) -> None:
        """Should trim to end of file when end is not specified."""
        trimmer = AudioTrimmer()
        input_file = temp_dir / "input.wav"
        input_file.touch()

        data, samplerate = mock_audio_data

        with (
            patch("src.audio_tools.sf.read", return_value=(data, samplerate)),
            patch("src.audio_tools.sf.write") as mock_write,
        ):
            trimmer.trim(input_file, start=3.0)

        # Check trimmed data length (2 seconds from 3s to 5s = 88200 samples)
        written_data = mock_write.call_args[0][1]
        assert len(written_data) == 88200

    def test_raises_on_start_exceeds_duration(self, temp_dir: Path, mock_audio_data: tuple[np.ndarray, int]) -> None:
        """Should raise ValueError when start exceeds duration."""
        trimmer = AudioTrimmer()
        input_file = temp_dir / "input.wav"
        input_file.touch()

        data, samplerate = mock_audio_data

        with (
            patch("src.audio_tools.sf.read", return_value=(data, samplerate)),
            pytest.raises(ValueError, match="exceeds audio duration"),
        ):
            trimmer.trim(input_file, start=10.0)

    def test_raises_on_start_after_end(self, temp_dir: Path, mock_audio_data: tuple[np.ndarray, int]) -> None:
        """Should raise ValueError when start is after end."""
        trimmer = AudioTrimmer()
        input_file = temp_dir / "input.wav"
        input_file.touch()

        data, samplerate = mock_audio_data

        with (
            patch("src.audio_tools.sf.read", return_value=(data, samplerate)),
            pytest.raises(ValueError, match="Start time must be before end time"),
        ):
            trimmer.trim(input_file, start=3.0, end=1.0)

    def test_applies_fade_in(self, temp_dir: Path, mock_audio_data: tuple[np.ndarray, int]) -> None:
        """Should apply fade in effect."""
        trimmer = AudioTrimmer()
        input_file = temp_dir / "input.wav"
        input_file.touch()

        data, samplerate = mock_audio_data

        with (
            patch("src.audio_tools.sf.read", return_value=(data, samplerate)),
            patch("src.audio_tools.sf.write") as mock_write,
        ):
            trimmer.trim(input_file, start=0, end=2.0, fade_in=0.5)

        written_data = mock_write.call_args[0][1]
        # First sample should be near zero (faded)
        assert abs(written_data[0, 0]) < abs(data[0, 0])

    def test_applies_fade_out(self, temp_dir: Path, mock_audio_data: tuple[np.ndarray, int]) -> None:
        """Should apply fade out effect."""
        trimmer = AudioTrimmer()
        input_file = temp_dir / "input.wav"
        input_file.touch()

        data, samplerate = mock_audio_data

        with (
            patch("src.audio_tools.sf.read", return_value=(data, samplerate)),
            patch("src.audio_tools.sf.write") as mock_write,
        ):
            trimmer.trim(input_file, start=0, end=2.0, fade_out=0.5)

        written_data = mock_write.call_args[0][1]
        # Last sample should be near zero (faded)
        assert abs(written_data[-1, 0]) < 0.01


class TestAudioNormalizerAnalyze:
    """Tests for AudioNormalizer.analyze method."""

    def test_analyzes_stereo_audio(self, temp_dir: Path) -> None:
        """Should analyze stereo audio levels."""
        test_file = temp_dir / "test.wav"
        test_file.touch()

        # Create test data with known levels
        rng = np.random.default_rng(42)
        data = rng.random((44100, 2), dtype=np.float32) * 0.5  # Max ~0.5
        samplerate = 44100

        with patch("src.audio_tools.sf.read", return_value=(data, samplerate)):
            result = AudioNormalizer.analyze(test_file)

        assert "peak" in result
        assert "peak_db" in result
        assert "rms" in result
        assert "rms_db" in result
        assert "duration" in result
        assert "samplerate" in result
        assert "channels" in result

        assert result["channels"] == 2
        assert result["samplerate"] == 44100
        assert result["peak"] > 0
        assert result["rms"] > 0

    def test_analyzes_mono_audio(self, temp_dir: Path) -> None:
        """Should analyze mono audio levels."""
        test_file = temp_dir / "test.wav"
        test_file.touch()

        rng = np.random.default_rng(42)
        data = rng.random(44100, dtype=np.float32) * 0.8
        samplerate = 44100

        with patch("src.audio_tools.sf.read", return_value=(data, samplerate)):
            result = AudioNormalizer.analyze(test_file)

        assert result["channels"] == 1

    def test_handles_silent_audio(self, temp_dir: Path) -> None:
        """Should handle silent audio (all zeros)."""
        test_file = temp_dir / "test.wav"
        test_file.touch()

        data = np.zeros((44100, 2), dtype=np.float32)
        samplerate = 44100

        with patch("src.audio_tools.sf.read", return_value=(data, samplerate)):
            result = AudioNormalizer.analyze(test_file)

        assert result["peak"] == 0.0
        assert result["peak_db"] == float("-inf")


class TestAudioNormalizerNormalize:
    """Tests for AudioNormalizer.normalize method."""

    @pytest.fixture
    def mock_audio_data(self) -> tuple[np.ndarray, int]:
        """Create mock audio data with peak at 0.5 (-6 dB).

        Returns:
            Tuple of (audio data array, sample rate).

        """
        samplerate = 44100
        rng = np.random.default_rng(42)
        data = rng.random((44100, 2), dtype=np.float32) * 0.5
        return data, samplerate

    def test_normalizes_to_target_peak(self, temp_dir: Path, mock_audio_data: tuple[np.ndarray, int]) -> None:
        """Should normalize to target peak level."""
        normalizer = AudioNormalizer()
        input_file = temp_dir / "input.wav"
        input_file.touch()

        data, samplerate = mock_audio_data

        with (
            patch("src.audio_tools.sf.read", return_value=(data, samplerate)),
            patch("src.audio_tools.sf.write") as mock_write,
        ):
            result = normalizer.normalize(input_file, target_db=-3.0, mode="peak")

        assert result.name == "input_normalized.wav"
        mock_write.assert_called_once()

    def test_normalizes_with_rms_mode(self, temp_dir: Path, mock_audio_data: tuple[np.ndarray, int]) -> None:
        """Should normalize using RMS mode."""
        normalizer = AudioNormalizer()
        input_file = temp_dir / "input.wav"
        input_file.touch()

        data, samplerate = mock_audio_data

        with (
            patch("src.audio_tools.sf.read", return_value=(data, samplerate)),
            patch("src.audio_tools.sf.write") as mock_write,
        ):
            normalizer.normalize(input_file, target_db=-12.0, mode="rms")

        mock_write.assert_called_once()

    def test_normalizes_in_place(self, temp_dir: Path, mock_audio_data: tuple[np.ndarray, int]) -> None:
        """Should overwrite original when in_place=True."""
        normalizer = AudioNormalizer()
        input_file = temp_dir / "input.wav"
        input_file.touch()

        data, samplerate = mock_audio_data

        with (
            patch("src.audio_tools.sf.read", return_value=(data, samplerate)),
            patch("src.audio_tools.sf.write") as mock_write,
        ):
            result = normalizer.normalize(input_file, in_place=True)

        assert result == input_file
        # Check output path in write call
        assert mock_write.call_args[0][0] == str(input_file)

    def test_uses_custom_output_path(self, temp_dir: Path, mock_audio_data: tuple[np.ndarray, int]) -> None:
        """Should use custom output path when provided."""
        normalizer = AudioNormalizer()
        input_file = temp_dir / "input.wav"
        output_file = temp_dir / "custom_output.wav"
        input_file.touch()

        data, samplerate = mock_audio_data

        with (
            patch("src.audio_tools.sf.read", return_value=(data, samplerate)),
            patch("src.audio_tools.sf.write"),
        ):
            result = normalizer.normalize(input_file, output_path=output_file)

        assert result == output_file

    def test_raises_on_silent_audio(self, temp_dir: Path) -> None:
        """Should raise ValueError for silent audio."""
        normalizer = AudioNormalizer()
        input_file = temp_dir / "silent.wav"
        input_file.touch()

        data = np.zeros((44100, 2), dtype=np.float32)
        samplerate = 44100

        with (
            patch("src.audio_tools.sf.read", return_value=(data, samplerate)),
            pytest.raises(ValueError, match="silent"),
        ):
            normalizer.normalize(input_file)

    def test_clips_to_prevent_distortion(self, temp_dir: Path) -> None:
        """Should clip audio to prevent clipping distortion."""
        normalizer = AudioNormalizer()
        input_file = temp_dir / "input.wav"
        input_file.touch()

        # Audio that will exceed 1.0 after normalization to 0 dB
        rng = np.random.default_rng(42)
        data = rng.random((44100, 2), dtype=np.float32) * 0.1
        samplerate = 44100

        with (
            patch("src.audio_tools.sf.read", return_value=(data, samplerate)),
            patch("src.audio_tools.sf.write") as mock_write,
        ):
            normalizer.normalize(input_file, target_db=0.0)

        written_data = mock_write.call_args[0][1]
        # Ensure all values are clipped to [-1, 1]
        assert np.all(written_data >= -1.0)
        assert np.all(written_data <= 1.0)


class TestAudioNormalizerNormalizeBatch:
    """Tests for AudioNormalizer.normalize_batch method."""

    def test_normalizes_multiple_files(self, temp_dir: Path) -> None:
        """Should normalize multiple files."""
        normalizer = AudioNormalizer()

        files = [temp_dir / f"file{i}.wav" for i in range(3)]
        for f in files:
            f.touch()

        rng = np.random.default_rng(42)
        data = rng.random((44100, 2), dtype=np.float32) * 0.5
        samplerate = 44100

        with (
            patch("src.audio_tools.sf.read", return_value=(data, samplerate)),
            patch("src.audio_tools.sf.write"),
        ):
            results = normalizer.normalize_batch(files)

        assert len(results) == 3

    def test_calls_progress_callback(self, temp_dir: Path) -> None:
        """Should call progress callback for each file."""
        normalizer = AudioNormalizer()

        files = [temp_dir / f"file{i}.wav" for i in range(3)]
        for f in files:
            f.touch()

        rng = np.random.default_rng(42)
        data = rng.random((44100, 2), dtype=np.float32) * 0.5
        samplerate = 44100

        callback = MagicMock()

        with (
            patch("src.audio_tools.sf.read", return_value=(data, samplerate)),
            patch("src.audio_tools.sf.write"),
        ):
            normalizer.normalize_batch(files, progress_callback=callback)

        assert callback.call_count == 3

    def test_continues_on_error(self, temp_dir: Path) -> None:
        """Should continue processing after an error."""
        normalizer = AudioNormalizer()

        files = [temp_dir / f"file{i}.wav" for i in range(3)]
        for f in files:
            f.touch()

        rng = np.random.default_rng(42)
        data = rng.random((44100, 2), dtype=np.float32) * 0.5
        silent_data = np.zeros((44100, 2), dtype=np.float32)
        samplerate = 44100

        # First file will fail (silent), others will succeed
        call_count = [0]

        def mock_read(_path: str) -> tuple[np.ndarray, int]:
            call_count[0] += 1
            if call_count[0] == 1:
                return silent_data, samplerate
            return data, samplerate

        with (
            patch("src.audio_tools.sf.read", side_effect=mock_read),
            patch("src.audio_tools.sf.write"),
        ):
            results = normalizer.normalize_batch(files)

        # Should have 2 successful results (skipped the silent file)
        assert len(results) == 2
