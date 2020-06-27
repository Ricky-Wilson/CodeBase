#!/bin/python


from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library

standard_library.install_aliases()
from builtins import *
import os
import sys

files = sys.argv
files.pop(0)
for f in files:
    ext = os.path.splitext(f)[1]
    if ext:
        print(ext)
