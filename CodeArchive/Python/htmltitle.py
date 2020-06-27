
'''
Extract the text from a html title.
'''

import fnmatch
import os
from lxml import html, etree
import re


def find_files(base=os.curdir, pattern=None):
    for root, _, files in os.walk(base):
        for fpath in (os.path.join(root, name) for name in files):
            if pattern and fnmatch.fnmatch(fpath, pattern):
                yield fpath
            if not pattern:
                yield fpath


def all_html():
    for src in find_files(pattern='*.html'):
        yield html.parse(src)


def get_title(fpath):
    with open(fpath, 'r') as fobj:
        page = etree.tostring(html.fromstring(fobj.read()))
    matches = re.findall('<title>(.*?)</title>', page)
    if matches:
        return matches[0]

titles = []
for fpath in find_files(pattern="*.html"):
    title = get_title(fpath)
    if title and 'index of' not in title.lower():
        if title not in titles:
            titles.append(title)
            print(title)
