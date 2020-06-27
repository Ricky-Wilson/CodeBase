
import os
import fnmatch

def generate_directory_listing(path, name_filter=None):
    if name_filter:
        files = fnmatch.filter(os.listdir(path), name_filter)
    else:
        files = os.listdir(path)
    for name in files:
        fullname = os.path.join(path, name)
        displayname = linkname = name
        # Append / for directories or @ for symbolic links
        if os.path.isdir(fullname):
            displayname = name + "/"
            linkname = name + "/"
        if os.path.islink(fullname):
            displayname = name + "@"
            # Note: a link to a directory displays with @ and links with /
        yield linkname, displayname


