#!/bin/python

"""Simple HTTP Server.

This module builds on BaseHTTPServer by implementing the standard GET
and HEAD requests in a fairly straightforward manner.

"""


__version__ = "0.1"

__all__ = ["SimpleHTTPRequestHandler"]

import os
import posixpath
import BaseHTTPServer
import cgi
import sys
import shutil
import mimetypes
from concurrent.futures import ThreadPoolExecutor


BOOK_DIR = 'Books/'


os.chdir(BOOK_DIR)


def translate_path(path):
    """Translate a /-separated PATH to the local filename syntax.
    Components that mean special things to the local file system
    (e.g. drive or directory names) are ignored.  (XXX They should
     probably be diagnosed.)
    """
    # abandon query parameters
    path = path.split('?', 1)[0]
    path = path.split('#', 1)[0]
    # Don't forget explicit trailing slash when normalizing. Issue17324
    trailing_slash = path.rstrip().endswith('/')
    path = posixpath.normpath(path)
    words = path.split('/')
    words = filter(None, words)
    path = os.getcwd()
    for word in words:
        if os.path.dirname(word) or word in (os.curdir, os.pardir):
            # Ignore components that are not a simple file/directory name
            continue
        path = os.path.join(path, word)
    if trailing_slash:
        path += '/'
    return path


def anchor(link, name):
    return '\n<li>\n<a href="{}">{}</a>\n</li>\n'.format(link, name)


def get_link(path, name):
    fullname = os.path.abspath(name)
    displayname = os.path.splitext(name)[0]
    displayname = os.path.splitext(displayname)[0]
    displayname = displayname.replace('-', ' ')
    displayname = displayname.replace('.', '')
    displayname = displayname.replace('_', ' ')
    displayname = displayname.replace('pdf', '')
    displayname = displayname.replace('(', '')
    displayname = displayname.replace(')', '')
    displayname = displayname.replace('ebook', '')
    parts = list(displayname)
    parts[0] = displayname[0].upper()
    displayname = ''.join(parts)
    fullname = os.path.join(path, name)
    # linkname = name
    # # Append / for directories or @ for symbolic links
    # if os.path.isdir(fullname):
    #     displayname = name + "/"
    #     linkname = name + "/"
    # if os.path.islink(fullname):
    #     displayname = name + "@"
    return anchor(translate_path(path), displayname)


class SimpleHTTPRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    """Simple HTTP request handler with GET and HEAD commands.

    This serves files from  BOOK_DIR.

    The GET and HEAD requests are identical except that the HEAD
    request omits the actual contents of the file.

    """

    def do_GET(self):
        """Serve a GET request."""
        file_object = self.send_head()
        if not file_object:
            return
        self.copyfile(file_object, self.wfile)

    def do_HEAD(self):
        """Serve a HEAD request."""
        file_object = self.send_head()
        if file_object:
            file_object.close()

    def send_file(self, fpath):
        try:
            file_object = open(fpath, 'rb')
        except:
            self.send_error(404, '{} Not Found...'.format(fpath))
            return
        self.send_response(200)
        self.send_header("Content-type", self.guess_type(fpath))
        file_stat = os.fstat(file_object.fileno())
        self.send_header("Content-Length", str(file_stat[6]))
        self.send_header(
            "Last-Modified", self.date_time_string(file_stat.st_mtime))
        self.end_headers()
        return file_object

    def send_head(self):
        """Common code for GET and HEAD commands.

        This sends the response code and MIME headers.

        Return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.

        """
        path = translate_path(self.path)
        # in_root = os.path.relpath(path) == '.'
        # if in_root and os.path.exists('index.html'):
        #    self.log_message('%s','foo')
        if os.path.isdir(path):
            return self.list_directory(path)
        else:
            return self.send_file(path)

    def copyfile(self, source, outputfile):
        """Copy all data between two file objects.

        The SOURCE argument is a file object open for reading
        (or anything with a read() method) and the DESTINATION
        argument is a file object open for writing (or
        anything with a write() method).

        The only reason for overriding this would be to change
        the block size or perhaps to replace newlines by CRLF
        -- note however that this the default server uses this
        to copy binary data as well.

        """

        shutil.copyfileobj(source, outputfile)

    def guess_type(self, path):
        """Guess the type of a file.

        Argument is a PATH (a filename).

        Return value is a string of the form type/subtype,
        usable for a MIME Content-type header.

        The default implementation looks the file's extension
        up in the table self.extensions_map, using application/octet-stream
        as a default; however it would be permissible (if
        slow) to look inside the data to make a better guess.

        """
        if not mimetypes.inited:
            mimetypes.init()  # try to read system mime.types
        extensions_map = mimetypes.types_map.copy()
        extensions_map.update(
            {'': 'application/octet-stream',  # Default
             '.py': 'text/plain',
             '.c': 'text/plain',
             '.h': 'text/plain',
             })

        return extensions_map.get(os.path.splitext(path)[1])


class RequestHandler(SimpleHTTPRequestHandler):

    server_name = 'DWS'

    def get_book_list(self, path):
        lst = [name for name in os.listdir(path) if name.endswith('pdf.html')]
        lst = lst.sort(key=lambda a: a.lower())
        return lst

    def list_directory(self, path):
        """Helper to produce a directory listing (absent index.html).

        Return value is either a file object, or None (indicating an
        error).  In either case, the headers are sent, making the
        interface the same as for send_head().

        """

        files = (
            name for name in os.listdir(path)
            if name.endswith('pdf.html'))

        outputfile = open('index.html', 'wb')
        outputfile.write('<!DOCTYPE html5>\n')
        outputfile.write('<html>\n')
        outputfile.write("<title>DriftWoods Book Server.</title>\n")
        outputfile.write('<head>\n')
        outputfile.write('<style>\n')
        with open('main.css') as css:
            outputfile.write("{}\n".format(css.read()))
        outputfile.write('</style>\n')
        outputfile.write('</head>\n')
        outputfile.write('<body>\n')
        outputfile.write('<h2>DriftWood\'s Book Server.</h2>\n')
        outputfile.write('<ul>\n')
        for name in files:
            outputfile.write(get_link(path, name))
        outputfile.write('</ul>\n')
        outputfile.write('<footer>')
        outputfile.write(
            '<h3>Powered By <u>{}</u></h3>'.format(self.server_name))
        outputfile.write('</footer>')
        outputfile.write('</body>\n')
        outputfile.write('</html>\n')
        length = outputfile.tell()
        outputfile.seek(0)
        self.send_response(200)
        encoding = sys.getfilesystemencoding()
        self.send_header("Content-type", "text/html; charset=%s" % encoding)
        self.send_header("Content-Length", str(length))
        self.end_headers()
        # self.log_message("Updated %s", "index.html")
        outputfile.close()
        return open('index.html')
        return outputfile


def test(HandlerClass=RequestHandler, ServerClass=BaseHTTPServer.HTTPServer):
    BaseHTTPServer.test(HandlerClass, ServerClass)


if __name__ == '__main__':
    test()
