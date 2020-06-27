"""
Copyright 2008-2016,2020 VMware, Inc.  All rights reserved. -- VMware Confidential

Environent for components.

@todo: disable __import__ somehow (can't do it by just excluding from exec)
"""
import imp
import os

env = {}

env['ENV'] = os.environ

from vmis.db import db

import vmis.core.questions

from vmis.core.installer import Installer, InstallerType, IType

from vmis.util.path import path
from vmis.util.log import getLog
from vmis.util.shell import run, output, Escape

from vmis.core.component import ComponentError, InstalledComponent

from vmis.core.dependency import Version
from vmis import VERSION, VMISPYVERSION

def SetupVMISPY(version):
   """
   Set up a few objects to point to the functions relevant to this
   version of Python so that we don't have to worry about the versions
   in the code.  They can be dynamically changed and the code will still
   refer to the same symbols.

     vmispy.CreateExternalComponent vs. vmispy.CreateExternalComponent25

   Should be called after importing vmispy

   @param version: A string representing the major and minor Python
   version, without the .
   ie: 25, 26, or 30
   """
   import vmispy
   vmispy.CreateExternalComponent = getattr(vmispy, 'CreateExternalComponent%s' % version)
   vmispy.SetPythonInstallerObject = getattr(vmispy, 'SetPythonInstallerObject%s' % version)
   vmispy.SetReturnValue = getattr(vmispy, 'SetReturnValue%s' % version)
   vmispy.RunExternalMethod = getattr(vmispy, 'RunExternalMethod%s' % version)

   if not all([vmispy.CreateExternalComponent,
               vmispy.SetPythonInstallerObject,
               vmispy.SetReturnValue,
               vmispy.RunExternalMethod]):
      vmisdebug.FatalError('Could not assign vmispy to the correct versioned ' \
                           'functions for version %s.' % version)


def CreateComponentLoadFile(moduleName, loadPath, pyversion, component):
   """
   Create a temporary .py file that will set environment variables and
   load a remote component in a separate Python instance.
   """
   # XXX: See if much if this can be converted into C code in pyxx.c
   #  rather than supplied in this file.  Or alternately, it could be
   #  packed into a string, and that executed.  That would be cleaner
   #  than using the file system.
   import tempfile
   fd, envFile = tempfile.mkstemp(suffix='.vmis.env')

   os.write(fd, b"""
# Define VMIS_COMPONENT_ONLY first in this file.
VMIS_COMPONENT_ONLY = 'Set'
import imp
import os

def SetupVMISPY(version):
   vmispy.CreateExternalComponent = getattr(vmispy, 'CreateExternalComponent%s' % version)
   vmispy.SetPythonInstallerObject = getattr(vmispy, 'SetPythonInstallerObject%s' % version)
   vmispy.SetReturnValue = getattr(vmispy, 'SetReturnValue%s' % version)
   vmispy.RunExternalMethod = getattr(vmispy, 'RunExternalMethod%s' % version)

   if not all([vmispy.CreateExternalComponent,
               vmispy.SetPythonInstallerObject,
               vmispy.SetReturnValue,
               vmispy.RunExternalMethod]):
         vmisdebug.FatalError(u'Could not assign vmispy to the correct versioned functions ' \
                              u'for version %s.' % version)

import vmispy
""")
   os.write(fd, str('SetupVMISPY(%s)\n' % pyversion).encode())
   os.write(fd, b"""
import vmis.core.files as files
from vmis.core.installer import Installer, InstallerType, IType
import vmis.util.shell as shell
import vmis.util.path as path

""")
   os.write(fd, str("moduleName = '%s'\n" % moduleName).encode())
   os.write(fd, str("loadPath = '%s'\n" % loadPath).encode())
   os.write(fd, b"""
# Clear any existing installers from the global scope
installer = None

# Setup our module's environment
fileObj, pathName, description = imp.find_module(moduleName, [loadPath])
mod = imp.new_module(moduleName)


# The env variable is used as the stash of extra functionality we want
#  to allow the component to use natively.
env = {}
env['ENV'] = os.environ
env['Installer'] = Installer  # So the module knows about the Installer class
# Add in access to files

# Import errors
import vmis.core.errors as errors
env.update(errors.__dict__)

# Import Version
from vmis.core.version import Version
env['Version'] = Version

# Import regular expression parsing
import re
env['re'] = re

for i in ['SystemFile', 'ConfigFile', 'File', 'Link', 'Destination']:
   env[i] = getattr(files, i)
for i in ['path']:
   env[i] = getattr(path, i)
"""
   )
   # A few useful constants
   for txt in ['BINARY', 'SETUID', 'DEFAULT']:
      var = getattr(vmis.core.files, txt, None)
      os.write(fd, str("env['%s'] = %s\n" % (txt, var)).encode())
   os.write(fd, str("env['PYTHON_VERSION'] = '%s'\n" % pyversion).encode())
   os.write(fd, str("env['RET_VAL'] = 0\n").encode())
   os.write(fd, str("env['RET_STDOUT'] = 1\n").encode())
   os.write(fd, str("env['RET_STDERR'] = 2\n").encode())

   # A helpful class to make Destinations on the component side do what we
   # want them to do, which is to ship off expansion of variables like
   # BINDIR and LIBDIR to the main installer, where it can look up substitutions
   # in the database.
   os.write(fd, b"""
class ComponentDestination(files.Destination):
   def __init__(self, dest, installer, perm=env['DEFAULT'], fileType=files.File):
      # Initialize ourselves as a Destination.
      # BINDIR, LIBDIR, etc. is now stored in self.rawText
      super(ComponentDestination, self).__init__(dest, perm=perm,
                                                 fileType=fileType)

      # Store the installer
      self.installer = installer

   # Override _expand
   def _expand(self):
      # Ship this off to the installer side if we have an installer set
      # in order to get the expanded value back.
      if self.installer:
         val = self.installer.GetFileValue(str(self.rawText))
      else:
         # Try the default installer on this module
         if installer is not None:
            val = installer.GetFileValue(str(self.rawText))
         else:
"""
   )
   # XXX: This is a hack, but it's necessary.  Unhackify if possible.
   # This is a case that should not have ever happened, yet there
   # is code out there that *will* trigger this on upgrade.  Which
   # means we can't cause a fatal error here when the component is
   # already installed.  So:
   # Installed: Evaluate the string.  This isn't proper, but it will
   #   let uninstalation proceed.
   # Being Installed: Dump a stack trace so the programmer can fix
   #   the problem.
   if isinstance(component, InstalledComponent):
      os.write(fd, b"            val = str(self.rawText)\n")
   else:
      os.write(fd, b"            print('No installer has been instantiated yet.')\n")
      os.write(fd, b"            print('You cannot evaluate path variables outside the component class.')\n")
      os.write(fd, b"            raise NotImplementedError\n")
   os.write(fd, b"""
      return val

   # Stolen from Destination and modified in order to override the type
   def __div__(self, divisor):
      ret = ComponentDestination(path.path(self.rawText)/divisor, self.installer,
                                 perm=self.perm, fileType=self.fileType)
      ret.perm = self.perm
      ret.fileType = self.fileType
      return ret

   # Make the / operator work even when true division is enabled.
   __truediv__ = __div__

   def __unicode__(self):
      return self._expand()

   def __str__(self):
      return self._expand()

   def __repr__(self):
      return repr(self._expand())
"""
   )

   # We need these initial values when loading the component file
   # XXX: Find a better way to do this.  We can't use their actual
   # realtime values until the installer is ready to go, which means
   # the files have already been loaded.
   for txt in ['PREFIX', 'SYSCONFDIR', 'BINDIR', 'SBINDIR', 'LIBDIR',
               'DATADIR', 'DOCDIR', 'MANDIR', 'INCLUDEDIR', 'INITSCRIPTDIR',
               'INITDIR', 'CONFDIR']:
      var = getattr(vmis.core.files, txt, None)
      # If it is set, write the value in the temp file
      if var is not None:
         if isinstance(var, vmis.core.files.Destination):
            typemap = {}
            typemap[vmis.core.files.SystemFile] = 'files.SystemFile'
            typemap[vmis.core.files.ConfigFile] = 'files.ConfigFile'
            typemap[vmis.core.files.File] = 'files.File'
            typestr = typemap[var.fileType]
            if typestr is None:
               # This should remain a FatalError.  It is a programming error and should
               #  go through FatalError rather than just throwing an exception.
               vmisdebug.FatalError('var %s is of unknown Destination file type!' % (txt,))
            else:
               # Create our presets as ComponentDestinations, with an installer value of
               # None at the moment since we haven't built it yet.
               os.write(fd, str("env['%s'] = ComponentDestination('%s', None, perm=%s, fileType=%s)\n" % (txt, var.rawText, var.perm, typestr) ).encode())
      else:
         # Otherwise, set it to None.  The variable NEEDS to be set to something.
         os.write(fd, str("env['%s'] = None\n" % (txt, )).encode())

   os.write(fd, b"""
# Add the current environment to the module's dict, so it can access
#  items such as BINDIR, LIBDIR, etc.
mod.__dict__.update(env)

exec(fileObj.read(), mod.__dict__)

# Components are expected to include one (and only one) Installer subclass
# inside their module. We iterate over the module's dict looking for that
# item, and then instantiate it.
installers = [o for o in mod.__dict__.values() if
              type(o) is InstallerType and o is not Installer]
if len(installers) != 1:
   raise ComponentError(u'Component did not register an installer', component)
else:
   installer = installers[0]()

# XXX: Remote logging removed for now.  mod.log = getLog(moduleName)

installer.SetInstallerType(IType.REMOTEOPS)
installer.loadPath = loadPath

# Move some functionality out of the installer, into the module.
mod.__dict__['log'] = installer.log
mod.__dict__['installer'] = installer
"""
   )
   # We needed these set to initialize the component, but we couldn't get
   # an installer before the component was initialized.  Now that we have
   # an installer object, insert it back into each of our already created
   # presets.  From this point on, they will expand to the correct value.
   filelist = ['PREFIX', 'SYSCONFDIR', 'BINDIR', 'SBINDIR', 'LIBDIR',
               'DATADIR', 'DOCDIR', 'MANDIR', 'INCLUDEDIR', 'INITSCRIPTDIR',
               'INITDIR', 'CONFDIR']
   for txt in filelist:
      var = getattr(vmis.core.files, txt, None)
      os.write(fd, str("mod.__dict__['%s'].installer = installer\n" % txt).encode())

   os.write(fd, b"""
# mod MUST be held onto so that Python does not garbage
# collect this module.  Furthermore, this reference is
# used in the component's LoadInclude method so that an
# import can have a copy of the component's full environment.
# Hold a reference to this component's environment as well.
installer.mod = mod
installer.env = env
"""
            )
   os.close(fd)
   return envFile


def LoadInstaller(component, loadPath, preferInstalledVmis, upgrading):
   """
   Load an installer module

   @param component: component to load
   @param loadPath: path to load it from
   @param preferInstalledVmis: should be True for uninstalling and
   False for installing
   @param upgrading: indicate component upgrading or not.
   When upgrading is True and preferInstalledVmis is True, and but installed
   python runtime version and installing python runtime version is compatible,
   we will use the installing python runtime.
   @returns (module, installer): returns a tuple containing the containing
   module and installer object.  A reference to the module must be retained
   otherwise you'll wonder why things strangely go out of scope and disappear.

   @raises ImportError
   @raises ComponentError
   """
   # Some components have . in the name (like python2.5) which
   # Python will interpret as being a module separator
   moduleName = component.name.replace('.', '')
   fileObj, pathName, description = imp.find_module(moduleName, [loadPath])

   componentCoreVersion = component.coreVersion
   if component.name == 'vmware-installer': # XXX: HARDCODE - Fix this.
      componentCoreVersion = component.version


   # Go out to the C vmispy code to start up an external VMIS component.
   from vmis.core.remoteinstaller import RemoteInstaller
   import vmispy; # Import here because vmispy is only available when running VMIS,
                  #  but not when building it.

   # XXX: Python will *ALWAYS* already be installed on the system when
   #  I'm doing this?  This is the assumption for now, but no,
   #  this is not necessarily true:
   #
   # XXX: In the case that we are installing a new version of Python
   #  along w/ a new VMIS, Python will reside in the /tmp dir.  We
   #  need to be able to point correctly to it after unpacking it.
   #  FUTURE WORK.

   # Find the installer and python locations as well as the python version for
   # this component
   # XXX: Hardcoded installer component name here

   useInstalledVmis = preferInstalledVmis
   pyversion = None

   # For upgrading scenario, when the installed python is not python 2.x series
   # and installing python version is bigger than the installed version,
   # we assume they are compatible and use installing python runtime,
   # such as python 3.x series.
   if preferInstalledVmis and upgrading:
      pyversion1 = db.config.Get('vmware-installer', '%s.pyver' % componentCoreVersion, None)
      pyversion2 = os.environ['VMISPYVERSION']
      if pyversion1 and pyversion2:
         if int(pyversion1) >= 30 and int(pyversion2) >= int(pyversion1):
            useInstalledVmis = False
            pyversion = pyversion2

   vmisloc = None
   if useInstalledVmis:
      vmisloc = db.config.Get('vmware-installer', '%s.vmisloc' % componentCoreVersion, None)
   if not vmisloc:
      # There is no installed entry for this component, so we must be installing
      # it.  Use the system's version.
      vmisloc = '%s' % os.environ['VMWARE_INSTALLER']

   pythonloc = None
   if useInstalledVmis:
      pythonloc = db.config.Get('vmware-installer', '%s.pyloc' % componentCoreVersion, None)
   if not pythonloc:
      # There is no installed entry for this component, so we must be installing
      # it.  Use the system's version.
      pythonloc = '%s/python' % os.environ['VMWARE_INSTALLER']

   if not pyversion:
      if useInstalledVmis:
         pyversion = db.config.Get('vmware-installer', '%s.pyver' % componentCoreVersion, None)
      if not pyversion:
         # There is no installed entry for this component, so we must be installing
         # it.  Use the system's version.
         pyversion = os.environ['VMISPYVERSION']

   # This is the first point that vmispy is used, set up the function pointers to
   #  point to the correct version for this installer.
   # We have our own VMISPY (and support only this version).
   SetupVMISPY(os.environ['VMISPYVERSION'])

   # We are going to create a simple .py file in a temp directory
   #  that we will need to source.  This file will contain a bit
   #  of Python code to get the ball rolling and fire up the component
   #  on the remote side, as well as a list of environment variables
   #  that will be added into the dictionary for the module, giving
   #  it access to these.
   envFile = CreateComponentLoadFile(moduleName, loadPath, pyversion, component)
   remoteComponentUID = vmispy.CreateExternalComponent(str(pythonloc),
                              str(pyversion),
                              str(vmisloc),
                              str(envFile),
                              '%s/%s.py' % (loadPath, str(component.name)),
                              str(component.version))

   # Remove the temporary file.
   os.unlink(envFile);

   # If we receive a -1, then throw a ComponentError.  The remote component
   #  could not be initialized.  The code in transaction.py knows how to
   #  handle this exception.
   if remoteComponentUID < 0:
      # Error
      raise ComponentError('Component did not register an installer', component)

   # Otherwise, on success, create a remote installer to hand off messages to the real component.
   # Quick explanation of the next three lines:
   #
   # The inheritence chain looks something like:
   #     Installer
   #         | * -----------|                  RemoteComponent
   #  LocalInstallerOps <---|                         ^
   #         |                                        |
   #   RemoteInstaller <----- Messages -----> RemoteInstallerOps
   #
   #
   # LocalInstallerOps implements all the functionality we want to use
   #  locally, so we want to use it as the proxy.
   #
   # RemoteInstaller overrides specific functions, allowing us to catch
   #  the function calls that need to be passed to the remote installer.
   #  Rather than run them through the proxy, they are now passed over to
   #  the component running in a different version of Python.
   #  Calls back into RemoteInstaller from that component are then run
   #  through the proxy, using the methods in LocalInstallerOps and performing
   #  local operations (such as AddQuestion, AddTarget), and the results
   #  passed back through RemoteInstaller.
   #
   installer = RemoteInstaller(remoteComponentUID)
   installer.SetInstallerType(IType.LOCALOPS) # We want this side to use local calls
   installer.SetComponent(component)

   # XXX:  There is no module on this side, so we return None.  It is only being
   #  used to store a reference so that Python does not garbage collect it, and
   #  in this case, we have no module on this side.  It has been created and stored
   #  in the remote component.
   return (None, installer)
