from collections import deque
import argparse
# import os

from . import fsutil, gst, logging
from .fsutil import Path
from .gst import Scheduler
from .journal import Journal


def main():
    codecs = dict(
        opus=gst.OpusEncoder,
        mp3=gst.Mp3Encoder,
        flac=gst.FlacEncoder,
    )

    p = argparse.ArgumentParser(prog="pyaconv", add_help=False)
    p.add_argument("src", nargs="?", default=None)
    p.add_argument("dest", nargs="?", default=None)
    p.add_argument("-c", "--codec", choices=list(codecs.keys()), required=True)
    # p.add_argument("--cpu", type=int, default=max(1, os.cpu_count() - 1))
    a, _ = p.parse_known_args()

    # default encoder is Opus with default properties
    encoder = codecs[a.codec]
    props = encoder.properties()

    prop_names = []
    for prop in props:
        prop.add_argument(p)
        prop_names.append(prop.name)

    a = p.parse_args()

    if not a.src:
        p.print_help()
        exit()

    src_dir = Path(a.src)
    if a.dest:
        dest_dir = Path(a.dest)
    else:
        dest_dir = Path(a.src).with_suffix('.' + a.codec)

    logging.info("source directory is {}", src_dir.absolute())
    logging.info("destination directory is {}", dest_dir.absolute())

    vals = {}
    for n in prop_names:
        vals[n] = getattr(a, n.replace('-', '_'))

    journal = Journal(dest_dir)

    audio_files, other_files = fsutil.walk(src_dir, dest_dir, encoder.extension())

    other_files = deque(journal.remove_journaled(other_files))
    audio_files = deque(journal.remove_journaled(audio_files))

    fsutil.build_tree(other_files)
    fsutil.build_tree(audio_files)
    fsutil.hardlink_tree(other_files, journal)

    s = Scheduler(audio_files, journal, encoder=encoder, props=vals)
    s.run()


if __name__ == '__main__':
    main()
