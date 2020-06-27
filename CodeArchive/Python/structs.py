"""
Common structs for the package.
"""
from __future__ import division
import ctypes


class __pcap_header__(ctypes.Structure):
    """
    C-struct representation of a savefile header. See __validate_header__
    for validation.
    """
    _fields_ = [('magic', ctypes.c_uint),          # file magic number
                ('major', ctypes.c_ushort),        # major version number
                ('minor', ctypes.c_ushort),        # minor version number
                ('tz_off', ctypes.c_uint),         # timezone offset
                ('ts_acc', ctypes.c_uint),         # timestamp accuracy
                ('snaplen', ctypes.c_uint),        # snapshot length
                ('ll_type', ctypes.c_uint),        # link layer header type
                ('byteorder', ctypes.c_char_p),    # byte order specifier
                ('ns_resolution', ctypes.c_bool)]  # nanosecond resolution


class pcap_packet(ctypes.Structure):
    """
    ctypes Structure representation of a packet. The header field is a pointer
    to the header of the savefile the packet came from to provide context. It
    can be accessed with header[0]. By default, the raw packet is stored in
    a string of hexadecimal-encoded bytes as the packet field. The raw()
    method will return the raw binary packet.
    """
    _fields_ = [('header', ctypes.POINTER(__pcap_header__)),
                ('timestamp', ctypes.c_uint),
                ('timestamp_us', ctypes.c_uint),
                ('capture_len', ctypes.c_uint),
                ('packet_len', ctypes.c_uint)]

    packet = None

    def __init__(self, header, timestamp, timestamp_us, capture_len,
                 packet_len, packet):
        super(pcap_packet, self).__init__()
        self.header = header
        self.timestamp = timestamp
        self.timestamp_us = timestamp_us
        self.capture_len = capture_len
        self.packet_len = packet_len
        self.packet = packet

    def raw(self):
        """
        Return the raw binary data from the packet.
        """
        return self.packet

    def __repr__(self):
        if isinstance(self.packet, str):
            try:
                return self.raw()
            except TypeError:
                return str(self.packet)
        else:
            return str(self.packet)

    @property
    def timestamp_ms(self):
        return self.timestamp_us / 1000
