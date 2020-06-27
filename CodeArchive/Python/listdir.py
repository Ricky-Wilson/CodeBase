import io
import os
import functools
from lxml import etree as ET
from lxml.builder import E


@functools.lru_cache(maxsize=256)
def ls(directory):
    return os.listdir(directory)


def directory(path):
    file_list = ls(path)
    # path = translate_path(path)
    dom = E.html(E.head(E.title("Test")), E.body(E.ul()))
    html_list = dom.xpath("//ul")[0]
    for name in file_list:
        # linkname = urllib.parse.quote(path, errors="surrogatepass")
        link = name
        html_list.append(E.li(E.a(link, href=link)))
    data = ET.tostring(dom, pretty_print=1)
    fileobj = io.BytesIO()
    fileobj.write(data)
    fileobj.seek(0)
    return fileobj
