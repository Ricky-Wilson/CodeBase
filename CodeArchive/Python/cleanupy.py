"""
pyflakes3
pycodestyle
pylint
isort
black
python3-pasteurize
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys
from subprocess import getoutput

from future import standard_library

standard_library.install_aliases()


def flakes(this):
    return getoutput(f"pyflakes3 {this}")


def pycodestyle(this):
    return getoutput(f"pycodestyle {this}")


def pylint(this):
    return getoutput(f"pylint {this}")


def isort(this):
    return getoutput(f"python3 -m isort -y -sl -up {this}")


def black(this):
    return getoutput(f"black --target-version py36 {this}")


def pasteurize(this):
    return getoutput(f"python3-pasteurize --w -v {this}")


all = [flakes, pycodestyle, pylint, isort, black, pasteurize]

for this in all:
    print(this(sys.argv[1]))
