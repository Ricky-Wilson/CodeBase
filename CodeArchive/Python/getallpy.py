#!/bin/python3


from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library

standard_library.install_aliases()
from builtins import *
import adb
import find
import os


with open("pylst") as f:
    for line in f:
        filepath = line.strip()
        base = os.path.basename(filepath)
        print("Adding {} to AllPython".format(base))
        os.system("cp {} {}".format(filepath, "AllPython"))
