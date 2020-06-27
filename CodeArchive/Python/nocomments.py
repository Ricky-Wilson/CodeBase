#!/bin/python3

"""
Remove comments from a config file.
"""
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from future import standard_library

standard_library.install_aliases()
from builtins import *
import sys


with open(sys.argv[1]) as data:
    for line in data:
        line = line.strip()
        if line.startswith("#"):
            pass
        else:
            print(line)
