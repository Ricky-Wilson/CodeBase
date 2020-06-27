from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import


from future import standard_library

standard_library.install_aliases()
from builtins import str
from builtins import range
from builtins import *
import ipaddress
import socket
import sys

DEFAULT_TIMEOUT = 0.30
DEFAULT_PORT = "all"


def service_name(port):
    try:
        service = socket.getservbyport(port)
    except OSError:
        service = None
    finally:
        return service


def connect(*host, timeout=DEFAULT_TIMEOUT):
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        sock.connect(host)
        sock.close()
        return True
    except KeyboardInterrupt:
        sys.exit(0)
    except:
        return False
    finally:
        sock.close()


def scan(network="127.0.0.1", ports=DEFAULT_PORT, timeout=DEFAULT_TIMEOUT):

    if isinstance(ports, tuple):
        ports = list(range(*ports))
    if isinstance(ports, int):
        ports = [ports]
    if ports == "all":
        ports = list(range(0, 65535))
    if isinstance(ports, str) and ports != "all":
        ports = [socket.getservbyname(ports)]
    for addr in ipaddress.ip_network(network):

        for port in ports:
            if connect(str(addr), port, timeout=timeout):

                msg = f"Port: {port}\nService: {service_name(port)}\n" f"Host: {addr}\n"

                print(msg)


scan(ports=(0, 1000))
