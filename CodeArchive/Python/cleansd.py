#-*-coding:utf8;-*-
#qpy:3
#qpy:console

import os
import fnmatch
import json
import mimetypes
import shutil

if os.path.exists('/sdcard'):
    os.chdir('/sdcard')
    SD = '/sdcard'
else:
    SD = os.curdir


class MediaDirectories(object):
    def __init__(self):
        self.music = 'Music/'
        self.books = 'Books/'
        self.apps = 'Apps/'
        self.movies = 'Movies/'
        self.make_directories()
        
    def __str__(self):
        return json.dumps(self.__dict__, indent=4)

    def __iter__(self):
       ''' Returns the Iterator object '''
       return iter(self.__dict__.values())

    def move(self, *args, **kw):
        try:
            shutil.move(*args, **kw)
            print("Moved {} To {}".format(*args))
        except shutil.Error:
            pass
    
    def add_file(self, pth):
        try:
            mime = mimetypes.guess_type(pth, strict=0)[0].split('/')[1]
        except AttributeError:
            return
        
        if mime == 'vnd.android.package-archive':
            self.move(pth, self.apps)
        if mime == 'mpeg':
            self.move(pth, self.music)
        if mime == 'pdf':
            self.move(pth, self.books)
        if mime == 'mp4':
            self.move(pth, self.movies)

    def make_directories(self):
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


media = MediaDirectories()

def sort_files():
    for pth in sd():
        media.add_file(pth)
        
sort_files()      
        
 

    