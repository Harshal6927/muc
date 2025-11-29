# Copyright (c) 2025. All rights reserved.
"""Benchmark tests for performance optimizations (PRD-009)."""

import random
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.cache import CachedAudio, LRUAudioCache
from src.config import Config
from src.lazy_loader import LazySound, LazySoundLibrary


class TestStartupPerformance:
    """Benchmark tests for startup time."""

    @pytest.fixture
    def large_sound_library(self, tmp_path: Path) -> Path:
        """Create a library with 100 test sound files.

        Returns:
            Path to the temporary directory containing test sound files

        """
        for i in range(100):
            (tmp_path / f"sound_{i:03d}.wav").touch()
        return tmp_path

    def test_lazy_library_startup_time(self, large_sound_library: Path) -> None:
        """Startup should be under 500ms with 100 sounds.

        Target: <500ms for initial library creation.
        """
        start = time.perf_counter()
        _library = LazySoundLibrary(sounds_dir=large_sound_library)
        elapsed = time.perf_counter() - start

        # Just creating library should be fast (no scanning yet)
        assert elapsed < 0.1, f"Library creation took {elapsed * 1000:.1f}ms"

    def test_lazy_index_build_time(self, large_sound_library: Path) -> None:
        """Index building should be under 500ms with 100 sounds.

        Target: <500ms for building the sound index.
        """
        library = LazySoundLibrary(sounds_dir=large_sound_library)

        start = time.perf_counter()
        _ = library.sounds  # Triggers index build
        elapsed = time.perf_counter() - start

        assert elapsed < 0.5, f"Index build took {elapsed * 1000:.1f}ms (target: <500ms)"

    def test_metadata_load_time_single(self, tmp_path: Path) -> None:
        """Metadata loading should be reasonably fast."""
        test_file = tmp_path / "test.wav"
        test_file.touch()

        sound = LazySound(test_file)

        mock_info = MagicMock()
        mock_info.duration = 5.0
        mock_info.samplerate = 44100
        mock_info.channels = 2
        mock_info.format = "WAV"
        mock_info.subtype = "PCM_16"

        with patch("src.lazy_loader.sf.info", return_value=mock_info):
            start = time.perf_counter()
            _ = sound.metadata
            elapsed = time.perf_counter() - start

            # Should be very fast since it's mocked
            assert elapsed < 0.01


class TestCachePerformance:
    """Benchmark tests for cache performance."""

    def test_cache_put_get_latency(self) -> None:
        """Cache operations should be under 1ms."""
        cache = LRUAudioCache(max_size_bytes=100 * 1024 * 1024)
        data = np.zeros((44100 * 5,), dtype=np.float32)  # 5 seconds of audio

        cached = CachedAudio(
            data=data,
            samplerate=44100,
            size_bytes=data.nbytes,
            path=Path("test.wav"),
        )

        # Test put
        start = time.perf_counter()
        cache.put("test.wav", cached)
        put_time = time.perf_counter() - start

        assert put_time < 0.001, f"Cache put took {put_time * 1000:.3f}ms"

        # Test get
        start = time.perf_counter()
        _ = cache.get("test.wav")
        get_time = time.perf_counter() - start

        assert get_time < 0.001, f"Cache get took {get_time * 1000:.3f}ms"

    def test_cached_playback_latency(self) -> None:
        """Cached playback retrieval should be under 20ms.

        Target: <20ms latency for cached audio retrieval.
        """
        cache = LRUAudioCache()

        # Simulate realistic audio data (44100 Hz, 5 seconds, stereo)
        rng = np.random.default_rng()
        data = rng.random((44100 * 5, 2), dtype=np.float32)
        cached = CachedAudio(
            data=data,
            samplerate=44100,
            size_bytes=data.nbytes,
            path=Path("test.wav"),
        )

        cache.put("test.wav", cached)

        # Measure retrieval time
        times = []
        for _ in range(100):
            start = time.perf_counter()
            _ = cache.get("test.wav")
            times.append(time.perf_counter() - start)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        assert avg_time < 0.020, f"Average retrieval took {avg_time * 1000:.1f}ms (target: <20ms)"
        assert max_time < 0.050, f"Max retrieval took {max_time * 1000:.1f}ms"

    def test_cache_hit_rate_with_repeated_access(self) -> None:
        """Cache hit rate should be >80% for repeated sounds.

        Target: >80% hit rate for typical usage patterns.
        """
        cache = LRUAudioCache(max_size_bytes=10 * 1024 * 1024)  # 10 MB

        # Create 5 sounds
        sounds = []
        for i in range(5):
            data = np.zeros((10000,), dtype=np.float32)
            sounds.append(
                CachedAudio(
                    data=data,
                    samplerate=44100,
                    size_bytes=data.nbytes,
                    path=Path(f"sound_{i}.wav"),
                ),
            )
            cache.put(f"sound_{i}.wav", sounds[-1])

        # Simulate access pattern: 80% access to first 2 sounds, 20% to others
        for _ in range(100):
            key = (
                f"sound_{random.randint(0, 1)}.wav"  # noqa: S311
                if random.random() < 0.8  # noqa: S311
                else f"sound_{random.randint(2, 4)}.wav"  # noqa: S311
            )
            cache.get(key)

        stats = cache.stats
        assert stats["hit_rate"] > 0.8, f"Hit rate {stats['hit_rate']:.2%} is below 80%"


class TestMemoryPerformance:
    """Benchmark tests for memory usage."""

    def test_memory_limit_respected(self) -> None:
        """Cache should not exceed configured memory limit."""
        max_mb = 5
        cache = LRUAudioCache(max_size_bytes=max_mb * 1024 * 1024)

        # Try to add more data than the limit
        for i in range(20):
            # Each array is about 0.5 MB
            data = np.zeros((128 * 1024,), dtype=np.float32)
            cached = CachedAudio(
                data=data,
                samplerate=44100,
                size_bytes=data.nbytes,
                path=Path(f"sound_{i}.wav"),
            )
            cache.put(f"sound_{i}.wav", cached)

        stats = cache.stats
        assert stats["size_mb"] <= max_mb, f"Cache size {stats['size_mb']:.1f}MB exceeds limit {max_mb}MB"

    def test_lru_eviction_efficiency(self) -> None:
        """LRU eviction should maintain recently used items."""
        cache = LRUAudioCache(max_size_bytes=1024 * 1024)  # 1 MB

        # Add 4 sounds (each ~0.5 MB = 512KB)
        for i in range(4):
            data = np.zeros((128 * 1024,), dtype=np.float32)  # 512 KB
            cached = CachedAudio(
                data=data,
                samplerate=44100,
                size_bytes=data.nbytes,
                path=Path(f"sound_{i}.wav"),
            )
            cache.put(f"sound_{i}.wav", cached)

            # Access sound_0 frequently to keep it in cache
            if i > 0:
                cache.get("sound_0.wav")

        # Cache can only hold ~2 items (1MB / 512KB)
        # sound_0 should still be in cache (frequently accessed)
        assert "sound_0.wav" in cache
        # sound_3 should be in cache (most recently added)
        assert "sound_3.wav" in cache
        # Earlier sounds should be evicted
        assert len(cache) <= 2


class TestPreloadPerformance:
    """Benchmark tests for preloading."""

    def test_preload_batch_performance(self, tmp_path: Path) -> None:
        """Preloading should handle multiple files efficiently."""
        cache = LRUAudioCache()
        files = [tmp_path / f"sound_{i}.wav" for i in range(10)]
        for f in files:
            f.touch()

        test_data = np.zeros((1000,), dtype=np.float32)

        with patch("src.cache.sf.read", return_value=(test_data, 44100)):
            start = time.perf_counter()
            loaded = cache.preload(files)
            elapsed = time.perf_counter() - start

            assert loaded == 10
            # Should be reasonably fast even with mocking overhead
            assert elapsed < 1.0, f"Preload took {elapsed:.2f}s"


class TestAsyncConfigPerformance:
    """Benchmark tests for async configuration."""

    def test_async_save_non_blocking(self, tmp_path: Path) -> None:
        """Async save should return immediately."""
        with patch.object(Config, "load"):
            config = Config()
            config.config_file = tmp_path / "test_config.json"

            with patch("builtins.open", MagicMock()):
                start = time.perf_counter()
                config.save(blocking=False)
                elapsed = time.perf_counter() - start

                # Non-blocking save should return almost immediately
                assert elapsed < 0.01, f"Async save took {elapsed * 1000:.1f}ms"

                # Cancel the timer to avoid test pollution
                if config._auto_save_timer:
                    config._auto_save_timer.cancel()
