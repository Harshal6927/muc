# Copyright (c) 2025. All rights reserved.
"""Tests for the memory module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from src.memory import MemoryMonitor, MemoryStats, StreamingPlayer, get_object_size, should_stream


class TestMemoryStats:
    """Tests for MemoryStats dataclass."""

    def test_create_stats(self) -> None:
        """Test creating MemoryStats."""
        stats = MemoryStats(
            cache_mb=50.0,
            total_objects=1000,
            numpy_arrays=5,
            estimated_numpy_mb=25.0,
        )

        assert stats.cache_mb == 50.0
        assert stats.total_objects == 1000
        assert stats.numpy_arrays == 5
        assert stats.estimated_numpy_mb == 25.0


class TestMemoryMonitor:
    """Tests for MemoryMonitor class."""

    def test_get_stats(self) -> None:
        """Test getting memory statistics."""
        mock_manager = MagicMock()
        mock_cache = MagicMock()
        mock_cache.stats = {"size_mb": 10.0}
        mock_manager._cache = mock_cache

        monitor = MemoryMonitor(mock_manager)
        stats = monitor.get_stats()

        assert isinstance(stats, MemoryStats)
        assert stats.cache_mb == 10.0
        assert stats.total_objects > 0

    def test_get_stats_without_cache(self) -> None:
        """Test getting stats when cache not available."""
        mock_manager = MagicMock(spec=[])  # No _cache attribute

        monitor = MemoryMonitor(mock_manager)
        stats = monitor.get_stats()

        assert stats.cache_mb == 0.0

    def test_cleanup_normal(self) -> None:
        """Test normal cleanup."""
        mock_manager = MagicMock(spec=[])

        monitor = MemoryMonitor(mock_manager)
        collected = monitor.cleanup(aggressive=False)

        assert collected >= 0

    def test_cleanup_aggressive(self) -> None:
        """Test aggressive cleanup clears cache."""
        mock_manager = MagicMock()
        mock_cache = MagicMock()
        mock_manager._cache = mock_cache

        monitor = MemoryMonitor(mock_manager)
        monitor.cleanup(aggressive=True)

        mock_cache.clear.assert_called_once()


class TestGetObjectSize:
    """Tests for get_object_size function."""

    def test_numpy_array(self) -> None:
        """Test size of numpy array."""
        arr = np.zeros((100,), dtype=np.float32)
        size = get_object_size(arr)

        assert size == arr.nbytes
        assert size == 400  # 100 * 4 bytes

    def test_regular_object(self) -> None:
        """Test size of regular object."""
        obj = "hello"
        size = get_object_size(obj)

        assert size > 0


class TestStreamingPlayer:
    """Tests for StreamingPlayer class."""

    def test_init(self) -> None:
        """Test initialization."""
        mock_manager = MagicMock()
        player = StreamingPlayer(mock_manager)

        assert player.audio_manager == mock_manager
        assert not player.is_playing

    def test_stop_when_not_playing(self) -> None:
        """Test stop when not playing."""
        mock_manager = MagicMock()
        player = StreamingPlayer(mock_manager)

        # Should not raise
        player.stop()
        assert not player.is_playing

    def test_get_output_channels_with_device(self) -> None:
        """Test getting output channels with device."""
        mock_manager = MagicMock()
        mock_manager.output_device_id = 1

        player = StreamingPlayer(mock_manager)

        with patch("src.memory.sd.query_devices") as mock_query:
            mock_query.return_value = {"max_output_channels": 6}

            channels = player._get_output_channels()
            assert channels == 6

    def test_get_output_channels_no_device(self) -> None:
        """Test getting output channels without device."""
        mock_manager = MagicMock()
        mock_manager.output_device_id = None

        player = StreamingPlayer(mock_manager)
        channels = player._get_output_channels()

        assert channels == 2  # Default stereo

    def test_adjust_channels_expand_mono(self) -> None:
        """Test expanding mono to stereo."""
        mock_manager = MagicMock()
        player = StreamingPlayer(mock_manager)

        mono = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        stereo = player._adjust_channels(mono, 2)

        assert stereo.shape == (3, 2)

    def test_adjust_channels_reduce(self) -> None:
        """Test reducing channels."""
        mock_manager = MagicMock()
        player = StreamingPlayer(mock_manager)

        stereo = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)
        mono = player._adjust_channels(stereo, 1)

        assert mono.shape == (2, 1)

    def test_play_streaming_success(self, tmp_path: Path) -> None:
        """Test successful streaming playback."""
        mock_manager = MagicMock()
        mock_manager.output_device_id = 0

        player = StreamingPlayer(mock_manager)
        test_file = tmp_path / "test.wav"
        test_file.touch()

        mock_sf = MagicMock()
        mock_sf.samplerate = 44100

        mock_stream = MagicMock()

        with (
            patch("src.memory.sf.SoundFile", return_value=mock_sf),
            patch(
                "src.memory.sd.OutputStream",
                return_value=mock_stream,
            ),
            patch("src.memory.sd.query_devices", return_value={"max_output_channels": 2}),
        ):
            result = player.play_streaming(test_file)

            assert result is True
            assert player.is_playing
            mock_stream.start.assert_called_once()

    def test_play_streaming_error(self, tmp_path: Path) -> None:
        """Test streaming playback with error."""
        mock_manager = MagicMock()
        mock_manager.output_device_id = 0

        player = StreamingPlayer(mock_manager)
        test_file = tmp_path / "test.wav"
        test_file.touch()

        with patch("src.memory.sf.SoundFile", side_effect=Exception("Error")):
            result = player.play_streaming(test_file)

            assert result is False
            assert not player.is_playing


class TestShouldStream:
    """Tests for should_stream function."""

    def test_small_file(self, tmp_path: Path) -> None:
        """Test small file should not stream."""
        small_file = tmp_path / "small.wav"
        small_file.write_bytes(b"x" * 1000)  # 1 KB

        assert should_stream(small_file, threshold_mb=10.0) is False

    def test_large_file(self, tmp_path: Path) -> None:
        """Test large file should stream."""
        large_file = tmp_path / "large.wav"
        # Create 11 MB file
        large_file.write_bytes(b"x" * (11 * 1024 * 1024))

        assert should_stream(large_file, threshold_mb=10.0) is True

    def test_missing_file(self, tmp_path: Path) -> None:
        """Test missing file returns False."""
        missing = tmp_path / "missing.wav"
        assert should_stream(missing) is False

    def test_custom_threshold(self, tmp_path: Path) -> None:
        """Test custom threshold."""
        medium_file = tmp_path / "medium.wav"
        medium_file.write_bytes(b"x" * (6 * 1024 * 1024))  # 6 MB

        assert should_stream(medium_file, threshold_mb=5.0) is True
        assert should_stream(medium_file, threshold_mb=10.0) is False
