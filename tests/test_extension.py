from unittest import mock

from mopidy_youtube import Extension
from mopidy_youtube import backend as backend_lib
from mopidy_youtube import frontend as frontend_lib


def test_get_default_config():
    ext = Extension()

    config = ext.get_default_config()

    assert "[youtube]" in config
    assert "enabled = true" in config
    assert "youtube_api_key = " in config
    assert "threads_max = 16" in config
    assert "search_results = 15" in config
    assert "playlist_max_videos = 20" in config


def test_get_config_schema():
    ext = Extension()

    schema = ext.get_config_schema()

    assert "youtube_api_key" in schema
    assert "threads_max" in schema
    assert "search_results" in schema
    assert "playlist_max_videos" in schema
    assert "api_enabled" in schema
    assert "autoplay_enabled" in schema
    assert "strict_autoplay" in schema
    assert "max_autoplay_length" in schema
    assert "max_degrees_of_separation" in schema


def test_setup():
    registry = mock.Mock()

    ext = Extension()
    ext.setup(registry)

    registry.add.assert_called_with("backend", backend_lib.YouTubeBackend)
    registry.add.assert_called_with("frontend", frontend_lib.YouTubeAutoplayer)
