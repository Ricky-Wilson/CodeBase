"""
Copyright 2008 VMware, Inc.  All rights reserved. -- VMware Confidential

VMware Player Setup component installer.
"""

DEST = LIBDIR/'vmware/setup'
DEST.perm = BINARY


class PlayerExtras(Installer):
   def InitializeInstall(self, old, new, upgrade):
      self.AddTarget('File', '*', DEST)
