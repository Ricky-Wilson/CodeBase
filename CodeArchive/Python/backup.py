#-*-coding:utf8;-*-
#qpy:3
#qpy:console

import tarfile
import os

def make_tgz(output_filename, source_dir):
    with tarfile.open(output_filename, "w:gz") as tar: 
        tar.add(source_dir, arcname=os.path.basename(source_dir))

make_tgz('qpython.tgz', '/sdcard/qpython')