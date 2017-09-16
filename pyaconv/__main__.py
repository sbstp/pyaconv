from collections import deque
import sys

from . import fsutil, gst, logging
from .fsutil import Path
from .gst import Scheduler
from .journal import Journal

if __name__ == '__main__':
    logging.info("pyaconv starting...")

    # default encoder is Opus with default properties
    encoder = gst.OpusEncoder
    props = encoder.defaults()

    src_dir = Path(sys.argv[1])
    dest_dir = Path(sys.argv[2])

    journal = Journal(dest_dir)

    audio_files, other_files = fsutil.walk(src_dir, dest_dir, encoder.extension())

    other_files = deque(journal.remove_journaled(other_files))
    audio_files = deque(journal.remove_journaled(audio_files))

    fsutil.build_tree(other_files)
    fsutil.build_tree(audio_files)
    fsutil.hardlink_tree(other_files, journal)

    s = Scheduler(audio_files, journal, encoder=encoder, props=props)
    s.run()

    logging.info("pyaconf finished.")
