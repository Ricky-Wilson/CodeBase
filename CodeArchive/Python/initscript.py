def ConfigureService(serviceName, description, lsbStartDep, lsbStopDep, lsbStartBefore,
                     lsbStopAfter, chkcfgStartLevel, chkcfgStopLevel):
   """
   Configure a service using the program appropriate for the current system.
   Right now we support insserv, chkconfig, and update-rc.d

   ********                        READ ME ...  IMPORTANT!
   ********
   ******** This function expects the component using it to have the initinfo scripts in
   ******** initinfo/initinfo.*.  They shouldn't be installed, they should just be included
   ******** in the component.  Without them, it will fail.
   ********

   @param serviceName: The service name, matches the script name
   @param description: Text description of the service.  Single-line only
   @param lsbStartDep: Space separated list of services that must be started *before* this service.
   @param lsbStopDep: Space separated list of services that must be stopped *after* this service.
   @param lsbStartBefore: Space separated list of reverse deps.  This package must start before these.
   @param lsbStopAfter: Space separated list of reverse deps.  This package must stop after these.
   @param chkcfgStartLevel: The start number for chkconfig or update-rc.d scripts
   @param chkcfgStopLevel: The stop number for chkconfig or update-rc.d scripts
   """
   scriptFile = INITSCRIPTDIR/serviceName
   if not INITSCRIPTDIR or not scriptFile.exists():
      # TODO: Raise a dialog informing the user that we are unable to add init script links.
      # TODO: This can take the place of Workstation's current message for Gentoo and Arch
      # TODO: systems.
      return
   script = scriptFile.text()

   (initType, initProgram) = InitConfigProgram()

   if not initType:
      # We can't use a program to do it for us, lay down the links ourselves.
      if not INITDIR:
         # TODO: Raise a dialog informing the user that we are unable to add init script links.
         # TODO: This can take the place of Workstation's current message for Gentoo and Arch
         # TODO: systems.
         log.Warn('INITDIR has not been set.  No rc?.d style dirs '
                    'to populate.')
         return

      script = INITSCRIPTDIR/serviceName
      pattern = 'rc%(runlevel)d.d/%(letter)s%(priority)02d%(name)s'

      for runlevel in (2, 3, 5):
         # Build symlinks for this runlevel
         startLink = path(INITDIR/(pattern % {'runlevel': runlevel, 'letter': 'S',
                                              'priority': chkcfgStartLevel, 'name': serviceName}))
         stopLink = path(INITDIR/(pattern % {'runlevel': runlevel, 'letter': 'K',
                                             'priority': chkcfgStopLevel, 'name': serviceName}))
         try:
            script.symlink(startLink)
         except OSError as e:
            pass # Okay if it already exists
         try:
            script.symlink(stopLink)
         except OSError as e:
            pass # Okay if it already exists

         # Register files with the installer.  It will clean them up on uninstall.
         inst.RegisterFile(startLink)
         inst.RegisterFile(stopLink)

   if initType == 'insserv':
      # Add the insserv style header and add our service
      initheader = inst.GetFileText('initinfo/initinfo.lsb')
      initheader = re.sub('@@SERVICE_NAME@@', serviceName, initheader)
      initheader = re.sub('@@LSB_SERVICE_START_DEP@@', lsbStartDep, initheader)
      initheader = re.sub('@@LSB_SERVICE_STOP_DEP@@', lsbStopDep, initheader)
      initheader = re.sub('@@LSB_SERVICE_START_BEFORE_DEP@@', lsbStartBefore, initheader)
      initheader = re.sub('@@LSB_SERVICE_STOP_AFTER_DEP@@', lsbStopAfter, initheader)
      initheader = re.sub('@@SERVICE_DESCRIPTION@@', description, initheader)
      txt = re.sub('# VMWARE_INIT_INFO', initheader, script, re.DOTALL)
      scriptFile.write_text(txt)
      inst.RunCommand('/bin/sh', '-c', '%s -f %s >/dev/null 2>&1' % (initProgram, serviceName), ignoreErrors=True)

   if initType == 'chkconfig':
      # Add the chkconfig style header and add our service
      initheader = inst.GetFileText('initinfo/initinfo.chkconfig')
      initheader = re.sub('@@CHKCFG_START_LEVEL@@', str(chkcfgStartLevel), initheader)
      initheader = re.sub('@@CHKCFG_STOP_LEVEL@@', str(chkcfgStopLevel), initheader)
      initheader = re.sub('@@SERVICE_DESCRIPTION@@', description, initheader)
      txt = re.sub('# VMWARE_INIT_INFO', initheader, script, re.DOTALL)
      scriptFile.write_text(txt)
      inst.RunCommand(initProgram, '--add', serviceName, ignoreErrors=True)

   if initType == 'update-rc.d':
      # Add the insserv style header and add our service
      initheader = inst.GetFileText('initinfo/initinfo.updaterc')
      initheader = re.sub('@@SERVICE_NAME@@', serviceName, initheader)
      initheader = re.sub('@@LSB_SERVICE_START_DEP@@', lsbStartDep, initheader)
      initheader = re.sub('@@LSB_SERVICE_STOP_DEP@@', lsbStopDep, initheader)
      initheader = re.sub('@@LSB_SERVICE_START_BEFORE_DEP@@', lsbStartBefore, initheader)
      initheader = re.sub('@@LSB_SERVICE_STOP_AFTER_DEP@@', lsbStopAfter, initheader)
      initheader = re.sub('@@SERVICE_DESCRIPTION@@', description, initheader)
      txt = re.sub('# VMWARE_INIT_INFO', initheader, script, re.DOTALL)
      scriptFile.write_text(txt)
      inst.RunCommand(initProgram, serviceName,
                      'start', chkcfgStartLevel, '2', '3', '4', '.', 
                      'stop', chkcfgStopLevel, '0', '6', '.', ignoreErrors=True)

   log.Info('Installed Service: %s' % serviceName)

def DeconfigureService(serviceName):
   (initType, initProgram) = InitConfigProgram()
   if not initType:
      # The links have been registered with the installer.  It will remove them on
      # uninstall.
      pass

   if initType == 'insserv':
      inst.RunCommand('/bin/sh', '-c', '%s -f -r %s >/dev/null 2>&1' % (initProgram, serviceName), ignoreErrors=True)
   if initType == 'chkconfig':
      inst.RunCommand(initProgram, '--del', serviceName, ignoreErrors=True)
   if initType == 'update-rc.d':
      inst.RunCommand(initProgram, '-f', serviceName, 'remove', ignoreErrors=True)

   log.Info('Uninstalled Service: %s' % serviceName)

def InitConfigProgram():
   """
   Scan the system to try and guess the program that sets up the init script links.
   On RHEL, it's chkconfig, on SuSE it's insserv, and on Ubuntu it's update-rc.d.

   NOTE: Don't use insserv on Ubuntu per bug 776485.  Ubuntu so very wisely ships
         it but expects developers not to use it.
   """

   # First, check for update-rc.d b/c we want to use it instead
   # of insserv on Ubuntu and Debian systems.
   if path('/usr/sbin/update-rc.d').isexe():
      return ('update-rc.d', '/usr/sbin/update-rc.d')
   elif path('/sbin/update-rc.d').isexe():
      return ('update-rc.d', '/sbin/update-rc.d')
   elif (_which('update-rc.d')):
      return ('update-rc.d', _which('update-rc.d'))

   if path('/sbin/insserv').isexe():
      return ('insserv', '/sbin/insserv')
   elif _which('insserv'):
      return ('insserv', _which('insserv'))

   if path('/sbin/chkconfig').isexe():
      return ('chkconfig', '/sbin/chkconfig')
   elif (_which('chkconfig')):
      return ('chkconfig', _which('chkconfig'))

   # XXX: Add support for upstart in the future.

   return (None, None)

def _which(program):
   """
   Gets the PATH environment variable and checks for program
   in order.

   @param program: Executable to search for
   @returns: Full path if found and executable, None otherwise
   """
   # XXX: Borrowed from util/shell.py.  This should be broken into a
   # utility file to be used by both components and the main code.
   systemPath = ENV['PATH']
   paths = systemPath.split(':')
   for p in paths:
      fullPath = path(p)/program
      if fullPath.isexe():
         return str(fullPath) # Return a string, not a path object

   return None
