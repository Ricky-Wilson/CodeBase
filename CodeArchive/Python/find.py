#!/bin/python3

import os
import fnmatch
import sys
from mimetypes import guess_type

CWD = '.'


def walk(*args, **kw):
    for root, _, files in os.walk(*args, **kw):
        for name in files:
            yield os.path.join(root, name)


def find(pattern, directory=CWD):
    for root, _, files in os.walk(directory):
        for name in files:
            if fnmatch.fnmatch(name, pattern):
                yield os.path.join(name, root)


if __name__ == '__main__':
    try:
        pattern = sys.argv[1]
    except IndexError:
        sys.exit(1)
    if len(sys.argv) == 3:
        directory = sys.argv[1]
    else:
        directory = CWD
    for match in find(pattern, directory=directory):
        print(match)
