# Copyright (c) 2025. All rights reserved.
"""Tests for the cache module."""

from pathlib import Path
from unittest.mock import patch

import numpy as np

from src.cache import CachedAudio, LRUAudioCache


class TestCachedAudio:
    """Tests for CachedAudio dataclass."""

    def test_create_cached_audio(self) -> None:
        """Test creating a CachedAudio instance."""
        data = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)
        cached = CachedAudio(
            data=data,
            samplerate=44100,
            size_bytes=data.nbytes,
            path=Path("test.wav"),
        )

        assert cached.samplerate == 44100
        assert cached.size_bytes == data.nbytes
        assert cached.path == Path("test.wav")
        assert cached.access_count == 0
        assert np.array_equal(cached.data, data)

    def test_from_file(self, tmp_path: Path) -> None:
        """Test loading from file."""
        # Create a mock audio file
        test_file = tmp_path / "test.wav"
        test_data = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)

        with patch("src.cache.sf.read") as mock_read:
            mock_read.return_value = (test_data, 44100)

            cached = CachedAudio.from_file(test_file)

            assert cached.samplerate == 44100
            assert np.array_equal(cached.data, test_data)
            assert cached.path == test_file
            mock_read.assert_called_once_with(str(test_file), dtype="float32")


class TestLRUAudioCache:
    """Tests for LRUAudioCache."""

    def test_init_default_size(self) -> None:
        """Test initialization with default size."""
        cache = LRUAudioCache()
        assert cache.max_size_bytes == 100 * 1024 * 1024  # 100 MB

    def test_init_custom_size(self) -> None:
        """Test initialization with custom size."""
        cache = LRUAudioCache(max_size_bytes=50 * 1024 * 1024)
        assert cache.max_size_bytes == 50 * 1024 * 1024

    def test_put_and_get(self) -> None:
        """Test putting and getting cached audio."""
        cache = LRUAudioCache()
        data = np.array([[0.1, 0.2]], dtype=np.float32)
        cached = CachedAudio(
            data=data,
            samplerate=44100,
            size_bytes=data.nbytes,
            path=Path("test.wav"),
        )

        cache.put("test.wav", cached)
        result = cache.get("test.wav")

        assert result is not None
        assert result.samplerate == 44100
        assert np.array_equal(result.data, data)

    def test_get_nonexistent(self) -> None:
        """Test getting nonexistent key."""
        cache = LRUAudioCache()
        result = cache.get("nonexistent.wav")
        assert result is None

    def test_get_updates_access_count(self) -> None:
        """Test that get updates access count."""
        cache = LRUAudioCache()
        data = np.array([[0.1]], dtype=np.float32)
        cached = CachedAudio(
            data=data,
            samplerate=44100,
            size_bytes=data.nbytes,
            path=Path("test.wav"),
        )

        cache.put("test.wav", cached)
        cache.get("test.wav")
        cache.get("test.wav")

        result = cache.get("test.wav")
        assert result is not None
        assert result.access_count == 3

    def test_eviction_on_size_limit(self) -> None:
        """Test that old items are evicted when size limit reached."""
        # Small cache that can hold only one item
        cache = LRUAudioCache(max_size_bytes=100)

        data1 = np.zeros((10,), dtype=np.float32)  # 40 bytes
        cached1 = CachedAudio(
            data=data1,
            samplerate=44100,
            size_bytes=data1.nbytes,
            path=Path("test1.wav"),
        )

        data2 = np.zeros((20,), dtype=np.float32)  # 80 bytes
        cached2 = CachedAudio(
            data=data2,
            samplerate=44100,
            size_bytes=data2.nbytes,
            path=Path("test2.wav"),
        )

        cache.put("test1.wav", cached1)
        cache.put("test2.wav", cached2)

        # First item should be evicted
        assert "test1.wav" not in cache
        assert "test2.wav" in cache

    def test_lru_order(self) -> None:
        """Test that least recently used items are evicted first."""
        cache = LRUAudioCache(max_size_bytes=200)

        data = np.zeros((10,), dtype=np.float32)  # 40 bytes each

        # Add three items
        for i in range(3):
            cached = CachedAudio(
                data=data,
                samplerate=44100,
                size_bytes=data.nbytes,
                path=Path(f"test{i}.wav"),
            )
            cache.put(f"test{i}.wav", cached)

        # Access first item to make it recently used
        cache.get("test0.wav")

        # Add another item that causes eviction
        large_data = np.zeros((30,), dtype=np.float32)  # 120 bytes
        cached = CachedAudio(
            data=large_data,
            samplerate=44100,
            size_bytes=large_data.nbytes,
            path=Path("test3.wav"),
        )
        cache.put("test3.wav", cached)

        # test1.wav should be evicted (least recently used)
        assert "test1.wav" not in cache
        # test0.wav should still be present (recently accessed)
        assert "test0.wav" in cache

    def test_clear(self) -> None:
        """Test clearing the cache."""
        cache = LRUAudioCache()
        data = np.array([[0.1]], dtype=np.float32)

        for i in range(3):
            cached = CachedAudio(
                data=data,
                samplerate=44100,
                size_bytes=data.nbytes,
                path=Path(f"test{i}.wav"),
            )
            cache.put(f"test{i}.wav", cached)

        cache.clear()

        assert len(cache) == 0
        assert cache.stats["entries"] == 0
        assert cache.stats["size_mb"] == 0

    def test_stats(self) -> None:
        """Test cache statistics."""
        cache = LRUAudioCache(max_size_bytes=1024 * 1024)
        data = np.zeros((100,), dtype=np.float32)

        cached = CachedAudio(
            data=data,
            samplerate=44100,
            size_bytes=data.nbytes,
            path=Path("test.wav"),
        )
        cache.put("test.wav", cached)

        # Miss
        cache.get("nonexistent.wav")
        # Hit
        cache.get("test.wav")

        stats = cache.stats

        assert stats["entries"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_preload(self, tmp_path: Path) -> None:
        """Test preloading multiple files."""
        cache = LRUAudioCache()
        files = [tmp_path / f"test{i}.wav" for i in range(3)]

        test_data = np.array([[0.1, 0.2]], dtype=np.float32)

        with patch("src.cache.sf.read") as mock_read:
            mock_read.return_value = (test_data, 44100)

            loaded = cache.preload(files)

            assert loaded == 3
            assert len(cache) == 3

    def test_preload_handles_errors(self, tmp_path: Path) -> None:
        """Test that preload handles file errors gracefully."""
        cache = LRUAudioCache()
        files = [tmp_path / "test.wav"]

        with patch("src.cache.sf.read", side_effect=Exception("Read error")):
            loaded = cache.preload(files)

            assert loaded == 0
            assert len(cache) == 0

    def test_contains(self) -> None:
        """Test __contains__ method."""
        cache = LRUAudioCache()
        data = np.array([[0.1]], dtype=np.float32)
        cached = CachedAudio(
            data=data,
            samplerate=44100,
            size_bytes=data.nbytes,
            path=Path("test.wav"),
        )

        cache.put("test.wav", cached)

        assert "test.wav" in cache
        assert "other.wav" not in cache

    def test_len(self) -> None:
        """Test __len__ method."""
        cache = LRUAudioCache()
        data = np.array([[0.1]], dtype=np.float32)

        assert len(cache) == 0

        for i in range(3):
            cached = CachedAudio(
                data=data,
                samplerate=44100,
                size_bytes=data.nbytes,
                path=Path(f"test{i}.wav"),
            )
            cache.put(f"test{i}.wav", cached)

        assert len(cache) == 3
