import json

from .fsutil import Path
from . import logging


def compare_props(left, right):
    if len(left) != len(right):
        return False
    for key, val in left.items():
        if right[key] != val:
            return False
    return True


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

    def __init__(self, dest, props):
        self._log = set()
        self._dest = dest.absolute()
        self._props = props
        p = Path(dest / ".pyaconv")
        if p.exists():
            with p.open() as f:
                for line in f.readlines():
                    # Parse the line of json and remove the special $path property.
                    item_props = json.loads(line.rstrip())
                    path = (dest / Path(item_props.pop("$path"))).absolute()
                    # Only add log entries that have the same properties.
                    if compare_props(item_props, props):
                        self._log.add(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        # Override log with valid entries.
        self._file = p.open('w')
        for path in self._log:
            self._write_entry(path)

    def __del__(self):
        self._file.close()

    def add(self, path):
        self._log.add(path)
        self._write_entry(path)

    def _write_entry(self, path):
        props = self._props.copy()
        props["$path"] = str(path.absolute().relative_to(self._dest))
        self._file.write(json.dumps(props))
        self._file.write("\n")
        self._file.flush()

    def __contains__(self, path):
        """
        The only entries in the log should be the files that have the same properties
        and that were commited to the log.
        """
        return path in self._log

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
