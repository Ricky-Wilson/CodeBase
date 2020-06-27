from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import


#!/bin/python3

from future import standard_library

standard_library.install_aliases()
from builtins import *
import sys


def get_results(fpath):
    with open(fpath) as fp:
        for line in fp:
            print(len(line))


def main():
    get_results(sys.argv[1])


main()
