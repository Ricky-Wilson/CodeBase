#!/usr/bin/python3

import subprocess


def pydoc(module):
    print(subprocess.getoutput(f'pydoc3 -w {module}'))


pydoc('BuildDocs')