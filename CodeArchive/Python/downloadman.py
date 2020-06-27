from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import


from future import standard_library

standard_library.install_aliases()
from builtins import *
from builtins import object
import posixpath
from glob import glob
import os
import shutil


DOWNLOAD_PATH = "/home/anonymous/Downloads"


class Manager(object):
    def __init__(self, directory=DOWNLOAD_PATH):
        self.directory = directory
        self.page_dir = posixpath.join(directory, "Pages")
        if not posixpath.exists(self.page_dir):
            os.mkdir(self.page_dir)

    def glob(self, pattern):
        return glob(posixpath.join(self.directory, pattern))

    @property
    def partial(self):
        return self.glob("*.crdownload")

    def remove_partial(self):
        [os.remove(this) for this in self.partial]

    @property
    def pages(self):
        return self.glob("*.html") + self.glob("*_files*")

    def movePages(self):
        [shutil.move(this, self.page_dir) for this in self.pages]
