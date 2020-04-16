from unittest import mock
import pytest

from mopidy import httpclient

from mopidy_youtube.apis import youtube_api, youtube_bs4api, youtube_scrapi
from mopidy_youtube import Extension, backend, youtube


# need to work out how to add youtube_api.API to this list
apis = [youtube_scrapi.scrAPI, youtube_bs4api.bs4API]

proxy = None  # httpclient.format_proxy(config['proxy'])
youtube.Video.proxy = proxy


user_agent = "{}/{}".format(Extension.dist_name, Extension.version)

headers = {
    "user-agent": httpclient.format_user_agent(user_agent),
    "Cookie": "PREF=hl=en;",
    "Accept-Language": "en;q=0.8",
}

yak = "fakeyoutubekey"
youtube_api.youtube_api_key = yak
youtube.ThreadPool.threads_max = 4

@pytest.fixture
def config():
    return {
        "core": {"cache_dir": "."},
        "http": {"hostname": "127.0.0.1", "port": "6680"},
        "youtube": {
            "enabled": "true",
            "youtube_api_key": yak,
            "threads_max": 16,
            "search_results": 30,
            "playlist_max_videos": 20,
            "api_enabled": False,
        },
    }

def test_audio_url():

    for api in apis:
        youtube.Entry.api = api(proxy, headers)

        video = youtube.Video.get("e1YqueG2gtQ")

        assert video.audio_url.get() 
        assert video._audio_url == 


