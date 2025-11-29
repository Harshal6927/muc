# Copyright (c) 2025. All rights reserved.
"""Audio manipulation utilities for trimming and normalization."""

from collections.abc import Callable
from pathlib import Path

import numpy as np
import soundfile as sf

from .logging_config import get_logger

logger = get_logger(__name__)


class AudioTrimmer:
    """Trims audio files to specific time ranges."""

    @staticmethod
    def parse_time_to_seconds(time_str: str) -> float:
        """Parse time string to seconds.

        Accepts: "30", "0:30", "1:30.5", "01:30:00.500"

        Args:
            time_str: Time string in various formats

        Returns:
            Time in seconds as float

        Raises:
            ValueError: If time format is invalid

        """
        time_str = time_str.strip()

        parts = time_str.split(":")

        if len(parts) == 1:
            return float(parts[0])
        if len(parts) == 2:
            mins, secs = parts
            return float(mins) * 60 + float(secs)
        if len(parts) == 3:
            hours, mins, secs = parts
            return float(hours) * 3600 + float(mins) * 60 + float(secs)
        raise ValueError(f"Invalid time format: {time_str}")

    @staticmethod
    def format_seconds(seconds: float) -> str:
        """Format seconds to M:SS.ms string.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted time string

        """
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins}:{secs:05.2f}"

    def get_duration(self, audio_path: Path) -> float:
        """Get audio file duration in seconds.

        Args:
            audio_path: Path to audio file

        Returns:
            Duration in seconds

        """
        info = sf.info(str(audio_path))
        return info.duration

    def trim(
        self,
        input_path: Path,
        output_path: Path | None = None,
        start: float = 0,
        end: float | None = None,
        fade_in: float = 0,
        fade_out: float = 0,
    ) -> Path:
        """Trim an audio file.

        Args:
            input_path: Input audio file
            output_path: Output path (defaults to input_name_trimmed.ext)
            start: Start time in seconds
            end: End time in seconds (None = end of file)
            fade_in: Fade in duration in seconds
            fade_out: Fade out duration in seconds

        Returns:
            Path to the trimmed file

        Raises:
            ValueError: If time range is invalid

        """
        # Load audio
        data, samplerate = sf.read(str(input_path))

        # Get total duration
        total_samples = len(data)
        total_duration = total_samples / samplerate

        # Calculate sample indices
        start_sample = int(start * samplerate)
        end_sample = int(end * samplerate) if end else total_samples

        # Validate
        if start_sample >= total_samples:
            raise ValueError(f"Start time ({start}s) exceeds audio duration ({total_duration:.1f}s)")
        end_sample = min(end_sample, total_samples)
        if start_sample >= end_sample:
            raise ValueError("Start time must be before end time")

        # Trim
        trimmed = data[start_sample:end_sample].astype(np.float64)

        # Apply fades
        if fade_in > 0:
            fade_samples = int(fade_in * samplerate)
            fade_samples = min(fade_samples, len(trimmed))
            fade_curve = np.linspace(0, 1, fade_samples)
            if len(trimmed.shape) == 2:
                fade_curve = fade_curve.reshape(-1, 1)
            trimmed[:fade_samples] *= fade_curve

        if fade_out > 0:
            fade_samples = int(fade_out * samplerate)
            fade_samples = min(fade_samples, len(trimmed))
            fade_curve = np.linspace(1, 0, fade_samples)
            if len(trimmed.shape) == 2:
                fade_curve = fade_curve.reshape(-1, 1)
            trimmed[-fade_samples:] *= fade_curve

        # Generate output path
        if output_path is None:
            output_path = input_path.parent / f"{input_path.stem}_trimmed{input_path.suffix}"

        # Save
        sf.write(str(output_path), trimmed, samplerate)

        logger.info(f"Trimmed {input_path.name} -> {output_path.name}")
        return output_path


class AudioNormalizer:
    """Normalizes audio file levels."""

    @staticmethod
    def analyze(audio_path: Path) -> dict:
        """Analyze audio levels.

        Args:
            audio_path: Path to audio file

        Returns:
            Dict with peak, rms, and audio info

        """
        data, samplerate = sf.read(str(audio_path))

        # Convert to mono for analysis
        mono = np.mean(data, axis=1) if len(data.shape) == 2 else data

        # Calculate peak
        peak = np.max(np.abs(mono))
        peak_db = 20 * np.log10(peak) if peak > 0 else -np.inf

        # Calculate RMS
        rms = np.sqrt(np.mean(mono**2))
        rms_db = 20 * np.log10(rms) if rms > 0 else -np.inf

        return {
            "peak": float(peak),
            "peak_db": float(peak_db),
            "rms": float(rms),
            "rms_db": float(rms_db),
            "duration": len(data) / samplerate,
            "samplerate": samplerate,
            "channels": data.shape[1] if len(data.shape) == 2 else 1,
        }

    def normalize(
        self,
        input_path: Path,
        output_path: Path | None = None,
        target_db: float = -3.0,
        mode: str = "peak",
        *,
        in_place: bool = False,
    ) -> Path:
        """Normalize audio to target level.

        Args:
            input_path: Input audio file
            output_path: Output path (None = auto-generate)
            target_db: Target level in dB
            mode: "peak" for peak normalization, "rms" for loudness
            in_place: Overwrite original file

        Returns:
            Path to normalized file

        Raises:
            ValueError: If audio file is silent

        """
        data, samplerate = sf.read(str(input_path))

        # Calculate current level
        mono = np.mean(data, axis=1) if len(data.shape) == 2 else data

        current = np.max(np.abs(mono)) if mode == "peak" else np.sqrt(np.mean(mono**2))

        if current == 0:
            raise ValueError("Audio file is silent")

        current_db = 20 * np.log10(current)
        gain_db = target_db - current_db
        gain = 10 ** (gain_db / 20)

        # Apply gain
        normalized = data * gain

        # Clip to prevent distortion
        normalized = np.clip(normalized, -1.0, 1.0)

        # Determine output path
        if in_place:
            output_path = input_path
        elif output_path is None:
            output_path = input_path.parent / f"{input_path.stem}_normalized{input_path.suffix}"

        # Save
        sf.write(str(output_path), normalized, samplerate)

        logger.info(f"Normalized {input_path.name} (gain: {gain_db:+.1f} dB)")
        return output_path

    def normalize_batch(
        self,
        files: list[Path],
        target_db: float = -3.0,
        mode: str = "peak",
        *,
        in_place: bool = False,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> list[Path]:
        """Normalize multiple files.

        Args:
            files: List of audio file paths
            target_db: Target level in dB
            mode: "peak" or "rms"
            in_place: Overwrite original files
            progress_callback: Callback for progress (current, filename)

        Returns:
            List of output paths

        """
        results = []

        for i, file_path in enumerate(files):
            if progress_callback:
                progress_callback(i + 1, file_path.name)

            try:
                result = self.normalize(
                    file_path,
                    target_db=target_db,
                    mode=mode,
                    in_place=in_place,
                )
                results.append(result)
            except Exception:
                logger.exception(f"Failed to normalize {file_path.name}")

        return results
