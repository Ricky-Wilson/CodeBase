
import os
import posixpath
import socket
import sys
import threading
import time
from concurrent import futures
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler

import listdir

BASE = 'static'
ENCODING = sys.getfilesystemencoding()
os.chdir(BASE)

THREAD_POOL = futures.ThreadPoolExecutor(max_workers=20)


class RequestHandler(SimpleHTTPRequestHandler):
    server_version = 'dwhttpd'

    def __init__(self, *args, directory=BASE, **kwargs):
        self.directory = directory
        super().__init__(*args, **kwargs)

    def list_directory(self, path):
        fileobj = listdir.directory(path)
        size = len(fileobj.getvalue())
        self.send_response(HTTPStatus.OK)
        self.send_header(f"Content-type", "text/html; charset={ENCODING}")
        self.send_header("Content-Length", size)
        self.end_headers()
        return fileobj

    def do_GET(self):
        data = self.send_head()
        if not data:
            self.close_connection = 1
            return
        try:
            #THREAD_POOL.submit(lambda: self.copyfile(data, self.wfile))
            self.copyfile(data, self.wfile)
        finally:
            data.close()

    def do_HEAD(self):
        """Serve a HEAD request."""
        self.send_response(200)
        self.send_header('Active-Threads', threading.active_count())
        self.end_headers()

    @listdir.functools.lru_cache(256)
    def log_message(self, *args):
        args = list(args)
        args.pop(0) and args.pop()
        print(' '.join(args))

    def log_error(self, *args):
        args = list(args)
        args.pop(0)
        status = args[0]
        name = status.name
        code = status.numerator
        # print(f'{code} {name} {self.path}')


class Server(HTTPServer):
    allow_reuse_address = True


def build_server(host, port):
    return Server((host, port), RequestHandler)


def main():
    with build_server('127.0.0.1', 8080) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            sys.stdout.write('\r\n')
            sys.exit(0)
        finally:
            THREAD_POOL.shutdown()
            httpd.server_close()


if __name__ == '__main__':
    main()
