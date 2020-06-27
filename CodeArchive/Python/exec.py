# Python 3 file

import subprocess
import time
import sys

cwd = sys.argv[1]
script = sys.argv[2]

start = time.time()
exitcode = subprocess.call(
    ['python', script], cwd=cwd, stderr=subprocess.STDOUT)


end = time.time()

seconds = end - start

print()
print(
    'Process return {0} ({1})   execution time: {2:.03f} s'.format(exitcode, hex(exitcode), seconds))

if sys.platform == 'win32':
    subprocess.call("pause", shell=True)
else:
    input("Press Enter to continue...")
