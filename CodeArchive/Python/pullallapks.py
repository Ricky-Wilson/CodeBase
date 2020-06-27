from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from future import standard_library

standard_library.install_aliases()
from builtins import *
from apkinstaller import adb


def packages(*args):
    if "third_party" in args:
        args = "-3"
    elif "system" in args:
        args = "-s"
    elif "enabled" in args:
        args = "-e"
    elif "disabled" in args:
        args = "-d"
    else:
        args = None

    return (
        adb(f'shell cmd package list packages {args or ""}')
        .replace("package:", "")
        .split("\n")
    )


def apk_path(pkg_name):
    return adb("shell pm path {pkg_name}")


def get_apk_paths(*args):
    return [apk_path(pkg) for pkg in packages(*args)]
