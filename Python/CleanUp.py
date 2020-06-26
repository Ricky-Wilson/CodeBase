#!/usr/bin/python3

'''
Remove unwanted cluter from the
Python Codebase.
'''

import glob
import os
import shutil


def remove_cache(basedir='.'):
    cache = os.path.join(basedir, '__pycache__')
    if os.path.exists(cache):
        shutil.rmtree(cache)


def remove_compiled(basedir='.'):
    for name in os.listdir(basedir):
        if name.endswith('.pyc'):
            os.remove(os.path.join(basedir, name))


def fix_permissions(basedir='.'):
    path = os.path.join(basedir, '*.py')
    for name in glob.glob(path):
        os.chmod(name, 777)


def clean(basedir='.'):
    remove_cache(basedir)
    remove_compiled(basedir)
    fix_permissions(basedir)

if __name__ == '__main__':
    clean()
