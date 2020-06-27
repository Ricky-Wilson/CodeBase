"""
Copyright 2010-2019 VMware, Inc.  All rights reserved. -- VMware Confidential
"""

import os
import re
import sys
import time

from vmis.core.files import LIBDIR
from vmis.db import db
from vmis.util.path import path
from vmis.util.shell import run
from vmis.util.log import getLog

from vmis import vmisdebug
from vmis import VERSION

log = getLog('vmis.ui.uiAppControl')

class AppControlNotFoundError(Exception):
   """Could not locate the App Control application"""
   pass

class AppControlError(Exception):
   """ Error in the app control program """
   pass

class UIAppControl:
   """UI helper class for App Control access"""

   def __init__(self):
      # We need to save the original library directory for later use.
      # We will need to get to programs that were originally installed on the system
      # and if the user changes LIBDIR, we don't want the new one.  Explicitly
      # cast it to a string and create a new path object with that path.
      self.ORIGLIBDIR = path(str(LIBDIR))

      self.appControl = self.LocateAppControl()
      if self.appControl:
         log.info('Initialized UIAppControl.  Located at: %s' % self.appControl)
      else:
         log.info('Could not locate installer App Control.')
         raise AppControlNotFoundError('Could not locate installer App Control.')

   def LocateAppControl(self):
      """
      Attempt to locate an instance of vmware-app-control.  This function will search
      the original LIBDIR first.  If not found there, then it will fall back on the
      installer supplied app control.

      @returns: A path object to the located App Control or None if not found.
      """
      # Try self.ORIGLIBDIR first
      loc = path(self.ORIGLIBDIR/'vmware/bin/vmware-app-control')
      self.LIBDIR = self.ORIGLIBDIR/'vmware'
      if loc.exists():
          return loc

      return None

   def RunAppControl(self, stdin):
      """
      Execute App Control with the given stdin

      @stdin: The commands to pass to App Control
      @returns: stdout
      """
      ret = run(self.appControl, '--', '-l', self.LIBDIR, stdin=stdin)
      stdout = ret['stdout']
      if ret['retCode'] != 0:
         raise AppControlError('Return from vmware-app-control was non-zero: %d' % ret['retCode'])
      if not re.findall('initialize workstation: ok', stdout):
         raise AppControlError('Could not initialize App Control.')
      if not re.findall('refresh-lists: ok', stdout):
         raise AppControlError('Could not refresh App Control lists.')
      if re.findall('shutdown-error', stdout):
         raise AppControlError('Error shutting down virtual machines.')
      if re.findall('vix-error', stdout):
         raise AppControlError('VIX error while running App Control.')
      return stdout

   def Initialize(self):
      """
      Initialize App Control and retrieve the number of open VMs and
      open applications.  The values are stored locally into
      self.numVMs and self.numApps.
      """
      results = self.RunAppControl(b'initialize workstation\nrefresh-lists\nget-vm-count\nget-app-count\nexit\n')

      # Retrieve the number of open VMs
      numVMs = 0
      mt = re.findall('get-vm-count: count: (.*?)\n', results)
      if not mt:
         raise AppControlError('Could not retrieve number of open VMs.')
      try:
         numVMs = int(mt[0])
      except ValueError:
         raise AppControlError('Number of open VMs was non-integer: %s' % mt[0])
      self.numVMs = numVMs

      # Retrieve the number of open apps.
      numApps = 0
      mt = re.findall('get-app-count: count: (.*?)\n', results)
      if not mt:
         raise AppControlError('Could not retrieve number of open Apps.')
      try:
         numApps = int(mt[0])
      except ValueError:
         raise AppControlError('Number of open Apps was non-integer: %s' % mt[0])
      self.numApps = numApps

   def GetVMInfo(self, num):
      """
      Retrieve information on a VM

      @returns: The name of the VM
      """
      vminfo = self.RunAppControl(b'initialize workstation\nrefresh-lists\nget-vm-name %d\nexit\n' % num)
      if re.findall('bad-arg', vminfo):
         raise AppControlError('Cannot retrieve VM name: Returned: %s' % vminfo)
      mt = re.findall('get-vm-name %d: name: (.*?)\n' % num, vminfo)
      if not mt:
         raise AppControlError('Cannot parse VM name from: %s' % vminfo)
      name = mt[0]
      return name

   def GetAppInfo(self, num):
      """
      Retrieve information on an Application

      @returns: A tuple of (The App name, The App product)
      """
      appInfo = self.RunAppControl(b'initialize workstation\nrefresh-lists\nget-app-name %d\nget-app-product %d\nexit\n' % (num, num))

      if re.findall('bad-arg', appInfo):
         raise AppControlError('Cannot retrieve App name: Returned: %s' % appInfo)
      mt = re.findall('get-app-name %d: name: (.*?)\n' % num, appInfo)
      if not mt:
         raise AppControlError('Cannot parse App name from: %s' % appInfo)
      name = mt[0]
      mt = re.findall('get-app-product \d+: product: (.*?)\n', appInfo)
      if not mt:
         raise AppControlError('Cannot parse App product from: %s' % appInfo)
      product = mt[0]

      return (name, product)

   def ShutdownAll(self):
      """ Suspend all running VMs and kill running user interfaces """
      try:
         self.RunAppControl(b'initialize workstation\nrefresh-lists\nshutdown-vm all\nexit\n')
      except Exception as e:
         # It's completely acceptable to hit an exception here.  Log it and return.
         log.info('Acceptable exception while shutting down VMs: %s' % e)
         return

      time.sleep(2)  # Slight pause to let the final VM close
      # XXX: For now the app doesn't close UIs, so do our heavy-handed killall on our UIs.
      # XXX: This will go away when vmware-app-control implements "shutdown-app all"
      run('/usr/bin/killall', 'vmplayer', 'vmware', ignoreErrors=True)
      time.sleep(2)  # Slight pause to let the kill process finish
