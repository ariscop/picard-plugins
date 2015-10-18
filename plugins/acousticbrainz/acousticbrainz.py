# -*- coding: utf-8 -*-
# Acousticbrainz plugin for Picard
# Copyright (C) 2015  Andrew Cook
# Copyright (C) 2015  Sophist
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

PLUGIN_NAME = u'AcousticBrainz'
PLUGIN_AUTHOR = u'Andrew Cook, Sophist'
PLUGIN_DESCRIPTION = u'''Add's the following tags:
<ul>
<li>Key (in ID3v2.3 format)</li>
<li>Beats Per Minute (BPM)</li>
<li>Genre</li>
<li>Mood</li>
</ul>
from the AcousticBrainz database.<br/><br/>
Note: This plugin requires Picard 1.4.'''
PLUGIN_LICENSE = "GPL-2.0"
PLUGIN_LICENSE_URL = "https://www.gnu.org/licenses/gpl-2.0.txt"
PLUGIN_VERSION = "0.1"
PLUGIN_API_VERSIONS = ["1.4.0"] # Requires support for TKEY which is in 1.4

import json
from functools import partial
from picard import config, log
from picard.util import LockableObject
from picard.metadata import register_track_metadata_processor
from picard.webservice import REQUEST_DELAY

ACOUSTICBRAINZ_HOST = "acousticbrainz.org"
ACOUSTICBRAINZ_PORT = 80

REQUEST_DELAY[(ACOUSTICBRAINZ_HOST, ACOUSTICBRAINZ_PORT)] = 50

def album_add_request(album):
    album._requests += 1

def album_remove_request(album):
    album._requests -= 1
    album._finalize_loading(None)

class AcousticBrainz:
    def __init__(self, endpoint, callback):
        self.endpoint = endpoint
        self.callback = callback

    def __call__(self, album, track_metadata, trackXmlNode, releaseXmlNode):
        album.tagger.xmlws.download(
            ACOUSTICBRAINZ_HOST,
            ACOUSTICBRAINZ_PORT,
            u"/%s/%s" % (track_metadata["musicbrainz_recordingid"], self.endpoint),
            partial(self._response, album, track_metadata),
            priority=True
        )
        album_add_request(album)

    def _response(self, album, track_metadata, response, reply, error):
        if error:
            log.error(u"%s: Network error retrieving acousticBrainz data for recordingId %s",
                PLUGIN_NAME, track_metadata['musicbrainz_recordingid'])
            album_remove_request(album)
            return

        try:
            response = json.loads(response)
            self.callback(album, track_metadata, response)
        except Exception as e:
            log.error(u"%s: Error handling %s AcousticBrainz data for recordingId %s: %s",
                (PLUGIN_NAME, self.endpoint, track_metadata["musicbrainz_recordingid"], str(e)))

        album_remove_request(album)


def mood_genre(album, track_metadata, data):
    moods = []
    genres = []

    data = data["highlevel"]
    for k, v in data.items():
        if k.startswith("genre_") and not v["value"].startswith("not_"):
            genres.append(v["value"])
        if k.startswith("mood_") and not v["value"].startswith("not_"):
            moods.append(v["value"])

    track_metadata["genre"] = genres
    track_metadata["mood"] = moods

register_track_metadata_processor(AcousticBrainz("high-level", mood_genre))

def tonal_rhythm(album, track_metadata, data):
    if "tonal" in data:
        if "key_key" in data["tonal"]:
            key = data["tonal"]["key_key"]
            if "key_scale" in data["tonal"]:
                scale = data["tonal"]["key_scale"]
                if scale == "minor":
                    key += "m"
            track_metadata["key"] = key
            log.debug(u"%s: Track '%s' is in key %s", PLUGIN_NAME, track_metadata["title"], key)
    if "rhythm" in data:
        if "bpm" in data["rhythm"]:
            bpm = int(data["rhythm"]["bpm"] + 0.5)
            track_metadata["bpm"] = bpm
            log.debug(u"%s: Track '%s' has %s bpm", PLUGIN_NAME, track_metadata["title"], bpm)

register_track_metadata_processor(AcousticBrainz("low-level", tonal_rhythm))
