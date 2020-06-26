#!/usr/bin/python3

'''
Transfor a group of modules into a
single module by removing the .git directory
in each sub-module.
'''


import os
import shutil


def merge_modules(master='.'):
    '''
    Tansform a directory of modules
    into a single module.
    '''
    for this in os.listdir(master):
        fullpath = os.path.join(master, this)
        if os.path.isdir(fullpath):
            repo = os.path.join(fullpath, '.git')
            if os.path.exists(repo):
                shutil.rmtree(repo)


if __name__ == '__main__':
    merge_modules()



