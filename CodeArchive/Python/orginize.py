#-*-coding:utf8;-*-
#qpy:3
#qpy:console

import os
import fnmatch
import json
import mimetypes

if os.path.exists('/sdcard'):
    os.chdir('/sdcard')
    
SD = os.curdir


class MediaDirectories(object):
    def __init__(self):
        self.music = 'Music/'
        self.books = 'Books/'
        self.apps = 'Apps/'
        
    def __str__(self):
        return json.dumps(self.__dict__, indent=4)

    def __iter__(self):
       ''' Returns the Iterator object '''
       return iter(self.__dict__.values())
    
    def create_directories(self):
        for directory in self:
            if not os.path.exists(directory):
                print('Making {}'.format(directory))
                os.mkdir(directory)
    
    
        
        
def sd(pth=SD):
    for root, _, files in os.walk(pth):
        for pth in (os.path.join(root, fn) for fn in files):
            yield  pth


def find(pattern):
    for file_path in sd():
        if fnmatch.fnmatch(file_path, pattern):
             yield file_path


d = MediaDirectories()

d.create_directories()
def shell():                       
    while 1:            
        for name in find(input('Search ')):
            mime = mimetypes.guess_type(name, strict=0)
            print(name)
            print(mime)

shell()
    