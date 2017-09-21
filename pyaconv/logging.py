import functools
import sys

DEBUG = 1
INFO = 2
WARNING = 3
ERROR = 4

_level_map = {
    DEBUG: "DEBUG",
    INFO: "INFO",
    WARNING: "WARNING",
    ERROR: "ERROR",
}


def log(level, fmt, *args, **kwargs):
    fd = sys.stdout if level <= INFO else sys.stderr
    print('{}: {}'.format(_level_map[level], fmt.format(*args, **kwargs)),
          file=fd)


debug = functools.partial(log, DEBUG)
info = functools.partial(log, INFO)
warning = functools.partial(log, WARNING)
error = functools.partial(log, ERROR)
