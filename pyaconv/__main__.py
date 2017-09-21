from collections import deque
import argparse
import os
import time

from . import fsutil, logging, codecs
from .fsutil import Path
from .gst import Scheduler
from .journal import Journal, VoidJournal


def compute_paths(args):
    src_dir = Path(args.src)
    if args.dest:
        dest_dir = Path(args.dest)
    else:
        dest_dir = Path(args.src).with_suffix('.' + args.codec)
    return src_dir, dest_dir


def walk_and_clone(journal, src_dir, dest_dir, encoder):
    audio_files, other_files = fsutil.walk(src_dir, dest_dir, encoder.extension())

    other_files = deque(journal.remove_journaled(other_files))
    audio_files = deque(journal.remove_journaled(audio_files))

    fsutil.build_tree(other_files)
    fsutil.build_tree(audio_files)
    fsutil.hardlink_tree(other_files, journal)

    return audio_files


def get_properties(args, props):
    prop_names = [p.name for p in props]
    vals = {}
    for n in prop_names:
        vals[n] = getattr(args, n.replace('-', '_'))
    return vals


def format_time(time):
    hours, rem = divmod(time, 3600)
    mins, secs = divmod(rem, 60)
    return "{:02}:{:02}:{:02}".format(int(hours), int(mins), int(secs))


def main():
    p = argparse.ArgumentParser(prog="pyaconv", add_help=False)
    p.add_argument("src", nargs="?", default=None, help="source directory")
    p.add_argument("dest", nargs="?", default=None, help="destination directory, optional")
    p.add_argument("-c", dest="codec", choices=list(codecs.registry.keys()),
                   required=True, help="codec to use")
    p.add_argument("-t", type=int, dest="threads", default=max(1, os.cpu_count() - 1), metavar="",
                   help="number of threads, defaults to cpu count - 1")
    p.add_argument("--no-inc", default=False, action="store_true", help="disable incremental support")
    args, _ = p.parse_known_args()

    encoder = codecs.registry[args.codec]
    props = encoder.properties()

    for prop in props:
        prop.add_argument(p)

    args = p.parse_args()

    if not args.src:
        p.print_help()
        exit()

    src_dir, dest_dir = compute_paths(args)

    logging.info("codec is {}", args.codec)
    logging.info("source directory is {}", src_dir.absolute())
    logging.info("destination directory is {}", dest_dir.absolute())
    logging.info("number of threads is {}", args.threads)

    journal = VoidJournal() if args.no_inc else Journal(dest_dir)
    audio_files = walk_and_clone(journal, src_dir, dest_dir, encoder)

    s = Scheduler(audio_files, journal, encoder=encoder, props=get_properties(args, props), threads=args.threads)
    start = time.time()
    s.run()
    end = time.time()
    logging.info("time elapsed {}", format_time(end - start))


if __name__ == '__main__':
    main()
