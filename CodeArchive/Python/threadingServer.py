from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library

standard_library.install_aliases()
from builtins import *
import threading
import socketserver
import subprocess


class ThreadedEchoRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        # Echo the back to the client
        # data = self.request.recv(1024)
        # cur_thread = threading.currentThread()
        self.request.send(
            subprocess.getoutput("dmesg --follow --human --syslog ").encode()
        )
        return


class ThreadedEchoServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


if __name__ == "__main__":
    import socket
    import threading

    address = ("localhost", 1234)  # let the kernel give us a port
    server = ThreadedEchoServer(address, ThreadedEchoRequestHandler)
    t = threading.Thread(target=server.serve_forever)
    t.setDaemon(True)  # don't hang on exit
    t.start()
    print("Server loop running in thread:", t.getName())

    while 1:
        pass
