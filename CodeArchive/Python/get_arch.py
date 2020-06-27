#!/bin/python3

import os


with open('archive.lst') as f:
    for file_path in f:
        archive  = file_path.strip()
        os.system('adb pull {} archives'.format(archive))
