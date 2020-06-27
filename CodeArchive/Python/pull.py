#!/bin/python

import sys
import os


def pull(infile, outfile):
    os.system("adb pull {} {}".format(infile, outfile))


def push(infile, outfile):
    os.system("adb push {} {}".format(infile, outfile))


def shell(*args):
    os.system("adb shell {} 2>/dev/null".format(*args))


def pull_all(inputfile):
    with open(inputfile) as inputfile:
        for line in inputfile.readlines():
            pull(line)

shell("find -iname *.rc")