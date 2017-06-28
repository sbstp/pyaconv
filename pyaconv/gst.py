import os

from .fsutil import Path
from . import logging

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst  # noqa

GObject.threads_init()
Gst.init(None)


class BaseEncoder:

    def __init__(self, *, loop, src, dest, eos_cb=None, err_cb=None,
                 pipeline_desc=None):
        self._loop = loop
        self._pipeline = Gst.parse_launch(pipeline_desc)
        self._src = self._pipeline.get_by_name("src")
        self._enc = self._pipeline.get_by_name("enc")
        self._dest = self._pipeline.get_by_name("dest")
        self._bus = self._pipeline.get_bus()
        self._eos_cb = eos_cb
        self._err_cb = err_cb

        self._bus.add_watch(0, self._bus_callback, None)

        self._src.set_property("location", src)
        self._dest.set_property("location", dest)

    def start(self):
        self._pipeline.set_state(Gst.State.PLAYING)

    def __del__(self):
        self._pipeline.set_state(Gst.State.NULL)

    def _bus_callback(self, bus, message, _):
        # print(Gst.message_type_get_name(message.type))
        if message.type == Gst.MessageType.EOS:
            if self._eos_cb is not None:
                self._eos_cb(self._src.get_property("location"),
                             self._dest.get_property("location"))
        elif message.type == Gst.MessageType.ERROR:
            err, _ = message.parse_error()
            src_elem = None
            if isinstance(message.src, Gst.Element):
                fact = message.src.get_factory()
                src_elem = fact.get_name()
            if self._err_cb is not None:
                self._err_cb(err.message, src_elem)
        else:
            return True
        return False


_OPUS_PIPELINE = """filesrc name=src ! decodebin ! audioconvert ! \
audioresample ! opusenc name=enc ! oggmux ! filesink name=dest"""


class OpusEncoder(BaseEncoder):

    def __init__(self, *, loop, bitrate=64000, bitrate_type="vbr",
                 **kwargs):
        super().__init__(loop=loop, pipeline_desc=_OPUS_PIPELINE, **kwargs)
        self._enc.set_property("bitrate", bitrate)
        Gst.util_set_object_arg(self._enc, "bitrate-type", bitrate_type)


class Worker:

    def __init__(self, loop, queue, journal, finished_cb):
        self._loop = loop
        self._queue = queue
        self._journal = journal
        self._finished = False
        self._finished_cb = finished_cb

    def _eos_cb(self, src, dest):
        dest = Path(dest)
        self._journal.add(dest)
        self._next()

    def _next(self):
        if len(self._queue) > 0:
            src, dest = self._queue.popleft()
            logging.info("encoding {}", src.absolute())
            enc = OpusEncoder(loop=self._loop, src=src, dest=dest,
                              eos_cb=self._eos_cb,
                              err_cb=self._error)
            enc.start()
        else:
            self._finished = True
            self._finished_cb()

    def start(self):
        self._next()

    @property
    def finished(self):
        return self._finished

    def _error(self, error_msg, src_elem):
        if src_elem is not None:
            logging.error("gstreamer error in element '{}': {}\n", src_elem,
                          error_msg)
        else:
            logging.error("gstreamer error: %s", error_msg)
        self._loop.quit()


class Scheduler:

    def __init__(self, queue, journal, threads=None):
        if threads is None:
            threads = max(1, os.cpu_count() - 1)
        self._loop = GObject.MainLoop()
        self._workers = [Worker(self._loop, queue, journal,
                                self._worker_finished)
                         for _ in range(threads)]
        self._has_quit = False

    def _worker_finished(self):
        if all(w.finished for w in self._workers):
            self._has_quit = True
            self._loop.quit()

    def run(self):
        for w in self._workers:
            w.start()
        # check for early exits when the queue is empty
        if not self._has_quit:
            self._loop.run()
