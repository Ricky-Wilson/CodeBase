#!/usr/bin/env python3


import os
import pathlib
import sys

import chardet
from whoosh.fields import ID, TEXT, Schema
from whoosh.index import create_in
from whoosh.writing import AsyncWriter


def read_text(fpath):
    with open(fpath, "rb") as file_obj:
        data = file_obj.read()
        encoding = chardet.detect(data)["encoding"] or "latin1"
        return data.decode(encoding, errors="ignore")


def createSearchableData(root):
    """
    Schema definition: title(name of file), path(as ID), content(indexed
    but not stored),textdata (stored text content)
    """
    if isinstance(root, str):
        root = pathlib.Path(root)

    schema = Schema(
        title=TEXT(stored=True),
        path=ID(stored=True),
        content=TEXT,
        textdata=TEXT(stored=True),
    )
    if not os.path.exists("indexdir"):
        os.mkdir("indexdir")

    # Creating a index writer to add document as per schema
    ix = create_in("indexdir", schema)
    with ix.writer(procs=4, multisegment=True) as writer:
        for path in root.rglob("*.html"):
            title = path.name
            print(f"Adding {title}")
            text = read_text(path)
            writer.add_document(
                title=title, path=str(path), content=text, textdata=text
            )
            print(f"Added {title} to index")


root = "/var/www/html/site/files/Webs"
createSearchableData(root)
