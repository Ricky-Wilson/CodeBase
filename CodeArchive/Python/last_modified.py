
import os
import scandir

def lastmodified(fpath):
    paths = []
    for dirpath, dirs, files in scandir.walk(fpath):
        for name in files:
            fullpath = os.path.join(dirpath, name)
            if os.path.isfile(fullpath):
                paths.append(fullpath)
    for name in sorted(paths, key=os.path.getmtime):
        print name

lastmodified('/home/')
