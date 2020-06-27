#!/bin/python3

from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library

standard_library.install_aliases()
from builtins import *
import os

os.chdir("/var/www/html/Downloads")


def all_files(start="."):
    for root, _, files in os.walk(start):
        for name in files:
            yield os.path.join(root, name)


def mobile_html():
    for file_path in all_files():
        if file_path.endswith(".mhtml"):
            print(file_path)
