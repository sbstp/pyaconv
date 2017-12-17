from gi.repository import Gst

from .gst import BaseEncoder, Property, PropertyEnum, PropertyRange

_OPUS_PIPELINE = """filesrc name=src ! decodebin ! audioconvert ! \
audioresample ! opusenc name=enc ! oggmux ! filesink name=dest"""


class OpusEncoder(BaseEncoder):

    def apply_props(self, props, enc):
        enc.set_property("bitrate", props["bitrate"])
        Gst.util_set_object_arg(enc, "bitrate-type", props["bitrate-type"])
        Gst.util_set_object_arg(enc, "audio-type", props["audio-type"])

    @classmethod
    def properties(cls):
        return (
            Property("bitrate", type=int, default=64000, help="bitrate is bits per second"),
            PropertyEnum("bitrate-type", values=["cbr", "vbr",
                                                 "constrained_vbr"], default="vbr", help="bitrate type"),
            PropertyEnum("audio-type", values=["generic", "voice"],
                         default="generic", help="audio type to optimize for"),
        )

    @classmethod
    def extension(cls):
        return "ogg"

    @classmethod
    def pipeline(cls, _):
        return _OPUS_PIPELINE


_MP3_PIPELINE_ID3 = """filesrc name=src ! decodebin ! audioconvert ! \
audioresample ! lamemp3enc name=enc ! id3mux ! filesink name=dest"""

_MP3_PIPELINE_ID3V2 = """filesrc name=src ! decodebin ! audioconvert ! \
audioresample ! lamemp3enc name=enc ! id3v2mux ! filesink name=dest"""


class Mp3Encoder(BaseEncoder):

    def apply_props(self, props, enc):
        if props["bitrate"]:
            Gst.util_set_object_arg(enc, "target", "bitrate")
            enc.set_property("cbr", True)
            enc.set_property("bitrate", props["bitrate"])
        else:
            Gst.util_set_object_arg(enc, "target", "quality")
            enc.set_property("cbr", props["cbr"])
            enc.set_property("quality", props["quality"])

        enc.set_property("mono", props["mono"])
        Gst.util_set_object_arg(enc, "encoding-engine-quality", props["encoding-engine-quality"])

    @classmethod
    def properties(cls):
        # gst-inspect-1.0 lamemp3enc
        return (
            PropertyRange("bitrate", min=8, max=320, default=None,
                          help="bitrate is kilobits per second (implies CBR)"),
            PropertyRange("quality", min=0, max=10, default=4,
                          help="quality 0 being best, 10 being worst"),
            Property("cbr", type=bool, default=False, help="CBR encoding"),
            PropertyEnum("encoding-engine-quality", values=["fast", "standard", "high"],
                         default="high", help="quality/speed of the encoding engine"),
            Property("mono", type=bool, default=False, help="mono encoding"),
            Property("id3v2", type=bool, default=False, help="Use id3v2 tags")
        )

    @classmethod
    def extension(cls):
        return "mp3"

    @classmethod
    def pipeline(cls, props):
        if props["id3v2"]:
            return _MP3_PIPELINE_ID3V2
        return _MP3_PIPELINE_ID3


_FLAC_PIPELINE_16 = """filesrc name=src ! decodebin ! audioconvert ! \
audioresample ! audio/x-raw, format=S16LE ! flacenc name=enc ! \
filesink name=dest"""

_FLAC_PIPELINE_24 = """filesrc name=src ! decodebin ! audioconvert ! \
audioresample ! audio/x-raw, format=S24LE ! flacenc name=enc ! \
filesink name=dest"""

_FLAC_PIPELINE_32 = """filesrc name=src ! decodebin ! audioconvert ! \
audioresample ! audio/x-raw, format=S24_32LE ! flacenc name=enc ! \
filesink name=dest"""


class FlacEncoder(BaseEncoder):

    def apply_props(self, props, enc):
        enc.set_property("escape-coding", True)
        enc.set_property("exhaustive-model-search", True)
        Gst.util_set_object_arg(enc, "quality", props["quality"])

    @classmethod
    def properties(cls):
        return (
            PropertyEnum("bit-depth", values=[16, 24, 32], type=int,
                         default=16, help="bit depth per sample"),
            PropertyEnum("quality", values=[str(q) for q in range(0, 9)],
                         default="5", help="compression quality: 0 fastest ; 8 best"),
        )

    @classmethod
    def extension(cls):
        return "flac"

    @classmethod
    def pipeline(cls, props):
        depth = props["bit-depth"]
        if depth == 16:
            return _FLAC_PIPELINE_16
        elif depth == 24:
            return _FLAC_PIPELINE_24
        elif depth == 32:
            return _FLAC_PIPELINE_32
        else:
            raise ValueError("invalid bit depth, expected 16, 24 or 32")


registry = dict(
    opus=OpusEncoder,
    mp3=Mp3Encoder,
    flac=FlacEncoder,
)
