
'''
A interface to the find command.
'''

import subprocess

NEWLINE = '\n'


def find(*args, callback=False):
    results = subprocess.getoutput(f'find {" ".join(args)}').split(NEWLINE)
    if not callback:
        return results
    for result in results:
        yield function(result)


def test():
    results = find('~ -iname "*.py"', callback=print)

test()
