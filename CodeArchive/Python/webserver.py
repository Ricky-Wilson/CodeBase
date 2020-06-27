from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import html
import http.server as http
import os
import socketserver
import sys
import urllib.error
import urllib.parse
import urllib.request
import posixpath
import mimetypes
import lxml
from lxml.builder import E

SERVER_ROOT = '/var/www/html'
os.chdir(SERVER_ROOT)


def guess_ftype(this):
    return mimetypes.guess_type(this)[0]


def translate_path(path):
    """Translate a /-separated PATH to the local filename syntax.
    Components that mean special things to the local file system
    (e.g. drive or directory names) are ignored.  (XXX They should
    probably be diagnosed.)
    """
    # abandon query parameters
    path = path.split("?", 1)[0]
    path = path.split("#", 1)[0]
    # Don't forget explicit trailing slash when normalizing. Issue17324
    trailing_slash = path.rstrip().endswith("/")
    path = posixpath.normpath(urllib.parse.unquote(path))
    words = path.split("/")
    words = [_f for _f in words if _f]
    path = os.getcwd()
    for word in words:
        if os.path.dirname(word) or word in (os.curdir, os.pardir):
            # Ignore components that are not a simple file/directory name
            continue
        path = os.path.join(path, word)
        if trailing_slash:
            path += "/"
    return path


def directory(path):
    if not path == '/':
        path = SERVER_ROOT
    print(path)
    file_list = os.listdir(path)
    #path = translate_path(path)
    dom = E.html(E.head(E.title("Test")), E.body(E.ul()))
    html_list = dom.xpath("//ul")[0]
    for name in file_list:
        #linkname = urllib.parse.quote(path, errors="surrogatepass")
        link = path
        html_list.append(E.li(E.a(link, href=link)))
    return lxml.etree.tostring(dom, pretty_print=1)


def fixpath(path):
    pardir = posixpath.pardir(path)
    basename = posixpath.basename(path)
    absolute_path = posixpath.abspath(path)
    return posixpath.join(pardir, basename)


class RequestHandler(http.SimpleHTTPRequestHandler):

    @property
    def is_dir(self):
        return posixpath.isdir(self.path)

    @property
    def is_file(self):
        return posixpath.isfile(self.path)

    @property
    def is_root(self):
        return self.path == '/'

    def send_file(self):

        if self.is_file:
            self.send_response(200)
            self.send_header("content-type", guess_ftype(self.path))
            self.end_headers()
            with open(self.path, 'r') as fp:
                self.wfile.write(fp.read().encode('latin-1'))
            return
        if self.is_dir:
            """
            parts = urllib.parse.urlsplit(self.path)
            if not parts.path.endswith("/"):
                # redirect browser - doing basically what apache does
                self.send_response(301)
                new_parts = (parts[0], parts[1], parts[
                             2] + "/", parts[3], parts[4])
                new_url = urllib.parse.urlunsplit(new_parts)
                print(new_url)
                self.send_header("Location", new_url)
                self.end_headers()
            """
            self.send_response(200)
            self.send_header('content-type', "text/html")
            self.end_headers()
            self.wfile.write(directory(self.path))
            return

    def do_GET(self):
        print(self.path)
        self.send_file()


class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    server_version = "Offline Web/"
    allow_reuse_address = 1

    def verify_request(self, request, client_address):
        return True


def main():
    # os.chdir('/home/anonymous/Web-Archive')
    server_address = "127.0.0.1", 8000
    service = Server(server_address, RequestHandler)
    service.server_version = "test"
    service.allow_reuse_address = True
    service.serve_forever()


if __name__ == "__main__":
    main()
