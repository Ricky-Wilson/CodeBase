from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from future import standard_library

standard_library.install_aliases()
from builtins import *
import glob
import subprocess
import time
import os


NULL = open("/dev/null", "wb+")
PDF_FILES = glob.glob("/home/anonymous/Scripts/webserver/www/Books/*.pdf")


def pdftohtml(*args):
    cmd = ["pdftohtml"]
    cmd.extend(list(args))
    return subprocess.Popen(cmd, stdout=NULL)


def main():
    while PDF_FILES:
        if len(subprocess._active) < 10:
            pdf = PDF_FILES.pop()
            print("Converting {}".format(pdf))
            try:
                pdftohtml("-s", "-p", "-c", "-dataurls", pdf)
            except:
                pass
        else:
            subprocess._cleanup()

    print("Finishing up conversion")
    while subprocess._active:
        pass


main()
