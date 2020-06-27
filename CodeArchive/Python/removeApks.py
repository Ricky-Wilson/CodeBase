
'''
delete APK files from 
the download folder.
'''

import os
import glob

def main():
    os.chdir('/sdcard/Download')
    for apk in glob.glob('*.apk'):
        os.remove(apk)

    
main()    


