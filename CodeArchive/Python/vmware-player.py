"""
Copyright 2008-2019 VMware, Inc.  All rights reserved. -- VMware Confidential

VMware Player component installer.
"""

DEST = LIBDIR/'vmware'
CONF = DEST/'setup/vmware-config'
LICENSETOOL=BINDIR/'vmware-license-enter.sh'

PRODUCT = 'VMware Player'
PRODUCT_FUSION = 'VMware Fusion for Mac OS'
LICENSEVERSION = '15.0'
LICENSEVERSION_FUSION = '11.0'

class Player(Installer):
   """
   This class is a shell used to wrap the product around the Player
   components.  All it needs are to set up the images for the GUI
   installer.
   """

   def InitializeQuestions(self, old, new, upgrade):

      self.AddQuestion('TextEntry',
                       key='serialNumber',
                       text='',
                       header='Enter license key.',
                       footer='(optional) You can enter this information later.',
                       default='',
                       required=True,
                       level='REGULAR',
                       deferrable=True)

   def PreTransactionInstall(self, old, new, upgrade):
      pass

   def InitializeInstall(self, old, new, upgrade):
      self.AddTarget('File', 'doc/*', DOCDIR/'vmware-player')
      self.AddTarget('File', 'lib/share/EULA.txt', DEST/'share/EULA.txt')
      self.AddTarget('File', 'lib/share/vmware-player.eval', DEST/'share/vmware-player.eval')

   def PostInstall(self, old, new, upgrade):
      # serial entered by user:
      serialNumber = self.GetAnswer('serialNumber')
      if serialNumber:
         ret = self.RunCommand(LICENSETOOL, serialNumber, PRODUCT, LICENSEVERSION)
         if ret.retCode != 0:
            self.RunCommand(LICENSETOOL, serialNumber, PRODUCT_FUSION, LICENSEVERSION_FUSION)

      if self.GetAnswer('eula.deferred', component='vmware-player') == 'yes':
         self.RunCommand(CONF, '-s', 'acceptEULA', 'none')
         self.DelConfig('eula.deferred')
      else:
         self.RunCommand(CONF, '-s', 'acceptEULA', 'yes')
