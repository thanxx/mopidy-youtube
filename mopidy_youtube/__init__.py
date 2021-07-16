import logging
import pathlib

import pkg_resources
from mopidy import config, ext

__version__ = pkg_resources.get_distribution("Mopidy-YouTube").version

logger = logging.getLogger(__name__)


class Extension(ext.Extension):

    dist_name = "Mopidy-YouTube"
    ext_name = "youtube"
    version = __version__

    def get_default_config(self):
        return config.read(pathlib.Path(__file__).parent / "ext.conf")

    def get_config_schema(self):
        schema = super().get_config_schema()
        schema["youtube_api_key"] = config.String(optional=True)
        schema["search_results"] = config.Integer(minimum=1)
        schema["playlist_max_videos"] = config.Integer(minimum=1)
        schema["api_enabled"] = config.Boolean(optional=True)
        schema["channel_id"] = config.String(optional=True)
        schema["musicapi_enabled"] = config.Boolean(optional=True)
        schema["musicapi_cookie"] = config.String(optional=True)
        schema["autoplay_enabled"] = config.Boolean(optional=True)
        schema["strict_autoplay"] = config.Boolean(optional=True)
        schema["max_autoplay_length"] = config.Integer(optional=True)
        schema["max_degrees_of_separation"] = config.Integer()
        return schema

    def setup(self, registry):
        from .backend import YouTubeBackend
        from .frontend import YouTubeAutoplayer

        registry.add("backend", YouTubeBackend)
        registry.add("frontend", YouTubeAutoplayer)
