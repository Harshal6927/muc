# Copyright (c) 2025. All rights reserved.
"""Tests for the lazy_loader module."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from src.lazy_loader import BackgroundIndexer, LazySound, LazySoundLibrary


class TestLazySound:
    """Tests for LazySound class."""

    def test_name_from_path(self, tmp_path: Path) -> None:
        """Test sound name is derived from filename."""
        path = tmp_path / "my_sound.wav"
        path.touch()

        sound = LazySound(path)
        assert sound.name == "my_sound"

    def test_extension(self, tmp_path: Path) -> None:
        """Test extension property."""
        path = tmp_path / "sound.wav"
        path.touch()

        sound = LazySound(path)
        assert sound.extension == ".wav"

    def test_metadata_loaded_lazily(self, tmp_path: Path) -> None:
        """Test metadata is loaded on first access."""
        path = tmp_path / "sound.wav"
        path.touch()

        sound = LazySound(path)

        mock_info = MagicMock()
        mock_info.duration = 5.0
        mock_info.samplerate = 44100
        mock_info.channels = 2
        mock_info.format = "WAV"
        mock_info.subtype = "PCM_16"

        with patch("src.lazy_loader.sf.info", return_value=mock_info) as mock_sf_info:
            # First access loads metadata
            metadata = sound.metadata

            assert metadata["duration"] == 5.0
            assert metadata["samplerate"] == 44100
            assert metadata["channels"] == 2
            mock_sf_info.assert_called_once()

            # Second access uses cached property
            _ = sound.metadata
            assert mock_sf_info.call_count == 1  # Not called again

    def test_metadata_handles_errors(self, tmp_path: Path) -> None:
        """Test metadata returns defaults on error."""
        path = tmp_path / "bad_sound.wav"
        path.touch()

        sound = LazySound(path)

        with patch("src.lazy_loader.sf.info", side_effect=Exception("Read error")):
            metadata = sound.metadata

            assert metadata["duration"] == 0.0
            assert metadata["format"] == "unknown"

    def test_duration_property(self, tmp_path: Path) -> None:
        """Test duration property."""
        path = tmp_path / "sound.wav"
        path.touch()

        sound = LazySound(path)

        mock_info = MagicMock()
        mock_info.duration = 3.5
        mock_info.samplerate = 44100
        mock_info.channels = 1
        mock_info.format = "WAV"
        mock_info.subtype = "PCM_16"

        with patch("src.lazy_loader.sf.info", return_value=mock_info):
            assert sound.duration == 3.5

    def test_load_audio(self, tmp_path: Path) -> None:
        """Test loading audio data."""
        path = tmp_path / "sound.wav"
        path.touch()

        sound = LazySound(path)
        test_data = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)

        with patch("src.lazy_loader.sf.read", return_value=(test_data, 44100)):
            data, samplerate = sound.load_audio()

            assert np.array_equal(data, test_data)
            assert samplerate == 44100

    def test_load_audio_cached(self, tmp_path: Path) -> None:
        """Test that audio data is cached after first load."""
        path = tmp_path / "sound.wav"
        path.touch()

        sound = LazySound(path)
        test_data = np.array([[0.1]], dtype=np.float32)

        with patch("src.lazy_loader.sf.read", return_value=(test_data, 44100)) as mock_read:
            sound.load_audio()
            sound.load_audio()

            assert mock_read.call_count == 1

    def test_unload(self, tmp_path: Path) -> None:
        """Test unloading audio data."""
        path = tmp_path / "sound.wav"
        path.touch()

        sound = LazySound(path)
        test_data = np.array([[0.1]], dtype=np.float32)

        with patch("src.lazy_loader.sf.read", return_value=(test_data, 44100)):
            sound.load_audio()
            assert sound.is_loaded()

            sound.unload()
            assert not sound.is_loaded()


class TestLazySoundLibrary:
    """Tests for LazySoundLibrary class."""

    def test_init_with_single_dir(self, tmp_path: Path) -> None:
        """Test initialization with single directory."""
        library = LazySoundLibrary(sounds_dir=tmp_path)

        assert library.sounds_dir == tmp_path
        assert library.sounds_dirs == [tmp_path]

    def test_init_with_multiple_dirs(self, tmp_path: Path) -> None:
        """Test initialization with multiple directories."""
        dir1 = tmp_path / "sounds1"
        dir2 = tmp_path / "sounds2"
        dir1.mkdir()
        dir2.mkdir()

        library = LazySoundLibrary(sounds_dirs=[dir1, dir2])

        assert library.sounds_dirs == [dir1, dir2]
        assert library.sounds_dir == dir1

    def test_sounds_property_builds_index(self, tmp_path: Path) -> None:
        """Test sounds property lazily builds index."""
        # Create test files
        (tmp_path / "sound1.wav").touch()
        (tmp_path / "sound2.mp3").touch()
        (tmp_path / "readme.txt").touch()  # Should be ignored

        library = LazySoundLibrary(sounds_dir=tmp_path)

        assert library._sounds is None

        sounds = library.sounds

        assert library._sounds is not None
        assert len(sounds) == 2
        assert "sound1" in sounds
        assert "sound2" in sounds
        assert "readme" not in sounds

    def test_sounds_in_subdirectories(self, tmp_path: Path) -> None:
        """Test sounds in subdirectories are found."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested_sound.wav").touch()
        (tmp_path / "root_sound.wav").touch()

        library = LazySoundLibrary(sounds_dir=tmp_path)
        sounds = library.sounds

        assert len(sounds) == 2
        assert "nested_sound" in sounds
        assert "root_sound" in sounds

    def test_later_directories_override(self, tmp_path: Path) -> None:
        """Test that later directories override earlier ones."""
        dir1 = tmp_path / "sounds1"
        dir2 = tmp_path / "sounds2"
        dir1.mkdir()
        dir2.mkdir()

        (dir1 / "sound.wav").touch()
        (dir2 / "sound.wav").touch()

        library = LazySoundLibrary(sounds_dirs=[dir1, dir2])
        sounds = library.sounds

        # sound should come from dir2 (later directory)
        assert sounds["sound"].path.parent == dir2

    def test_refresh(self, tmp_path: Path) -> None:
        """Test refreshing the library."""
        library = LazySoundLibrary(sounds_dir=tmp_path)

        # Access sounds to build index
        _ = library.sounds
        assert library._sounds is not None

        # Refresh clears the index
        library.refresh()
        assert library._sounds is None

    def test_get(self, tmp_path: Path) -> None:
        """Test getting a sound by name."""
        (tmp_path / "test.wav").touch()

        library = LazySoundLibrary(sounds_dir=tmp_path)

        sound = library.get("test")
        assert sound is not None
        assert sound.name == "test"

        missing = library.get("nonexistent")
        assert missing is None

    def test_get_paths(self, tmp_path: Path) -> None:
        """Test getting dictionary of paths."""
        (tmp_path / "sound1.wav").touch()
        (tmp_path / "sound2.wav").touch()

        library = LazySoundLibrary(sounds_dir=tmp_path)
        paths = library.get_paths()

        assert len(paths) == 2
        assert paths["sound1"] == tmp_path / "sound1.wav"

    def test_len(self, tmp_path: Path) -> None:
        """Test __len__."""
        (tmp_path / "s1.wav").touch()
        (tmp_path / "s2.wav").touch()

        library = LazySoundLibrary(sounds_dir=tmp_path)
        assert len(library) == 2

    def test_contains(self, tmp_path: Path) -> None:
        """Test __contains__."""
        (tmp_path / "exists.wav").touch()

        library = LazySoundLibrary(sounds_dir=tmp_path)

        assert "exists" in library
        assert "missing" not in library

    def test_iter(self, tmp_path: Path) -> None:
        """Test __iter__."""
        (tmp_path / "a.wav").touch()
        (tmp_path / "b.wav").touch()

        library = LazySoundLibrary(sounds_dir=tmp_path)
        names = list(library)

        assert len(names) == 2
        assert "a" in names
        assert "b" in names


class TestBackgroundIndexer:
    """Tests for BackgroundIndexer class."""

    def test_start_indexing(self, tmp_path: Path) -> None:
        """Test starting background indexing."""
        (tmp_path / "sound.wav").touch()

        library = LazySoundLibrary(sounds_dir=tmp_path)
        indexer = BackgroundIndexer(library)

        on_complete = MagicMock()

        # Mock metadata loading
        mock_info = MagicMock()
        mock_info.duration = 1.0
        mock_info.samplerate = 44100
        mock_info.channels = 2
        mock_info.format = "WAV"
        mock_info.subtype = "PCM_16"

        with patch("src.lazy_loader.sf.info", return_value=mock_info):
            indexer.start_indexing(on_complete=on_complete)

            # Wait for indexing to complete
            time.sleep(0.5)

            assert not indexer.is_indexing
            on_complete.assert_called_once()

    def test_double_start_ignored(self, tmp_path: Path) -> None:
        """Test that starting twice is ignored."""
        library = LazySoundLibrary(sounds_dir=tmp_path)
        indexer = BackgroundIndexer(library)
        indexer._indexing = True

        indexer.start_indexing()
        # Should not change anything since already indexing

    def test_shutdown(self, tmp_path: Path) -> None:
        """Test shutdown."""
        library = LazySoundLibrary(sounds_dir=tmp_path)
        indexer = BackgroundIndexer(library)

        indexer.shutdown()
        # Should not raise
