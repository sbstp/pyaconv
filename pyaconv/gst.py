from gi.repository import GObject, Gst
import os


from .fsutil import Path
from . import logging


class BaseProperty:

    def __init__(self, name, help=None):
        self.name = name
        self.help = help

    def add_argument(self, arg_parser):
        raise NotImplementedError


class Property(BaseProperty):

    def __init__(self, name, *, type, default, help=None):
        super().__init__(name, help)
        self.type = type
        self.default = default

    def add_argument(self, arg_parser):
        if self.type is not bool:
            arg_parser.add_argument("--" + self.name,
                                    type=self.type,
                                    default=self.default,
                                    metavar="",
                                    help=self.help + " (default: {})".format(self.default))
        else:
            true_def = " (default)" if self.default else ""
            false_def = " (default)" if not self.default else ""
            arg_parser.add_argument("--" + self.name,
                                    default=self.default,
                                    dest=self.name,
                                    action="store_true",
                                    help=self.help + true_def)
            arg_parser.add_argument("--no-" + self.name,
                                    default=self.default,
                                    dest=self.name,
                                    action="store_false",
                                    help="no " + self.help + false_def)


class PropertyEnum(BaseProperty):

    def __init__(self, name, *, values, default, type=str, help=None):
        assert default in values
        super().__init__(name, help)
        self.values = values
        self.default = default
        self.type = type

    def add_argument(self, arg_parser):
        s = ', '.join(str(v) for v in self.values)
        arg_parser.add_argument("--" + self.name,
                                choices=self.values,
                                default=self.default,
                                metavar="",
                                type=self.type,
                                help=self.help + " (default: {}) {{{}}}".format(self.default, s), )


class PropertyRange(BaseProperty):

    def __init__(self, name, *, min, max, default, help=None):
        super().__init__(name, help)
        self.min = min
        self.max = max
        self.default = default

    def add_argument(self, arg_parser):
        arg_parser.add_argument("--" + self.name,
                                type=int,
                                choices=range(self.min, self.max + 1),
                                default=self.default or None,
                                help=self.help + " (default: {})".format(self.default or "None"),
                                metavar="[{}-{}]".format(self.min, self.max))


class BaseEncoder:

    def __init__(self, *, loop, src, dest, eos_cb=None, err_cb=None,
                 props=None):
        pipeline = self.__class__.pipeline(props)
        self._loop = loop
        self._pipeline = Gst.parse_launch(pipeline)
        self._src = self._pipeline.get_by_name("src")
        self._enc = self._pipeline.get_by_name("enc")
        self._dest = self._pipeline.get_by_name("dest")
        self._bus = self._pipeline.get_bus()
        self._eos_cb = eos_cb
        self._err_cb = err_cb

        self.src = src
        self.dest = dest
        self.setter = self._pipeline.get_by_interface(Gst.TagSetter)

        self._bus.add_watch(0, self._bus_callback, None)

        self._src.set_property("location", src)
        self._dest.set_property("location", dest)

        self.apply_props(props, self._enc)

    def start(self):
        """
        Start the Gstreamer pipeline, starting the encoding process.
        """
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

    def apply_props(self, props, enc):
        """
        Called to apply the properties to the gstreamer encoder module, after initialization.
        """
        raise NotImplementedError

    @classmethod
    def extension(cls):
        """
        Return the extension of files generated by this encoder, e.g. "ogg", "mp3".
        """
        raise NotImplementedError

    @classmethod
    def pipeline(cls, props):
        """
        Return the pipeline string used to initialize this encoder class. There should be a
        filesrc named src and a filesink named dest. The encoder should be named enc. The
        BaseEncoder will automatically get those objects from the pipeline.
        """
        raise NotImplementedError


class Worker:

    def __init__(self, loop, queue, journal, finished_cb, encoder, props):
        self._loop = loop
        self._queue = queue
        self._journal = journal
        self._finished = False
        self._finished_cb = finished_cb
        self._encoder = encoder
        self._props = props

    def _eos_cb(self, src, dest):
        dest = Path(dest)
        self._journal.add(dest)
        self._next()

    def _next(self):
        if len(self._queue) > 0:
            src, dest = self._queue.popleft()
            logging.info("encoding {} -> {}", src, dest)
            enc = self._encoder(loop=self._loop, src=src, dest=dest,
                                eos_cb=self._eos_cb,
                                err_cb=self._error,
                                props=self._props)
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

    def __init__(self, queue, journal, *, encoder, props, threads=None):
        if threads is None:
            threads = max(1, os.cpu_count() - 1)
        self._loop = GObject.MainLoop()
        self._workers = [Worker(self._loop, queue, journal,
                                self._worker_finished, encoder, props)
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


def duration(path):
    """
    Accurate detection of MP3 duration: https://blog.affien.com/archives/2009/04/19/gstreamer-accurate-duration/
    """
    pipeline = Gst.parse_launch("filesrc name=src ! decodebin ! fakesink name=sink")
    src = pipeline.get_by_name("src")
    sink = pipeline.get_by_name("sink")
    bus = pipeline.get_bus()

    src.set_property("location", str(path.absolute()))
    pipeline.set_state(Gst.State.PLAYING)

    message = bus.timed_pop_filtered(Gst.CLOCK_TIME_NONE, Gst.MessageType.ERROR | Gst.MessageType.EOS)
    try:
        if message.type == Gst.MessageType.EOS:
            query = Gst.Query.new_duration(Gst.Format.TIME)
            if sink.query(query):
                _, duration = query.parse_duration()
                return duration
            else:
                raise Exception("duration query failed")
        elif message.type == Gst.MessageType.ERROR:
            err, _ = message.parse_error()
            raise Exception(err)
    finally:
        pipeline.set_state(Gst.State.NULL)
