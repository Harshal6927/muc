# Copyright (c) 2025. All rights reserved.
"""Lazy loading and sound library management."""

import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from functools import cached_property
from pathlib import Path
from typing import Any

import soundfile as sf

from .cache import LRUAudioCache
from .logging_config import get_logger
from .validators import SUPPORTED_FORMATS

logger = get_logger(__name__)


class LazySound:
    """A sound that loads metadata and audio lazily."""

    def __init__(self, path: Path) -> None:
        """Initialize lazy sound.

        Args:
            path: Path to the audio file

        """
        self.path = path
        self._audio_data: tuple[Any, int] | None = None
        self._metadata: dict | None = None

    @property
    def name(self) -> str:
        """Sound name derived from filename."""
        return self.path.stem

    @property
    def extension(self) -> str:
        """File extension."""
        return self.path.suffix.lower()

    @cached_property
    def metadata(self) -> dict:
        """Load metadata on first access.

        Returns:
            Dictionary with audio metadata (duration, samplerate, channels, format, subtype)

        """
        try:
            info = sf.info(str(self.path))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to read metadata for {self.path}: {e}")
            return {
                "duration": 0.0,
                "samplerate": 0,
                "channels": 0,
                "format": "unknown",
                "subtype": "unknown",
            }
        else:
            return {
                "duration": info.duration,
                "samplerate": info.samplerate,
                "channels": info.channels,
                "format": info.format,
                "subtype": info.subtype,
            }

    @property
    def duration(self) -> float:
        """Get duration without loading full audio."""
        return self.metadata["duration"]

    @property
    def samplerate(self) -> int:
        """Get sample rate."""
        return self.metadata["samplerate"]

    @property
    def channels(self) -> int:
        """Get channel count."""
        return self.metadata["channels"]

    def load_audio(self) -> tuple:
        """Load audio data. Called on playback.

        Returns:
            Tuple of (data, samplerate)

        """
        if self._audio_data is None:
            data, samplerate = sf.read(str(self.path), dtype="float32")  # pyright: ignore[reportGeneralTypeIssues]
            self._audio_data = (data, samplerate)
        return self._audio_data

    def unload(self) -> None:
        """Release loaded audio data."""
        self._audio_data = None

    def is_loaded(self) -> bool:
        """Check if audio data is loaded.

        Returns:
            True if audio data is loaded, False otherwise

        """
        return self._audio_data is not None


class LazySoundLibrary:
    """Sound library with lazy loading."""

    EXTENSIONS = SUPPORTED_FORMATS

    def __init__(self, sounds_dir: Path | None = None, sounds_dirs: list[Path] | None = None) -> None:
        """Initialize the lazy sound library.

        Args:
            sounds_dir: Single directory containing sound files (legacy)
            sounds_dirs: List of directories to scan for sounds

        """
        if sounds_dirs:
            self.sounds_dirs = sounds_dirs
            self.sounds_dir = sounds_dirs[0] if sounds_dirs else Path.cwd() / "sounds"
        elif sounds_dir:
            self.sounds_dirs = [sounds_dir]
            self.sounds_dir = sounds_dir
        else:
            self.sounds_dirs = [Path.cwd() / "sounds"]
            self.sounds_dir = Path.cwd() / "sounds"

        self._sounds: dict[str, LazySound] | None = None
        self._index_lock = threading.Lock()
        logger.debug(f"LazySoundLibrary initialized with dirs: {self.sounds_dirs}")

    @property
    def sounds(self) -> dict[str, LazySound]:
        """Lazily build sound index on first access."""
        if self._sounds is None:
            with self._index_lock:
                if self._sounds is None:  # Double-check locking
                    self._sounds = self._build_index()
        return self._sounds

    def _build_index(self) -> dict[str, LazySound]:
        """Build sound index from directories.

        Returns:
            Dictionary mapping sound names to LazySound instances

        """
        sounds: dict[str, LazySound] = {}

        for sounds_dir in self.sounds_dirs:
            if sounds_dir.exists():
                for path in sounds_dir.rglob("*"):
                    if path.suffix.lower() in self.EXTENSIONS:
                        sound = LazySound(path)
                        # Later directories override earlier ones
                        sounds[sound.name] = sound

        logger.info(f"Built index with {len(sounds)} sounds")
        return sounds

    def refresh(self) -> None:
        """Force refresh of sound index."""
        with self._index_lock:
            self._sounds = None
        logger.info("Sound library index refreshed")

    def iter_sounds(self) -> Iterator[LazySound]:
        """Iterate over sounds without loading all into memory.

        Yields:
            LazySound instances

        """
        for sounds_dir in self.sounds_dirs:
            if sounds_dir.exists():
                for path in sounds_dir.rglob("*"):
                    if path.suffix.lower() in self.EXTENSIONS:
                        yield LazySound(path)

    def get(self, name: str) -> LazySound | None:
        """Get a sound by name.

        Args:
            name: Sound name (stem of filename)

        Returns:
            LazySound if found, None otherwise

        """
        return self.sounds.get(name)

    def get_paths(self) -> dict[str, Path]:
        """Get dictionary of sound names to paths.

        Returns:
            Dictionary mapping sound names to file paths

        """
        return {name: sound.path for name, sound in self.sounds.items()}

    def __len__(self) -> int:
        """Return number of sounds in library.

        Returns:
            Number of sounds in the library

        """
        return len(self.sounds)

    def __contains__(self, name: str) -> bool:
        """Check if sound exists in library.

        Returns:
            True if sound exists, False otherwise

        """
        return name in self.sounds

    def __iter__(self) -> Iterator[str]:
        """Iterate over sound names.

        Returns:
            Iterator over sound names

        """
        return iter(self.sounds)


class BackgroundIndexer:
    """Index sounds in background thread."""

    def __init__(self, library: LazySoundLibrary, cache: "LRUAudioCache | None" = None) -> None:
        """Initialize the background indexer.

        Args:
            library: LazySoundLibrary instance to index
            cache: Optional LRUAudioCache to preload sounds into

        """
        self.library = library
        self.cache = cache
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._indexing = False
        self._on_complete: Callable[[], None] | None = None

    def start_indexing(
        self,
        on_complete: Callable[[], None] | None = None,
        preload_metadata: bool = True,
    ) -> None:
        """Start background indexing.

        Args:
            on_complete: Callback to invoke when indexing is complete
            preload_metadata: If True, preload metadata for all sounds

        """
        if self._indexing:
            return

        self._indexing = True
        self._on_complete = on_complete
        self._executor.submit(self._index, preload_metadata)
        logger.info("Background indexing started")

    def _index(self, preload_metadata: bool) -> None:
        """Perform indexing in background."""
        try:
            # Force index rebuild
            _ = self.library.sounds

            # Pre-load metadata for all sounds (not audio data)
            if preload_metadata:
                for sound in self.library.sounds.values():
                    _ = sound.metadata

            if self._on_complete:
                self._on_complete()

            logger.info("Background indexing complete")
        except Exception:
            logger.exception("Background indexing failed")
        finally:
            self._indexing = False

    def preload_sounds(self, sound_names: list[str]) -> None:
        """Preload specific sounds into cache in background.

        Args:
            sound_names: List of sound names to preload

        """
        if not self.cache:
            return

        def _preload() -> None:
            if self.cache is None:
                return
            paths = []
            for name in sound_names:
                sound = self.library.get(name)
                if sound:
                    paths.append(sound.path)
            self.cache.preload(paths)

        self._executor.submit(_preload)

    @property
    def is_indexing(self) -> bool:
        """Check if indexing is in progress."""
        return self._indexing

    def shutdown(self) -> None:
        """Shutdown the executor."""
        self._executor.shutdown(wait=False)
