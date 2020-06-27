from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library

standard_library.install_aliases()
from builtins import *
import socket

try:
    from urllib.parse import urlparse
except ImportError:
    from urllib.parse import urlparse

CONNECTION_TIMEOUT = 5
CHUNK_SIZE = 1024
HTTP_VERSION = 1.0
CRLF = "\r\n\r\n"

socket.setdefaulttimeout(CONNECTION_TIMEOUT)


def receive_all(sock, chunk_size=CHUNK_SIZE):
    """
    Gather all the data from a request.
    """
    chunks = []
    while True:
        chunk = sock.recv(int(chunk_size))
        if chunk:
            chunks.append(chunk.decode())
        else:
            break

    return "".join(chunks)


def get(url, **kw):
    kw.setdefault("timeout", CONNECTION_TIMEOUT)
    kw.setdefault("chunk_size", CHUNK_SIZE)
    kw.setdefault("http_version", HTTP_VERSION)
    kw.setdefault("headers_only", False)
    kw.setdefault("response_code_only", False)
    kw.setdefault("body_only", False)
    url = urlparse(url)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(kw.get("timeout"))
    sock.connect((url.netloc, url.port or 80))
    msg = "GET {0} HTTP/{1} {2}"
    sock.sendall(msg.format(url.path or "/", kw.get("http_version"), CRLF).encode())
    data = receive_all(sock, chunk_size=kw.get("chunk_size"))
    sock.shutdown(socket.SHUT_RDWR)
    sock.close()

    headers = data.split(CRLF, 1)[0]
    request_line = headers.split("\n")[0]
    response_code = request_line.split()[1]
    headers = headers.replace(request_line, "")
    body = data.replace(headers, "").replace(request_line, "")

    if kw["body_only"]:
        return body
    if kw["headers_only"]:
        return headers
    if kw["response_code_only"]:
        return response_code
    else:
        return data


print(get("http://127.0.0.1/"))
