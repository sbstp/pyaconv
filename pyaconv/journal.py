from .fsutil import Path
from . import logging


class BaseJournal:

    def add(self, path):
        raise NotImplementedError

    def __contains__(self, item):
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError

    def remove_journaled(self, pairs):
        raise NotImplementedError


class Journal(BaseJournal):

    """
    This is a log of what has been cloned. In memory, files are kept
    as absolute paths. In the log file, the paths are saved in relative
    form. Their root is the destination folder. This permits moving the
    destination folder around.
    """

    def __init__(self, dest):
        self._log = set()
        self._dest = dest.absolute()
        p = Path(dest / ".pyaconv")
        if p.exists():
            with p.open() as f:
                for item in f.readlines():
                    self._log.add((dest / item.rstrip()).absolute())
        p.parent.mkdir(parents=True, exist_ok=True)
        self._file = p.open('a')

    def __del__(self):
        self._file.close()

    def add(self, path):
        path = path.absolute()
        self._log.add(path)
        self._file.write(str(path.relative_to(self._dest)))
        self._file.write("\n")
        self._file.flush()

    def __contains__(self, item):
        return item in self._log

    def __len__(self):
        return len(self._log)

    def remove_journaled(self, pairs):
        for p in pairs:
            dest = p[1].absolute()
            if dest in self:
                logging.info("skipping {}", dest)
            else:
                yield p


class VoidJournal(BaseJournal):

    def add(self, path):
        pass

    def __contains__(self, item):
        return False

    def __len__(self):
        return 0

    def remove_journaled(self, pairs):
        return pairs
