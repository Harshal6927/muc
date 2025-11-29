# Copyright (c) 2025. All rights reserved.
"""Audio caching system with LRU eviction."""

from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
import soundfile as sf

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CachedAudio:
    """Cached audio data with metadata."""

    data: np.ndarray
    samplerate: int
    size_bytes: int
    path: Path
    access_count: int = field(default=0)

    @classmethod
    def from_file(cls, path: Path) -> "CachedAudio":
        """Load audio from file.

        Args:
            path: Path to the audio file

        Returns:
            CachedAudio instance with loaded data

        """
        data, samplerate = sf.read(str(path), dtype="float32")  # pyright: ignore[reportGeneralTypeIssues]
        size_bytes = data.nbytes
        return cls(
            data=data,
            samplerate=samplerate,
            size_bytes=size_bytes,
            path=path,
        )


class LRUAudioCache:
    """LRU cache for audio data with memory limit."""

    DEFAULT_MAX_SIZE = 100 * 1024 * 1024  # 100 MB

    def __init__(self, max_size_bytes: int | None = None) -> None:
        """Initialize the LRU cache.

        Args:
            max_size_bytes: Maximum cache size in bytes (default: 100 MB)

        """
        self.max_size_bytes = max_size_bytes or self.DEFAULT_MAX_SIZE
        self._cache: OrderedDict[str, CachedAudio] = OrderedDict()
        self._lock = Lock()
        self._current_size = 0

        # Statistics
        self.hits = 0
        self.misses = 0

        logger.debug(f"LRUAudioCache initialized with max size {self.max_size_bytes / (1024 * 1024):.1f} MB")

    def get(self, key: str) -> CachedAudio | None:
        """Get cached audio, moving to end (most recent).

        Args:
            key: Cache key (usually file path as string)

        Returns:
            CachedAudio if found, None otherwise

        """
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key].access_count += 1
                self.hits += 1
                logger.debug(f"Cache hit: {key}")
                return self._cache[key]
            self.misses += 1
            logger.debug(f"Cache miss: {key}")
            return None

    def put(self, key: str, audio: CachedAudio) -> None:
        """Add audio to cache, evicting old entries if needed.

        Args:
            key: Cache key (usually file path as string)
            audio: CachedAudio instance to cache

        """
        with self._lock:
            # If already in cache, update and move to end
            if key in self._cache:
                old_size = self._cache[key].size_bytes
                self._current_size -= old_size
                self._cache.move_to_end(key)

            # Evict until we have room
            while self._cache and self._current_size + audio.size_bytes > self.max_size_bytes:
                self._evict_one()

            # Add new entry
            self._cache[key] = audio
            self._current_size += audio.size_bytes
            logger.debug(f"Cached: {key} ({audio.size_bytes / 1024:.1f} KB)")

    def _evict_one(self) -> None:
        """Evict the least recently used entry."""
        if self._cache:
            key, audio = self._cache.popitem(last=False)
            self._current_size -= audio.size_bytes
            logger.debug(f"Evicted from cache: {key}")

    def preload(self, paths: list[Path]) -> int:
        """Pre-load multiple sounds into cache.

        Args:
            paths: List of paths to audio files to preload

        Returns:
            Number of sounds successfully preloaded

        """
        loaded = 0
        for path in paths:
            key = str(path)
            if key not in self._cache:
                try:
                    audio = CachedAudio.from_file(path)
                    self.put(key, audio)
                    loaded += 1
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"Failed to preload {path}: {e}")
        logger.info(f"Preloaded {loaded} sounds into cache")
        return loaded

    def clear(self) -> None:
        """Clear the entire cache."""
        with self._lock:
            self._cache.clear()
            self._current_size = 0
            self.hits = 0
            self.misses = 0
            logger.info("Cache cleared")

    def contains(self, key: str) -> bool:
        """Check if key is in cache without updating LRU order.

        Args:
            key: Cache key to check

        Returns:
            True if key is in cache

        """
        with self._lock:
            return key in self._cache

    @property
    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics

        """
        with self._lock:
            total_requests = self.hits + self.misses
            hit_rate = self.hits / total_requests if total_requests > 0 else 0.0

            return {
                "entries": len(self._cache),
                "size_bytes": self._current_size,
                "size_mb": self._current_size / (1024 * 1024),
                "max_size_mb": self.max_size_bytes / (1024 * 1024),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": hit_rate,
                "hit_rate_percent": hit_rate * 100,
            }

    def __len__(self) -> int:
        """Return number of items in cache."""  # noqa: DOC201
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """Check if key is in cache."""  # noqa: DOC201
        return self.contains(key)
