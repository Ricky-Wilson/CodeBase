#!/usr/bin/env python3

"""
Manage downloaded contentent.
"""


import glob
import posixpath
import shutil
import tarfile
import os

DOWNLOAD_DIR = "/home/anonymous/Downloads"
ARCHIVE_DIR = "/home/anonymous/Web-Archive"
WEBPAGE_DIR = posixpath.join(ARCHIVE_DIR, "Web-Pages")
TARBALL = posixpath.join(ARCHIVE_DIR, "archive.tar")

if not posixpath.exists(ARCHIVE_DIR):
    os.mkdir(ARCHIVE_DIR)

if not posixpath.exists(WEBPAGE_DIR):
    os.mkdir(WEBPAGE_DIR)


def webpages_in_downloads():
    files = glob.glob(posixpath.join(DOWNLOAD_DIR, "*.html"))
    dirs = glob.glob(posixpath.join(DOWNLOAD_DIR, "*_files"))
    return files + dirs


def webpages_in_archive():
    return (posixpath.abspath(this) for this in os.listdir(WEBPAGE_DIR))


def add_file(fp):
    tarball = tarfile.TarFile(TARBALL, "a")
    tarball.add(fp, arcname="Web-Docs")
    tarball.close()


def update_archive():
    webpages = webpages_in_downloads()
    for fp in webpages:
        shutil.move(fp, WEBPAGE_DIR)
    add_file(WEBPAGE_DIR)


update_archive()
