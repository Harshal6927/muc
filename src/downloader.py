# Copyright (c) 2025. All rights reserved.
"""YouTube audio downloader."""

import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

from rich.console import Console

from .logging_config import get_logger

logger = get_logger(__name__)


def check_yt_dlp_available() -> bool:
    """Check if yt-dlp is available.

    Returns:
        True if yt-dlp is installed, False otherwise.

    """
    try:
        import yt_dlp  # noqa: F401, PLC0415
    except ImportError:
        return False
    else:
        return True


def check_ffmpeg_available() -> bool:
    """Check if ffmpeg is available for audio conversion.

    Returns:
        True if ffmpeg is in PATH, False otherwise.

    """
    return shutil.which("ffmpeg") is not None


class YouTubeDownloader:
    """Downloads audio from YouTube."""

    # Regex patterns for YouTube URLs
    URL_PATTERNS: ClassVar[list[str]] = [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    ]

    def __init__(self, console: Console, sounds_dir: Path) -> None:
        """Initialize the YouTubeDownloader.

        Args:
            console: Rich console for output
            sounds_dir: Directory to save downloaded sounds

        """
        self.console = console
        self.sounds_dir = sounds_dir

    def validate_url(self, url: str) -> str | None:
        """Validate YouTube URL and extract video ID.

        Args:
            url: YouTube URL to validate

        Returns:
            Video ID if valid, None otherwise.

        """
        for pattern in self.URL_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def get_video_info(self, url: str) -> dict | None:
        """Get video information without downloading.

        Args:
            url: YouTube URL

        Returns:
            Dict with title, duration, etc. or None on failure.

        """
        try:
            import yt_dlp  # noqa: PLC0415

            ydl_opts: dict = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # pyright: ignore[reportArgumentType]
                info = ydl.extract_info(url, download=False)
                return {
                    "id": info.get("id"),
                    "title": info.get("title"),
                    "duration": info.get("duration"),  # seconds
                    "uploader": info.get("uploader"),
                    "view_count": info.get("view_count"),
                }
        except Exception:
            logger.exception("Failed to get video info")
            return None

    def download(
        self,
        url: str,
        output_name: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        audio_format: str = "wav",
        audio_quality: str = "192",
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> Path | None:
        """Download audio from YouTube.

        Args:
            url: YouTube URL
            output_name: Output filename (without extension)
            start_time: Start time for extraction (e.g., "0:30" or "30")
            end_time: End time for extraction (e.g., "1:00" or "60")
            audio_format: Output format (wav, mp3, ogg)
            audio_quality: Audio quality (bitrate for mp3)
            progress_callback: Callback for progress updates (percent, status)

        Returns:
            Path to downloaded file, or None on failure

        """
        try:
            import yt_dlp  # noqa: PLC0415
        except ImportError:
            self.console.print("[red]✗[/red] yt-dlp is not installed")
            self.console.print("[dim]Install with: uv add muc[yt-dlp][/dim]")
            return None

        if not check_ffmpeg_available():
            self.console.print("[red]✗[/red] ffmpeg is not installed (required for audio conversion)")
            self.console.print("[dim]Download from: https://ffmpeg.org/download.html[/dim]")
            return None

        # Validate URL
        video_id = self.validate_url(url)
        if not video_id:
            self.console.print("[red]✗[/red] Invalid YouTube URL")
            return None

        # Get video info for default name
        if not output_name:
            info = self.get_video_info(url)
            output_name = self._sanitize_filename(info["title"]) if info else video_id

        # Ensure sounds directory exists
        self.sounds_dir.mkdir(parents=True, exist_ok=True)

        # Build output path
        output_path = self.sounds_dir / f"{output_name}.{audio_format}"
        temp_path = self.sounds_dir / f".{output_name}_temp.%(ext)s"

        # Build yt-dlp options
        ydl_opts: dict = {
            "format": "bestaudio/best",
            "outtmpl": str(temp_path),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": audio_format,
                    "preferredquality": audio_quality,
                },
            ],
            "quiet": True,
            "no_warnings": True,
        }

        # Add time range extraction if specified
        if start_time or end_time:
            postprocessor_args = []
            if start_time:
                postprocessor_args.extend(["-ss", self._parse_time(start_time)])
            if end_time:
                postprocessor_args.extend(["-to", self._parse_time(end_time)])

            ydl_opts["postprocessor_args"] = {"ffmpeg": postprocessor_args}

        # Progress hook
        def progress_hook(d: dict) -> None:
            if d["status"] == "downloading":
                if progress_callback and "downloaded_bytes" in d and "total_bytes" in d:
                    percent = (d["downloaded_bytes"] / d["total_bytes"]) * 100
                    progress_callback(percent, "Downloading...")
            elif d["status"] == "finished" and progress_callback:
                progress_callback(100, "Converting...")

        ydl_opts["progress_hooks"] = [progress_hook]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # pyright: ignore[reportArgumentType]
                ydl.download([url])
        except Exception:
            logger.exception("Download failed")
            # Clean up temp files
            for temp_file in self.sounds_dir.glob(f".{output_name}_temp*"):
                temp_file.unlink()
            return None
        else:
            # Find the output file (yt-dlp may have added extension)
            expected_temp = self.sounds_dir / f".{output_name}_temp.{audio_format}"
            if expected_temp.exists():
                expected_temp.rename(output_path)

            # Clean up any temp files
            for temp_file in self.sounds_dir.glob(f".{output_name}_temp*"):
                temp_file.unlink()

            if output_path.exists():
                logger.info(f"Downloaded: {output_path}")
                return output_path
            logger.error("Download completed but output file not found")
            return None

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize a string for use as filename.

        Args:
            name: Original filename

        Returns:
            Sanitized filename safe for filesystem

        """
        # Remove invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, "")
        # Replace spaces with underscores
        name = name.replace(" ", "_")
        # Limit length
        name = name[:50]
        # Remove leading/trailing dots and spaces
        name = name.strip(". ")
        return name or "download"

    @staticmethod
    def _parse_time(time_str: str) -> str:
        """Parse time string to ffmpeg format.

        Accepts: "30", "0:30", "1:30", "01:30:00"
        Returns: "00:00:30" format

        Args:
            time_str: Time string in various formats

        Returns:
            Time string in HH:MM:SS format

        """
        time_str = time_str.strip()

        # Already in HH:MM:SS format
        if time_str.count(":") == 2:
            return time_str

        # MM:SS format
        if ":" in time_str:
            parts = time_str.split(":")
            if len(parts) == 2:
                mins, secs = parts
                return f"00:{int(mins):02d}:{int(secs):02d}"

        # Seconds only
        try:
            total_secs = int(time_str)
        except ValueError:
            return time_str
        else:
            mins, secs = divmod(total_secs, 60)
            hours, mins = divmod(mins, 60)
            return f"{hours:02d}:{mins:02d}:{secs:02d}"
