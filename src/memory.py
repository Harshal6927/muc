# Copyright (c) 2025. All rights reserved.
"""Memory usage monitoring and management."""

import gc
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

from .audio_manager import AudioManager
from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class MemoryStats:
    """Memory usage statistics."""

    cache_mb: float
    total_objects: int
    numpy_arrays: int
    estimated_numpy_mb: float


class MemoryMonitor:
    """Monitor and manage memory usage."""

    def __init__(self, audio_manager: AudioManager) -> None:
        """Initialize memory monitor.

        Args:
            audio_manager: AudioManager instance to monitor

        """
        self.audio_manager = audio_manager

    def get_stats(self) -> MemoryStats:
        """Get current memory statistics.

        Returns:
            MemoryStats with current memory usage info

        """
        # Cache size
        cache_mb = 0.0
        if hasattr(self.audio_manager, "_cache"):
            cache_mb = self.audio_manager._cache.stats.get("size_mb", 0.0)

        # Count objects
        gc.collect()
        all_objects = gc.get_objects()
        total_objects = len(all_objects)

        # Count numpy arrays and estimate memory
        numpy_arrays = 0
        numpy_bytes = 0

        for obj in all_objects:
            if isinstance(obj, np.ndarray):
                numpy_arrays += 1
                numpy_bytes += obj.nbytes

        return MemoryStats(
            cache_mb=cache_mb,
            total_objects=total_objects,
            numpy_arrays=numpy_arrays,
            estimated_numpy_mb=numpy_bytes / (1024 * 1024),
        )

    def cleanup(self, aggressive: bool = False) -> int:
        """Clean up unused memory.

        Args:
            aggressive: If True, also clear the audio cache

        Returns:
            Number of objects collected by garbage collector

        """
        if aggressive and hasattr(self.audio_manager, "_cache"):
            self.audio_manager._cache.clear()
            logger.info("Cleared audio cache")

        # Force garbage collection
        collected = gc.collect()
        logger.info(f"Garbage collection freed {collected} objects")
        return collected


def get_object_size(obj: object) -> int:
    """Get the size of an object in bytes.

    Args:
        obj: Object to measure

    Returns:
        Size in bytes

    """
    if isinstance(obj, np.ndarray):
        return obj.nbytes
    return sys.getsizeof(obj)


class StreamingPlayer:
    """Stream large audio files without loading entirely into memory."""

    CHUNK_SIZE = 4096  # frames per chunk

    def __init__(self, audio_manager: AudioManager) -> None:
        """Initialize streaming player.

        Args:
            audio_manager: AudioManager instance for device info

        """
        self.audio_manager = audio_manager
        self._stream: sd.OutputStream | None = None
        self._file: sf.SoundFile | None = None
        self._playing = False

    def play_streaming(
        self,
        file_path: Path,
        volume: float = 1.0,
    ) -> bool:
        """Play a file using streaming (low memory usage).

        Args:
            file_path: Path to audio file
            volume: Volume multiplier (0.0 to 1.0)

        Returns:
            True if playback started successfully

        """
        self.stop()

        try:
            # Open file for streaming
            self._file = sf.SoundFile(str(file_path))
            channels = self._get_output_channels()

            def callback(
                outdata: np.ndarray,
                frames: int,
                _time_info: dict,
                _status: sd.CallbackFlags,
            ) -> None:
                try:
                    data = self._file.read(frames, dtype="float32")  # pyright: ignore[reportOptionalMemberAccess]
                except Exception:  # noqa: BLE001
                    raise sd.CallbackStop from None
                else:
                    if len(data) < frames:
                        # End of file
                        outdata[: len(data)] = self._adjust_channels(data * volume, channels)
                        outdata[len(data) :] = 0
                        raise sd.CallbackStop
                    outdata[:] = self._adjust_channels(data * volume, channels)

            self._stream = sd.OutputStream(
                samplerate=self._file.samplerate,
                channels=channels,
                callback=callback,
                device=self.audio_manager.output_device_id,
            )
            self._stream.start()
            self._playing = True
            logger.debug(f"Started streaming playback: {file_path}")
        except Exception:
            logger.exception(f"Failed to start streaming playback: {file_path}")
            self.stop()
            return False
        else:
            return True

    def _get_output_channels(self) -> int:
        """Get the number of output channels for the device.

        Returns:
            Number of output channels for the configured device

        """
        if self.audio_manager.output_device_id is not None:
            device = sd.query_devices(self.audio_manager.output_device_id)
            if isinstance(device, dict):
                return int(device["max_output_channels"])
        return 2  # Default to stereo

    def _adjust_channels(self, data: np.ndarray, target_channels: int) -> np.ndarray:
        """Adjust audio channels to match output device.

        Returns:
            Audio data adjusted to target channel count

        """
        if len(data.shape) == 1:
            data = data.reshape(-1, 1)

        current_channels = data.shape[1]

        if current_channels < target_channels:
            # Duplicate channels to fill
            tile_count = target_channels // current_channels
            data = np.tile(data, (1, tile_count))

            # Pad with silence if still not enough
            if data.shape[1] < target_channels:
                padding = np.zeros((data.shape[0], target_channels - data.shape[1]))
                data = np.hstack((data, padding))

        elif current_channels > target_channels:
            data = data[:, :target_channels]

        return data

    def stop(self) -> None:
        """Stop streaming playback."""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if self._file:
            self._file.close()
            self._file = None

        self._playing = False
        logger.debug("Stopped streaming playback")

    @property
    def is_playing(self) -> bool:
        """Check if streaming playback is active."""
        return self._playing


def should_stream(file_path: Path, threshold_mb: float = 10.0) -> bool:
    """Determine if a file should be streamed based on size.

    Args:
        file_path: Path to the audio file
        threshold_mb: Size threshold in MB above which to stream

    Returns:
        True if file should be streamed

    """
    try:
        size_bytes = file_path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
    except OSError:
        return False
    else:
        return size_mb > threshold_mb
