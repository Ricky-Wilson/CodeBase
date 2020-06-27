#!/usr/bin/env python3


import functools
import mimetypes
import posixpath

if not mimetypes.inited:
    mimetypes.init()  # try to read system mime.types


EXTENTIONS_MAP = mimetypes.types_map.copy()
EXTENTIONS_MAP.update(
    {
        "": "application/octet-stream",  # Default
        ".py": "text/plain",
        ".c": "text/plain",
        ".h": "text/plain",
        ".log": "text/plain",
        ".log": "text/plain",
        ".mhtml": "text/html",
    }
)


@functools.lru_cache()
def guess_type(path):
    """Guess the type of a file.

    Argument is a PATH (a filename).

    Return value is a string of the form type/subtype,
    usable for a MIME Content-type header.

    The default implementation looks the file's extension
    up in the table EXTENTION_MAP, using application/octet-stream
    as a default; however it would be permissible (if
    slow) to look inside the data to make a better guess.
    """

    base, ext = posixpath.splitext(path)
    if ext in EXTENTIONS_MAP:
        return EXTENTIONS_MAP[ext]
    ext = ext.lower()
    if ext in EXTENTIONS_MAP:
        return EXTENTIONS_MAP[ext]
    else:
        return EXTENTIONS_MAP[""]
