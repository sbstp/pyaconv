import gi
gi.require_version('Gst', '1.0')

from gi.repository import GObject, Gst  # noqa

GObject.threads_init()
Gst.init(None)
