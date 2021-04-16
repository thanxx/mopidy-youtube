import re
import string
import unicodedata
from urllib.parse import parse_qs, urlparse

import pykka
from mopidy import backend, httpclient
from mopidy.models import Album, Artist, SearchResult, Track, Ref, Playlist
from mopidy_youtube import Extension, logger, youtube
from mopidy_youtube.apis import youtube_api, youtube_bs4api


"""
A typical interaction:
1. User searches for a keyword (YouTubeLibraryProvider.search)
2. User adds a track to the queue (YouTubeLibraryProvider.lookup)
3. User plays a track from the queue (YouTubePlaybackProvider.translate_uri)
step 1 requires only 2 API calls. Data for the next steps are loaded in the
background, so steps 2/3 are usually instantaneous.
"""


def extract_id(uri):
    """takes a uri in the form youtube:video/<title>.<id> and returns <id>"""
    return uri.split(".")[-1]


def safe_url(uri):
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
    safe_uri = unicodedata.normalize("NFKD", uri).encode("ASCII", "ignore")
    return re.sub(
        r"\s+", " ", "".join(c for c in map(chr, safe_uri) if c in valid_chars)
    ).strip()


class YouTubeBackend(pykka.ThreadingActor, backend.Backend):
    def __init__(self, config, audio):
        super().__init__()
        self.config = config
        self.library = YouTubeLibraryProvider(backend=self)
        self.playback = YouTubePlaybackProvider(audio=audio, backend=self)
        youtube_api.youtube_api_key = (
            config["youtube"]["youtube_api_key"] or None
        )
        youtube.ThreadPool.threads_max = config["youtube"]["threads_max"]
        youtube.Video.search_results = config["youtube"]["search_results"]
        youtube.Playlist.playlist_max_videos = config["youtube"][
            "playlist_max_videos"
        ]
        youtube.api_enabled = config["youtube"]["api_enabled"]
        self.uri_schemes = ["youtube", "yt"]
        self.user_agent = "{}/{}".format(Extension.dist_name, Extension.version)

    def on_start(self):
        proxy = httpclient.format_proxy(self.config["proxy"])
        youtube.Video.proxy = proxy
        headers = {
            "user-agent": httpclient.format_user_agent(self.user_agent),
            "Cookie": "PREF=hl=en;",
            "Accept-Language": "en;q=0.8",
        }

        if youtube.api_enabled is True:
            if youtube_api.youtube_api_key is None:
                logger.error("No YouTube API key provided, disabling API")
                youtube.api_enabled = False
            else:
                youtube.Entry.api = youtube_api.API(proxy, headers)
                if youtube.Entry.search(q="test") is None:
                    logger.error(
                        "Failed to verify YouTube API key, disabling API"
                    )
                    youtube.api_enabled = False
                else:
                    logger.info("YouTube API key verified")

        if youtube.api_enabled is False:
            logger.info("using bs4API")
            youtube.Entry.api = youtube_bs4api.bs4API(proxy, headers)


class YouTubeLibraryProvider(backend.LibraryProvider):
    """
    Called when browsing or searching the library. To avoid horrible browsing
    performance, and since only search makes sense for youtube anyway, we we
    only answer queries for the 'any' field (for instance a {'artist': 'U2'}
    query is ignored).

    For performance we only do 2 API calls before we reply, one for search
    (youtube.Entry.search) and one to fetch video_count of all playlists
    (youtube.Playlist.load_info).

    We also start loading 2 things in the background:
     - info for all videos
     - video list for all playlists
    Hence, adding search results to the playing queue (see
    YouTubeLibraryProvider.lookup) will most likely be instantaneous, since
    all info will be ready by that time.
    """
    ROOT_DIR = Ref.directory(uri="youtube:", name="Youtube Playlists")


#    chillhop2020 = Ref.track(uri='youtube:https://www.youtube.com/watch?v=SINV2KJJ-MY', name='track')
#    deep = Ref.track(uri='youtube:playlist:https://www.youtube.com/playlist?list=PLVWkvsDBrJmYzemPpwvLkn0AfMXPWfm4s', name='Deep & Dub')

    
    _ROOT_DIR_CONTENTS = [
        Ref.directory(uri='youtube:collection/CHNL.UCKLtqNl0BkPfwM0Wzb4cSvw', name='My playlists')
    ]

    root_directory = ROOT_DIR

    def browse(self, uri):
        logger.info('__________________')
        logger.info('browse: ' + uri)
        if uri == self.ROOT_DIR.uri:
            return self._ROOT_DIR_CONTENTS
        elif uri.startswith("youtube:playlist"):
            logger.info('entered playlist')
            trackrefs=[]
            tracks=self.lookup(uri)
            for track in tracks:
                trackrefs.append(Ref.track(uri=track.uri, name=track.name))
            return trackrefs
        elif uri.startswith("youtube:collection"):
            logger.info('entered collection')
            playlistrefs=[]
            playlists=self.get_collection(uri)
            for playlist in playlists:
                playlistrefs.append(Ref.playlist(uri=playlist.uri, name=playlist.title.get()))
            return playlistrefs



    def search(self, query=None, uris=None, exact=False):
        # TODO Support exact search
        logger.info('youtube LibraryProvider.search "%s"', query)

        # handle only searching (queries with 'any') not browsing!
        if not (query and "any" in query):
            return None

        search_query = " ".join(query["any"])
        logger.info('Searching YouTube for query "%s"', search_query)

        try:
            entries = youtube.Entry.search(search_query)
        except Exception as e:
            logger.error('search error "%s"', e)
            return None

        # load playlist info (to get video_count) of all playlists together
        playlists = [entry for entry in entries if not entry.is_video]

        albums = []
        artists = []
        tracks = []

        logger.info(entries)

        for entry in entries:
            if entry.is_video:
                uri_base = "youtube:video"
                album = "YouTube Video"
                length = int(entry.length.get()) * 1000

                # # does it make sense to try to return youtube 'channels' as
                # # mopidy 'artists'? I'm not convinced.
                #if entry.channelId.get():
                #    artists.append(
                #            Artist(
                #                name=f"YouTube channel: {entry.channel.get()}",
                #                uri="yotube:channel/%s.%s" % (safe_url(entry.channel.get()), entry.channelId.get()),
                #                )
                #            )
                #else:
                #    logger.info("no channelId")

            else:
                uri_base = "youtube:playlist"
                album = "YouTube Playlist (%s videos)" % entry.video_count.get()
                length = 0

            name = entry.title.get()

            tracks.append(
                Track(
                    name=name.replace(";", ""),  # why is this .replace here?
                    comment=entry.id,
                    length=length,
                    artists=[Artist(name=entry.channel.get())],
                    album=Album(name=album),
                    uri="%s/%s.%s" % (uri_base, safe_url(name), entry.id),
                )
            )

        # load video info and playlist videos in the background. they should be
        # ready by the time the user adds search results to the playing queue
        for pl in playlists:
            name = pl.title.get()

            # does it make sense to return youtube 'playlists' as mopidy 'albums'?
            albums.append(
                Album(
                    name=name,
                    artists=[
                        Artist(
                            name=f"YouTube Playlist ({pl.video_count.get()} videos)"
                        )
                    ],
                    uri="%s/%s.%s"
                    % ("youtube:playlist", safe_url(name), pl.id),
                )
            )

            pl.videos  # start loading

        return SearchResult(
            uri="youtube:search", tracks=tracks, artists=artists, albums=albums
        )

    def get_collection(self, uri):
        channel_id = extract_id(uri)
        logger.info(channel_id)
        collection = youtube.Entry.get_collection(channel_id)
#        collection = youtube.Entry.search("playlist")
#        logger.info(collection)
#        for pl in collection:
#            logger.info(pl.title.get())
#       logger.info(response)
#       uris = ['youtube:playlist/Easy listening, bossa, etc.PLVWkvsDBrJmY1_aUV_uNwxFxjaUEEKEwO', 'youtube:playlist/Mixes late 2020.PLVWkvsDBrJmZX7K7vWkpvz_cqwdxhwSOq', 'youtube:playlist/Synth.PLVWkvsDBrJmYzyUfJgvh-8h-cUn86eWGS', 'youtube:playlist/Chill 2020.PLVWkvsDBrJmaTWF4O9PgWfGz8O-qQlRXU', 'youtube:playlist/Deep \\ Tech House.PLVWkvsDBrJmYK6VROwzofHzjbRJvZFHiw', 'youtube:playlist/Nature.PLVWkvsDBrJmbtRShYZ4evireiAV0C1DAV', 'youtube:playlist/Vaporwave.PLVWkvsDBrJmbtrQub-61rbo0wpL1ANMF9', 'youtube:playlist/Idm.PLVWkvsDBrJmbXLrzN-vqjG-EBxYFGzlhn', 'youtube:playlist/classic.PLVWkvsDBrJmb_XS76-hUmU0z9MQ7M2fGA', 'youtube:playlist/ретро.PLVWkvsDBrJmaTMTg3a6729FkwGcbeLqKs', 'youtube:playlist/jazz.PLVWkvsDBrJmYx7nHNLekgcBN82IWvUCi3', 'youtube:playlist/chill.PLVWkvsDBrJmZUw-pS4Qzs_Ac04SeqrViV', 'youtube:playlist/4:20.PLVWkvsDBrJmZry3_GSwkaY3bnTI5Lzi9o', 'youtube:playlist/Рецепты.PLVWkvsDBrJmbHgY1IwlFxzo-HDZw-zCX9', 'youtube:playlist/IT.PLVWkvsDBrJmYJkrDOkWzSM26MdkgW0B7x', 'youtube:playlist/Упражнения.PLVWkvsDBrJmZERA1RKT8lt6jRUA__Inje', 'youtube:playlist/ремонт.PLVWkvsDBrJmZmA8My3xN8EGWLWp6fZ9dG', 'youtube:playlist/Deep & dub.PLVWkvsDBrJmYzemPpwvLkn0AfMXPWfm4s', 'youtube:playlist/Ambient.PLVWkvsDBrJmbhsW2WwtsoXOFr4eTSzwEr', 'youtube:playlist/Sonic.PLVWkvsDBrJmbY00lIYFWYyHz-6hyNhvga', 'youtube:playlist/UK house.PLVWkvsDBrJmbJXAHCerPNljEhKubX3RU5', 'youtube:playlist/Old Days House.PLVWkvsDBrJmaFGx-aHNrzWJrGLMluIV8e', 'youtube:playlist/Progressive House.PLVWkvsDBrJmYCEt1d_U0IrRIlZJ520jNg', 'youtube:playlist/Chillhop.PLVWkvsDBrJmb6oaaQBJADuydGmj2YKur6'] 
#        uris = []
#        playlists = []
        for pl in collection:
            pl.uri="%s/%s.%s" % ("youtube:playlist", safe_url(pl.title.get()), pl.id)
        return collection



    def lookup(self, uri):
        """
        Called when the user adds a track to the playing queue, either from the
        search results, or directly by adding a yt:http://youtube.com/.... uri.
        uri can be of the form
            [yt|youtube]:<url to youtube video>
            [yt|youtube]:<url to youtube playlist>
            youtube:video/<title>.<id>
            youtube:playlist/<title>.<id>

        If uri is a video then a single track is returned. If it's a playlist the
        list of all videos in the playlist is returned.

        We also start loading the audio_url of all videos in the background, to
        be ready for playback (see YouTubePlaybackProvider.translate_uri).
        """

        logger.info('youtube LibraryProvider.lookup "%s"', uri)

        video_id = None
        playlist_id = None

#       # # should channels be returned?
#       channel_id = None
        if "youtube.com" in uri:
            url = urlparse(uri.replace("yt:", "").replace("youtube:", ""))
            req = parse_qs(url.query)
            print(req)
            if "list" in req:
                playlist_id = req.get("list")[0]
#            elif "channel/" in uri:
#                pass
            else:
                video_id = req.get("v")[0]

        elif "youtu.be" in uri:
            url = uri.replace("yt:", "").replace("youtube:", "")
            if not re.match("(?:http|https)://", url):
                url = "http://" + url
            video_id = urlparse(url).path
            if video_id[0] == "/":
                video_id = video_id[1:]

        elif "video/" in uri:
            video_id = extract_id(uri)
#       elif "channel/" in uri:
#           channel_id = "UCKLtqNl0BkPfwM0Wzb4cSvw"
#            channel_id = extract_id(uri)
#            logger.info(channel_id)
        else:
            playlist_id = extract_id(uri)

        if video_id:
            video = youtube.Video.get(video_id)
            video.audio_url  # start loading
            video.title.get()
            return [
                Track(
                    name=video.title.get().replace(
                        ";", ""
                    ),  # why is this .replace here?
                    comment=video.id,
                    length=video.length.get() * 1000,
                    artists=[Artist(name=video.channel.get())],
                    album=Album(name="YouTube Video",),
                    uri="youtube:video/%s.%s"
                    % (safe_url(video.title.get()), video.id),
                )
            ]

        
#       elif channel_id:
#           logger.info(channel_id)
#           logger.info("EXTRACTED___________")
#           channel = youtube.Channel.get(channel_id)
#
#           if not channel.videos.get():
#               logger.info('Cannot load "%s"', uri)
#               return []
#           videos = [v for v in channel.videos.get() if v.length.get() is not None]
#           album_name = "YouTube Video"

        else:
            playlist = youtube.Playlist.get(playlist_id)

            if not playlist.videos.get():
                logger.error('Cannot load "%s"', uri)
                return []

            # ignore videos for which no info was found (removed, etc)
            videos = [
                v for v in playlist.videos.get() if v.length.get() is not None
            ]
            album_name = playlist.title.get()

        # load audio_url in the background to be ready for playback
        for video in videos:
            video.audio_url  # start loading

        return [
            Track(
                name=video.title.get().replace(
                    ";", ""
                ),  # why is this .replace here?
                comment=video.id,
                length=video.length.get() * 1000,
                track_no=count,
                artists=[Artist(name=video.channel.get())],
                album=Album(name=album_name),
                uri="youtube:video/%s.%s"
                % (safe_url(video.title.get()), video.id),
            )
            for count, video in enumerate(videos, 1)
        ]

    def get_images(self, uris):
        return {uri: youtube.Video.get(uri).thumbnails.get() for uri in uris}


class YouTubePlaybackProvider(backend.PlaybackProvider):
    def translate_uri(self, uri):
        """
        Called when a track us ready to play, we need to return the actual url of
        the audio. uri must be of the form youtube:video/<title>.<id>
        (only videos can be played, playlists are expended into tracks by
        YouTubeLibraryProvider.lookup)
        """

        logger.info('youtube PlaybackProvider.translate_uri "%s"', uri)

        if "youtube:video/" not in uri:
            return None

        try:
            id = extract_id(uri)
            return youtube.Video.get(id).audio_url.get()
        except Exception as e:
            logger.error('translate_uri error "%s"', e)
            return None
