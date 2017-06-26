from collections import deque
import sys

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst # noqa

GObject.threads_init()
Gst.init(None)


def printf(fmt, *args, fd=sys.stdout):
    fd.write(fmt % (args))
    fd.flush()


class RawEncoder:

    def __init__(self, queue, loop, pipeline_desc):
        self._queue = queue
        self._loop = loop
        self._pipeline = Gst.parse_launch(pipeline_desc)
        self._src = self._pipeline.get_by_name("src")
        self._enc = self._pipeline.get_by_name("enc")
        self._dest = self._pipeline.get_by_name("dest")
        self._bus = self._pipeline.get_bus()

        self._bus.add_watch(0, self._bus_callback, None)

    def __del__(self):
        self._pipeline.set_state(Gst.State.NULL)

    def _set_src(self, path):
        self._src.set_property("location", path)

    def _set_dest(self, path):
        self._dest.set_property("location", path)

    def _play(self):
        self._pipeline.set_state(Gst.State.PLAYING)

    def _begin_encode(self, src, dest):
        printf("Encoding %s\n", src)
        self._set_src(src)
        self._set_dest(dest)
        self._play()

    def start(self):
        try:
            src, dest = self._queue.popleft()
            self._begin_encode(src, dest)
        except IndexError:
            raise ValueError("queue is empty")

    def _bus_callback(self, bus, message, _):
        # print(Gst.message_type_get_name(message.type))
        if message.type == Gst.MessageType.EOS:
            return self.end_of_stream()
        elif message.type == Gst.MessageType.ERROR:
            err, _ = message.parse_error()
            src_elem = None
            if isinstance(message.src, Gst.Element):
                fact = message.src.get_factory()
                src_elem = fact.get_name()
            return self.error(err.message, src_elem)
        elif message.type == Gst.MessageType.STATE_CHANGED:
            _, newstate, _ = message.parse_state_changed()
            print(newstate, message.src.get_name())
            if newstate == Gst.State.READY and message.src == self._pipeline:
                print("we in")
                if len(self._queue) > 0:
                    src, dest = self._queue.popleft()
                    self._begin_encode(src, dest)
                    return True
                else:
                    self._loop.quit()
                    return False
        return True

    def end_of_stream(self):
        self._pipeline.set_state(Gst.State.READY)
        return True

    def error(self, error_msg, src_elem):
        print("err")
        if src_elem is not None:
            printf("Error in element '%s': %s\n", src_elem,
                   error_msg,
                   fd=sys.stderr)
        else:
            printf("Error: %s", error_msg, fd=sys.stderr)
        self._loop.quit()
        return False


_OPUS_PIPELINE = """filesrc name=src ! decodebin ! audioconvert ! \
audioresample ! opusenc name=enc ! oggmux ! filesink name=dest"""


class OpusEncoder(RawEncoder):

    def __init__(self, queue, loop, *, bitrate=64000, bitrate_type="vbr"):
        super().__init__(queue, loop, _OPUS_PIPELINE)
        self._enc.set_property("bitrate", bitrate)
        Gst.util_set_object_arg(self._enc, "bitrate-type", bitrate_type)


files = [(file_src, file_src + '.ogg') for file_src in sys.argv[1:]]
files = deque(files)

loop = GObject.MainLoop()
p = OpusEncoder(files, loop)
p.start()
loop.run()
