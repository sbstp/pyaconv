import mimetypes
import os
import pathlib
import errno
import shutil

_SuperPath = type(pathlib.Path())


class Path(_SuperPath):

    def absolute(self):
        return Path(os.path.abspath(str(self)))


def walk(src_dir, dest_dir, extension, base_dir=None):
    """
    Recursively walks the source directory and categorizes files as audio or
    other.

    Returns
    """
    base_dir = base_dir or src_dir
    if not src_dir.exists():
        raise ValueError("source does not exist")
    if not src_dir.is_dir():
        raise ValueError("source directory is not a directory")

    if dest_dir.exists() and not dest_dir.is_dir():
        raise ValueError("destination is not a directory")

    audio_files = list()
    other_files = list()

    def walker(dir):
        for f in dir.iterdir():

            if f.is_file():
                kind, _ = mimetypes.guess_type(f.absolute().as_uri())
                clone_path = dest_dir / f.relative_to(base_dir)
                if kind is not None and kind.startswith("audio/"):
                    clone_path = clone_path.with_suffix("." + extension)
                    audio_files.append((f, clone_path))
                else:
                    other_files.append((f, clone_path))
            if f.is_dir():
                walker(f)

    walker(src_dir)
    return audio_files, other_files


def build_tree(pairs):
    for _, clone_path in pairs:
        clone_path.parent.mkdir(parents=True, exist_ok=True)


def hardlink_tree(pairs, journal):
    for src, copy in pairs:
        if not copy.exists():
            try:
                os.link(str(src), str(copy))
            except OSError as e:
                if e.errno == errno.EXDEV:
                    shutil.copy(str(src), str(copy))
                else:
                    raise
            journal.add(copy.absolute())
