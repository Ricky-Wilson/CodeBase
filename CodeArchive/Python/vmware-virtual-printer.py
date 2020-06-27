#
# Copyright 2018 VMware, Inc.  All rights reserved. -- VMware Confidential
#

"""
Virtual Printer Component installer.
"""

DEST = LIBDIR/'vmware/isoimages'

class VirtualPrinterISO(Installer):
   def InitializeInstall(self, old, new, upgrade):
      self.AddTarget('File', 'VirtualPrinter-Windows.iso', DEST/'VirtualPrinter-Windows.iso')
      self.AddTarget('File', 'VirtualPrinter-Linux.iso', DEST/'VirtualPrinter-Linux.iso')
