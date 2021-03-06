from collections import deque
import argparse
import os
import time
import json

from . import fsutil, logging, codecs
from .fsutil import Path
from .gst import Scheduler
from .journal import Journal, VoidJournal


def compute_paths(args):
    src_dir = Path(args.src)
    if args.dest:
        dest_dir = Path(args.dest)
        if args.keep:
            dest_dir = dest_dir / src_dir.name
    else:
        dest_dir = Path(args.src).with_suffix('.' + args.codec)
    return src_dir, dest_dir


def ask_folders(journal, src_dir, dest_dir, encoder):
    audio_files = []
    other_files = []

    resume_path = dest_dir / ".pyaconv.i"

    decisions = dict()
    # Load the previous decisions.
    if resume_path.exists():
        with resume_path.open('r') as f:
            decisions = json.load(f)

    # Re-load the paths that were wanted.
    for path in decisions:
        if decisions[path]:
            audio, other = fsutil.walk(src_dir / path, dest_dir, encoder.extension(), src_dir)
            audio_files.extend(audio)
            other_files.extend(other)

    # Compute the list of paths not yet visited.
    to_visit = [path for path in src_dir.iterdir()
                if path.is_dir() and str(path.relative_to(src_dir)) not in decisions]

    try:
        for path in sorted(to_visit):
            answer = ""
            while answer.lower() not in ["y", "n"]:
                try:
                    answer = input("Include %s? [y/n]: " % path.name)
                except EOFError:
                    print('')  # skip line on Ctrl-D
                    raise StopIteration

            yes = answer.lower() == "y"
            decisions[str(path.relative_to(src_dir))] = yes

            if answer.lower() == "y":
                audio, other = fsutil.walk(path, dest_dir, encoder.extension(), src_dir)
                audio_files.extend(audio)
                other_files.extend(other)
    except StopIteration:
        pass
    finally:
        with resume_path.open('w') as f:
            json.dump(decisions, f)

    other_files = deque(journal.remove_journaled(other_files))
    audio_files = deque(journal.remove_journaled(audio_files))

    fsutil.build_tree(other_files)
    fsutil.build_tree(audio_files)
    fsutil.hardlink_tree(other_files, journal)

    return audio_files


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
    p.add_argument("-i, --interactive", dest="interactive", default=False,
                   action="store_true", help="Use interactive mode")
    p.add_argument("--no-inc", default=False, action="store_true",
                   help="disable incremental support")
    p.add_argument('-k, --keep', action='store_true', dest="keep", default=False, help="keep source name folder")
    args, _ = p.parse_known_args()

    encoder = codecs.registry[args.codec]
    props_def = encoder.properties()

    for prop in props_def:
        prop.add_argument(p)

    args = p.parse_args()

    if not args.src:
        p.print_help()
        exit()

    props = get_properties(args, props_def)

    src_dir, dest_dir = compute_paths(args)
    logging.info("codec is {}", args.codec)
    logging.info("source directory is {}", src_dir.absolute())
    logging.info("destination directory is {}", dest_dir.absolute())
    logging.info("number of threads is {}", args.threads)

    logging.info("options are:")
    logging.info("----")
    for name, val in props.items():
        logging.info("{}: {}", name, val)
    logging.info("----")

    journal = VoidJournal(dest_dir) if args.no_inc else Journal(dest_dir, props)

    if args.interactive:
        audio_files = ask_folders(journal, src_dir, dest_dir, encoder)
    else:
        audio_files = walk_and_clone(journal, src_dir, dest_dir, encoder)

    s = Scheduler(audio_files, journal, encoder=encoder,
                  props=props, threads=args.threads)
    start = time.time()
    s.run()
    end = time.time()
    logging.info("time elapsed {}", format_time(end - start))


if __name__ == '__main__':
    main()
