#!/usr/bin/env python3


import cmd
import functools
import html
import http.server as http
import io
import logging
import mimetypes
import os
import posixpath
import socket
import socketserver
import sys
import threading
import time
import urllib
from datetime import datetime
from http import HTTPStatus

import lxml
import requests
from lxml.builder import E

import guesstype
import keyinput
from listing import directory


BLACKHOLE = open(os.devnull, "wb")
SERVER_ROOT = os.getcwd()
DOCUMENT_ROOT = posixpath.join(SERVER_ROOT, "www")
STATIC_FILES = posixpath.join(DOCUMENT_ROOT, "Static")
LOG_DIR = "Logs"
LOGFILE = posixpath.join(LOG_DIR, "server.log")
ENCODING = sys.getfilesystemencoding()
ALL = ""
START_TIME = datetime.now()


def uptime():
    print(datetime.now() - START_TIME)


def current_time():
    return datetime.ctime(datetime.now())


if not posixpath.exists(STATIC_FILES):
    os.mkdir(STATIC_FILES)
if not posixpath.exists(LOG_DIR):
    os.mkdir(LOG_DIR)
if not posixpath.exists(DOCUMENT_ROOT):
    os.mkdir(DOCUMENT_ROOT)


class RequestHandler(http.SimpleHTTPRequestHandler):
    server_version = "DriftWoods CWS"
    data_sent = 0
    # os.chdir('www')

    def not_found(self):
        self.send_response(404)
        self.send_header("Content-type", f"text/html; charset={ENCODING}")
        self.end_headers()
        self.wfile.write(b'not found...')
        return

    def redirect(self, url):
        self.send_response(301)
        self.send_header("Location", url)
        self.end_headers()

    def log_message(self, fmstr, *args):
        sys.stdout.flush()
        sys.stdout.write("\r\n")
        if isinstance(args[0], HTTPStatus):
            code, msg = args
            print(f"{self.command} {self.path} {code.value} {code.name}")
        elif isinstance(args[0], str):
            reqline, code, _ = args
            code = int(code)
            msg = HTTPStatus(code).name
            print(f"{self.command} {self.path} {code} {msg}")

    # @functools.lru_cache()
    def do_GET(self):
        self.path = self.path.lstrip('/').rstrip('/')
        path_chars = list(self.path)
        path_chars.insert(0, '/')
        self.path = ''.join(path_chars)
        if self.path == '/':
            self.path = '.'
        if posixpath.isdir(self.path):
            data = directory(self.path)
            self.send_response(200)
            self.send_header('content-type', 'text/html')
            self.end_headers()
            self.copyfile(data, self.wfile)
            data.close()
            return
        if posixpath.isfile(self.path):
            data = self.get_head()
            prinn(data)

        data = self.send_head()
        if data:
            try:
                self.copyfile(data, self.wfile)
            except Exception as error:
                print(error)
            finally:
                data.close()

    def do_HEAD(self):
        """Serve a HEAD request."""
        f = self.send_head()
        if f:
            f.close()

    def guess_type(self, path):
        return guesstype.guess_type(path)


class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True
    requests_handled = 0

    def verify_request(self, request, client_address):
        self.requests_handled += 1
        return True

    def main_loop(self):
        host, port = self.server_address
        print(f"Starting Server http://{host}:{port}/")
        while 1:
            try:
                self.handle_request()
            except KeyboardInterrupt:
                self.socket.close()
                sys.exit(0)


class CommandLine(cmd.Cmd):
    prompt = "DRIFTWOODS WEBSERVER: "

    def __init__(self, args, completekey="tab", stdin=None, stdout=None):
        """Instantiate a line-oriented interpreter framework.
        The optional argument 'completekey' is the readline name of a
        completion key; it defaults to the Tab key. If completekey is
        not None and the readline module is available, command completion
        is done automatically. The optional arguments stdin and stdout
        specify alternate input and output file objects; if not specified,
        sys.stdin and sys.stdout are used.

        """
        self.args = args
        self.server_address = "127.0.0.1", 8000
        self.url = f"http://{self.server_address[0]}:{self.server_address[1]}/"
        if stdin is not None:
            self.stdin = stdin
        else:
            self.stdin = sys.stdin
        if stdout is not None:
            self.stdout = stdout
        else:
            self.stdout = sys.stdout
        self.cmdqueue = []
        self.completekey = completekey

    def do_exit(self, *_):
        try:
            self.do_stop()
        except AttributeError:
            pass
        finally:
            sys.exit(0)

    def do_server_address(self, *args):
        print(self.url)

    def do_stop(self, args):
        try:
            self.server.socket.shutdown(socket.SHUT_RDWR)
            self.server_thread.join(timeout=1)
        except OSError:
            pass

    def do_start(self, *args):

        if len(args) == 2:
            self.server_address = args[0], int(args[1])
        try:
            self.server = Server(self.server_address, RequestHandler)
            self.server_thread = threading.Thread(target=self.server.main_loop)
            self.server_thread.setDaemon(1)
            self.server_thread.start()
        except OSError:
            pass

    def do_uptime(self, *args):
        return uptime()

    def do_socket_timeout(self, args):
        try:
            socket.setdefaulttimeout(float(args))
        except ValueError:
            print("Invalid timeout")

    def do_requests_handled(self, *args):
        try:
            print(f"{self.server.requests_handled} Requests Served.")
        except AttributeError:
            print("You must start the server before it can hanle any requests...")

    def do_get(self, path='/'):
        """
         Request a file from the server.
        """
        url = f"{self.url}{path}"
        print(requests.get(url).text)

    def do_head(self, path="/"):
        """
        Send a
        HTTP HEAD request to the server
        and print out the headers.
        """
        url = f"{self.url}{path}"
        print(requests.head(url).headers)

    def emptyline(self):
        os.system("clear")

    def default(*args):
        os.system(args[1])


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bind",
        "-b",
        default="",
        metavar="ADDRESS",
        help="Specify alternate bind address " "[default: all interfaces]",
    )

    parser.add_argument(
        "--directory",
        "-d",
        default=DOCUMENT_ROOT,
        help="Specify alternative DOCUMENT_ROOT",
    )

    quiet_help = (
        "Disable stdout & stderr by redirecting their"
        'output to a black hole know as "/dev/null"'
    )

    parser.add_argument(
        "--quiet", "-q", action="store_true", default=False, help=quiet_help
    )

    parser.add_argument(
        "port",
        action="store",
        default=8000,
        type=int,
        nargs="?",
        help="Specify alternate port [default: 8000]",
    )

    args = parser.parse_args()
    DOCUMENT_ROOT = args.directory
    if os.getcwd() is not DOCUMENT_ROOT:
        os.chdir(DOCUMENT_ROOT)
    if args.quiet:
        sys.stdout = BLACKHOLE
        sys.stderr = BLACKHOLE

shell = CommandLine(args)
shell.do_start()
shell.do_get()
shell.cmdloop()
