#!/usr/bin/env python3

from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library

standard_library.install_aliases()
from builtins import *
import subprocess
import os
import sys
import tempfile
import glob
import argparse

# A black hole
NULL_DEVICE = open(os.devnull, "wb+")
PROCESSES = []
TEMP_FILES = []


def background_job(cmd, stdout=None, stderr=sys.stderr):
    proc = subprocess.Popen(cmd.split(), stdout=stdout, stderr=stderr)
    PROCESSES.append(proc)
    return proc


def command(cmd, **kw):
    if kw.get("background", 0):
        return background_job(cmd)
    return subprocess.getoutput(cmd)


def adb(args, **kw):
    """ Run an adb command.
    Example 1: adb('devices -l')
    Example 2: adb('devices', '-l')
    """
    return command(f"adb {args}", **kw)


def install(*apks, **kw):
    if len(apks) is 1 and os.path.isdir(apks[0]):
        pth = apks[0].rstrip("/") + "/"
        apks = glob.glob(pth + "/*.apk")
    return [adb(f"install {apk}", **kw) for apk in apks].pop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path",
        action="store",
        default=os.getcwd(),
        type=str,
        nargs="?",
        help="Specify the path to the apks",
    )

    args = parser.parse_args()
    install(args.path)
