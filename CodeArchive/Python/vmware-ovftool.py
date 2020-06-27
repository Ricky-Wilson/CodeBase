"""
Copyright 2008-2019 VMware, Inc.  All rights reserved. -- VMware Confidential

VMware OVFTool component installer.
"""

DEST = LIBDIR/'vmware-ovftool'
CONF = LIBDIR/'vmware/setup/vmware-config'

class OVFTool(Installer):
   """
   This class contains the installer logic for the OVFTool component.
   """
   def InitializeInstall(self, old, new, upgrade):
       self.AddTarget('File', '*', DEST)
       self.AddTarget('Link', DEST/'ovftool', BINDIR/'ovftool')

       self.SetPermission(DEST/'ovftool', BINARY)
       self.SetPermission(DEST/'ovftool.bin', BINARY)

   def PostInstall(self, old, new, upgrade):
      if self.GetAnswer('ovftool.eula.deferred') == 'yes':
         self.RunCommand(CONF, '-s', 'acceptOVFEULA', 'none')
         self.DelConfig('ovftool.eula.deferred')
      else:
         self.RunCommand(CONF, '-s', 'acceptOVFEULA', 'yes')
