import os
import shutil

BASE_PATH = '/home/driftwood/Codebase/Libs/Web'

for this in os.listdir(BASE_PATH):
    fullpath = os.path.join(BASE_PATH, this)
    if os.path.isdir(fullpath):
        repo = os.path.join(fullpath, '.git')
        if os.path.exists(repo):
            shutil.rmtree(repo)

