#!/usr/bin/python
#
# Copyright (c) 2013,Thibault Saunier <thibault.saunier@collabora.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin St, Fifth Floor,
# Boston, MA 02110-1301, USA.
import os
import urlparse
import subprocess
import ConfigParser
from loggable import Loggable

from baseclasses import GstValidateTest, TestsManager, Test, Scenario, NamedDic
from utils import MediaFormatCombination, get_profile,\
    path2url, DEFAULT_TIMEOUT, which, GST_SECOND, Result, \
    compare_rendered_with_original


DEFAULT_GST_VALIDATE = "gst-validate-1.0"
DEFAULT_GST_VALIDATE_TRANSCODING = "gst-validate-transcoding-1.0"
DISCOVERER_COMMAND = "gst-validate-media-check-1.0 --discover-only"

MEDIA_INFO_EXT = "media_info"
STREAM_INFO = "stream_info"

SPECIAL_PROTOCOLS = [("application/x-hls", "hls")]

PLAYBACK_TESTS = ["playbin uri=__uri__ audio_sink=autoaudiosink video_sink=autovideosink"]
COMBINATIONS = [
    MediaFormatCombination("ogg", "vorbis", "theora"),
    MediaFormatCombination("webm", "vorbis", "vp8"),
    MediaFormatCombination("mp4", "mp3", "h264"),
    MediaFormatCombination("mkv", "vorbis", "h264")]

PROTOCOL_TIMEOUTS = {"http": 60,
                     "hls": 60}

G_V_BLACKLISTED_TESTS = [("validate.hls.playback.fast_forward.*", "https://bugzilla.gnome.org/show_bug.cgi?id=698155"),
                         ("validate.hls.playback.seek_with_stop.*", "https://bugzilla.gnome.org/show_bug.cgi?id=723268"),
                         ("validate.*.simple_backward.*webm$", "https://bugzilla.gnome.org/show_bug.cgi?id=679250"),
                         ("validate.http.simple_backward.*", "https://bugzilla.gnome.org/show_bug.cgi?id=723270"),
                         ("validate.http.playback.seek_with_stop.*webm", "matroskademux.gst_matroska_demux_handle_seek_push: Seek end-time not supported in streaming mode"),
                         ("validate.http.playback.seek_with_stop.*mkv", "matroskademux.gst_matroska_demux_handle_seek_push: Seek end-time not supported in streaming mode")
                         ]

G_V_SCENARIOS = {"file": [Scenario.get_scenario("play_15s"),
                          Scenario.get_scenario("simple_backward"),
                          Scenario.get_scenario("fast_forward"),
                          Scenario.get_scenario("seek_forward"),
                          Scenario.get_scenario("seek_backward"),
                          Scenario.get_scenario("seek_with_stop"),
                          Scenario.get_scenario("scrub_forward_seeking")],
                 "http": [Scenario.get_scenario("play_15s"),
                          Scenario.get_scenario("fast_forward"),
                          Scenario.get_scenario("seek_forward"),
                          Scenario.get_scenario("seek_backward"),
                          Scenario.get_scenario("seek_with_stop"),
                          Scenario.get_scenario("simple_backward")],
                 "hls": [Scenario.get_scenario("play_15s"),
                         Scenario.get_scenario("fast_forward"),
                         Scenario.get_scenario("seek_forward"),
                         Scenario.get_scenario("seek_with_stop"),
                         Scenario.get_scenario("seek_backward")],
                 }




class GstValidateLaunchTest(GstValidateTest):
    def __init__(self, classname, options, reporter, pipeline_desc,
                 timeout=DEFAULT_TIMEOUT, scenario=None, file_infos=None):
        try:
            timeout = PROTOCOL_TIMEOUTS[file_infos.get("file-info", "protocol")]
        except KeyError:
            pass

        super(GstValidateLaunchTest, self).__init__(DEFAULT_GST_VALIDATE, classname,
                                              options, reporter,
                                              scenario=scenario,
                                              timeout=timeout)

        self.pipeline_desc = pipeline_desc
        self.file_infos = file_infos

    def build_arguments(self):
        GstValidateTest.build_arguments(self)
        self.add_arguments(self.pipeline_desc)

    def get_current_value(self):
        return self.get_current_position()


class GstValidateMediaCheckTest(Test):
    def __init__(self, classname, options, reporter, media_info_path, uri, timeout=DEFAULT_TIMEOUT):
        super(GstValidateMediaCheckTest, self).__init__(DISCOVERER_COMMAND, classname,
                                              options, reporter,
                                              timeout=timeout)
        self._uri = uri
        self._media_info_path = urlparse.urlparse(media_info_path).path

    def build_arguments(self):
        self.add_arguments(self._uri, "--expected-results",
                           self._media_info_path)


class GstValidateTranscodingTest(GstValidateTest):
    def __init__(self, classname, options, reporter,
                 combination, uri, file_infos, timeout=DEFAULT_TIMEOUT,
                 scenario=Scenario.get_scenario("play_15s")):

        try:
            timeout = PROTOCOL_TIMEOUTS[file_infos.get("file-info", "protocol")]
        except KeyError:
            pass

        try:
            # FIXME Come up with a less arbitrary calculation!
            hard_timeout = 4 * scenario.max_duration + timeout
        except AttributeError:
            hard_timeout = None
            pass

        super(GstValidateTranscodingTest, self).__init__(
            DEFAULT_GST_VALIDATE_TRANSCODING, classname,
            options, reporter, scenario=scenario, timeout=timeout,
            hard_timeout=hard_timeout)

        self.file_infos = file_infos
        self.uri = uri
        self.combination = combination
        self.dest_file = ""

    def set_rendering_info(self):
        self.dest_file = os.path.join(self.options.dest,
                                 os.path.basename(self.uri) +
                                 '-' + self.combination.acodec +
                                 self.combination.vcodec + '.' +
                                 self.combination.container)
        if urlparse.urlparse(self.dest_file).scheme == "":
            self.dest_file = path2url(self.dest_file)

        profile = get_profile(self.combination)
        self.add_arguments("-o", profile)

    def build_arguments(self):
        GstValidateTest.build_arguments(self)
        self.set_rendering_info()
        self.add_arguments(self.uri, self.dest_file)

    def get_current_value(self):
        return self.get_current_size()

    def check_results(self):
        if self.process.returncode == 0:
            orig_duration = long(self.file_infos.get("media-info", "file-duration"))
            res, msg = compare_rendered_with_original(orig_duration, self.dest_file)
            self.set_result(res, msg)
        else:
            GstValidateTest.check_results(self)


class GstValidateManager(TestsManager, Loggable):

    name = "validate"

    def __init__(self):
        TestsManager.__init__(self)
        Loggable.__init__(self)
        self._uris = []

    def init(self):
        if which(DEFAULT_GST_VALIDATE) and which(DEFAULT_GST_VALIDATE_TRANSCODING):
            return True

        return False

    def list_tests(self):
        for test_pipeline in PLAYBACK_TESTS:
            self._add_playback_test(test_pipeline)

        TIMEOUT_BY_PROTOCOL = {
            "http": 60,
            "hls": 120
        }
        for uri, mediainfo in self._list_uris():
            try:
                timeout = TIMEOUT_BY_PROTOCOL[mediainfo.config.get("file-info", "protocol")]
            except KeyError:
                timeout = DEFAULT_TIMEOUT

            classname = "validate.media_check.%s" % (os.path.splitext(os.path.basename(uri))[0].replace(".", "_"))
            self.add_test(GstValidateMediaCheckTest(classname,
                                                    self.options,
                                                    self.reporter,
                                                    mediainfo.path,
                                                    uri,
                                                    timeout=timeout))

        for uri, mediainfo in self._list_uris():
            if mediainfo.config.getboolean("media-info", "is-image") is True:
                continue
            for comb in COMBINATIONS:
                classname = "validate.%s.transcode.to_%s.%s" % (mediainfo.config.get("file-info", "protocol"),
                                                                str(comb).replace(' ', '_'),
                                                                os.path.splitext(os.path.basename(uri))[0].replace(".", "_"))
                self.add_test(GstValidateTranscodingTest(classname,
                                                         self.options,
                                                         self.reporter,
                                                         comb, uri,
                                                         mediainfo.config))

    def _check_discovering_info(self, media_info, uri=None):
        self.debug("Checking %s", media_info)
        config = ConfigParser.ConfigParser()
        f = open(media_info)
        config.readfp(f)
        try:
            # Just testing that the vairous mandatory infos are present
            caps = config.get("media-info", "caps")
            config.get("media-info", "file-duration")
            config.get("media-info", "seekable")
            if uri is None:
                uri = config.get("file-info", "uri")
            config.set("file-info", "protocol", urlparse.urlparse(uri).scheme)
            for caps2, prot in SPECIAL_PROTOCOLS:
                if caps2 == caps:
                    config.set("file-info", "protocol", prot)
                    break
            self._uris.append((uri,
                               NamedDic({"path": media_info,
                                         "config": config})))
        except ConfigParser.NoOptionError as e:
            self.debug("Exception: %s for %s", e, media_info)
        f.close()

    def _discover_file(self, uri, fpath):
        try:
            media_info = "%s.%s" % (fpath, MEDIA_INFO_EXT)
            args = DISCOVERER_COMMAND.split(" ")
            args.append(uri)
            if os.path.isfile(media_info):
                self._check_discovering_info(media_info, uri)
                return True
            elif fpath.endswith(STREAM_INFO):
                self._check_discovering_info(fpath)
                return True
            elif self.options.generate_info:
                args.extend(["--output-file", media_info])
            else:
                return True

            subprocess.check_output(args)
            self._check_discovering_info(media_info, uri)

            return True

        except subprocess.CalledProcessError as e:
            self.debug("Exception: %s", e)
            return False

    def _list_uris(self):
        if self._uris:
            return self._uris

        if not self.args:
            if isinstance(self.options.paths, str):
                self.options.paths = [os.path.join(self.options.paths)]

            for path in self.options.paths:
                for root, dirs, files in os.walk(path):
                    for f in files:
                        fpath = os.path.join(path, root, f)
                        if os.path.isdir(fpath) or fpath.endswith(MEDIA_INFO_EXT):
                            continue
                        else:
                            self._discover_file(path2url(fpath), fpath)

        self.debug("Uris found: %s", self._uris)

        return self._uris

    def _get_fname(self, scenario, protocol=None):
        if scenario is not None and scenario.name.lower() != "none":
            return "%s.%s.%s.%s" % ("validate", protocol, "playback", scenario.name)

        return "%s.%s.%s" % ("validate", protocol, "playback")

    def _add_playback_test(self, pipe):
        if self.options.mute:
            if "autovideosink" in pipe:
                pipe = pipe.replace("autovideosink", "fakesink")
            if "autoaudiosink" in pipe:
                pipe = pipe.replace("autoaudiosink", "fakesink")

        if "__uri__" in pipe:
            for uri, minfo in self._list_uris():
                npipe = pipe
                protocol = minfo.config.get("file-info", "protocol")

                for scenario in G_V_SCENARIOS[protocol]:
                    if minfo.config.getboolean("media-info", "seekable") is False:
                        self.debug("Do not run %s as %s does not support seeking",
                                   scenario, uri)
                        continue

                    if self.options.mute:
                        # In case of seeking we need to make sure the pipeline
                        # is run sync, otherwize some tests will fail
                        npipe = pipe.replace("fakesink", "'fakesink sync=true'")

                    fname = "%s.%s" % (self._get_fname(scenario,
                                       protocol),
                                       os.path.basename(uri).replace(".", "_"))
                    self.debug("Adding: %s", fname)

                    self.add_test(GstValidateLaunchTest(fname,
                                                        self.options,
                                                        self.reporter,
                                                        npipe.replace("__uri__", uri),
                                                        scenario=scenario,
                                                        file_infos=minfo.config)
                                 )
        else:
            self.add_test(GstValidateLaunchTest(self._get_fname(scenario, "testing"),
                                                self.options,
                                                self.reporter,
                                                pipe,
                                                scenario=scenario))

    def needs_http_server(self):
        for uri, mediainfo in self._list_uris():
            if urlparse.urlparse(uri).scheme == "http" and \
                    "127.0.0.1:%s" % (self.options.http_server_port) in uri:
                return True

    def get_blacklisted(self):
        return G_V_BLACKLISTED_TESTS