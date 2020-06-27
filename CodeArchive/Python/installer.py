"""
Copyright 2007,2020 VMware, Inc.  All rights reserved. -- VMware Confidential

Module for handling the installation side of components.
"""

from vmis import vmisdebug # For fatal_error

from vmis.core.errors import *

# XXX: Remove InstallerType when env.py is fixed to no longer
#  use it.
class InstallerType(type):
   """ Metaclass for registering component installers """
   def __new__(cls, name, bases, dct):
      return type.__new__(cls, name, bases, dct)

   def __init__(cls, name, bases, dct):
      type.__init__(cls, name, bases, dct)

class IType:
   """ Installer Type Enum """
   LOCALOPS, REMOTEINSTALLER, REMOTEOPS = list(range(3))

class InstallerLog(object):
   """
   This class is here as a convenience to the user.  It allows them
   to use the logging facilities of the installer with statements
   such as log.debug("message")
   """
   def __init__(self, installer):
      self.installer = installer

   def Debug(self, *args, **kwargs):
      """ Log a message """
      return self.installer.Log('debug', *args, **kwargs)

   def Info(self, *args, **kwargs):
      """ Log a message """
      return self.installer.Log('info', *args, **kwargs)

   def Warn(self, *args, **kwargs):
      """ Log a message """
      return self.installer.Log('warning', *args, **kwargs)

   def Error(self, *args, **kwargs):
      """ Log a message """
      return self.installer.Log('error', *args, **kwargs)

   def Critical(self, *args, **kwargs):
      """ Log a message """
      return self.installer.Log('critical', *args, **kwargs)

class InstallerGUI(object):
   """
   This class is here as a convenience to the user.  It scopes the
   gui functions in the components to gui.*
   """
   def __init__(self, installer):
      self.installer = installer

   def SetBannerImage(self, banner):
      """ Set banner image for use during installation """
      return self.installer.SetBannerImage(banner)

   def SetIconImages(self, filePaths):
      """ Sets the icons to be used for the window """
      return self.installer.SetIconImages(filePaths)

   def SetHeaderImage(self, imagePath):
      """ Sets the header image """
      return self.installer.SetHeaderImage(imagePath)

   def UserMessage(self, text, useWrapper=True):
      """ The GUI displays a message to the user """
      return self.installer.UserMessage(text, useWrapper=useWrapper)

class Installer(object, metaclass=InstallerType):
   """ Base class for all installers.  There should be little to no
   actual code in this class as we want imports for this file to
   be as limited as possible.

   Local access code will be stored in the LocalInstaller class
   and all imports relative to it in that file.

   Remote access code will be stored in the RemoteInstaller class
   and all imports relative to it in that file.  These should be
   limited to *only* those that are necessary to either implement
   functionality or to communicate with the main installer.
   Remote installation needs to be as encapsulated as possible as
   any modules that require dynamic loading will *NOT* load on the
   remote side.  As such, we cannot allow the main bulk of VMIS code
   to import.
   """

   def VerifyArguments(self, arg):
      """
      Verify arguments before pickling.  They should only match a specific
      set of types, otherwise they could be problematic during pickling or
      unpickling.  Log a debug level warning if one is found, along with the
      traceback, which pinpoints where it came from.
      """
      # Check types here to be sure that they are okay to pickle and transfer
      # We can't have any complicated types, so it's going to be a pretty
      # limited set.
      validTypes = (int, str, bool, list, tuple, dict, bytes, None)

      if type(arg) in (tuple, list):
         for a in arg:
            self.VerifyArguments(a)

      if type(arg) == dict:
         for key in arg:
            self.VerifyArguments(arg[key])

      if type(arg) not in validTypes and arg is not None:
         self.Log('debug', 'Pickle Warning: Invalid type: %s' % str(type(arg)))
         import traceback
         self.Log('debug', '\n'.join(traceback.format_stack()))

   def MessageIn(self, uid, str):
      self.proxyObject.MessageIn(uid, str)

   # Proxy to load in a local or remote component.
   proxyObject = None

   def SetInstallerType(self, itype, UID=-1):
      """ Import and load the correct code for a local or remote
      installer.

      @param itype: type of installer to create
      @param UID: Only used for RemoteInstallers
      """
      if itype == IType.LOCALOPS:
         from .localinstallerops import LocalInstallerOps as ProxyInstaller
         self.proxyObject = ProxyInstaller(self)
      elif itype == IType.REMOTEINSTALLER:
         from .remoteinstaller import RemoteInstaller as ProxyInstaller
         if UID == -1:
            raise ValueError('UID not set for RemoteInstaller')
         self.proxyObject = ProxyInstaller(self, UID)
      elif itype == IType.REMOTEOPS:
         from .remoteinstallerops import RemoteInstallerOps as ProxyInstaller
         self.proxyObject = ProxyInstaller(self)
      else:
         raise TypeError('Unknown installer type: %d' % itype)


   isProduct = property(lambda self: self.GetManifestValue("bonus"))
   """ True if the installer is flagged as a product, otherwise False """

   # Passthroughs to the proxy
   component = property(lambda self: self.proxyObject._component)
   files = property(lambda self: self.proxyObject._files)
   permissions = property(lambda self: self.proxyObject._permissions)
   filetypes = property(lambda self: self.proxyObject._filetypes)
   questions = property(lambda self: self.proxyObject._questions)
   banner = property(lambda self: self.proxyObject._banner)
   iconImagePaths = property(lambda self: self.proxyObject._iconImagePaths)
   headerImagePath = property(lambda self: self.proxyObject._headerImagePath)

   def __init__(self):
      # Have the installer default to local ops by default.
      self.SetInstallerType(IType.LOCALOPS)
      self.log = InstallerLog(self)
      self.gui = InstallerGUI(self)

   # Passthrough for config
   def GetAnswer(self, key, default=None, component=None):
      """
      Just a passthrough for GetConfig.  This function mirrors
      AddQuestion.
      """
      return self.GetConfig(key, default=default, component=component)
   
   def GetConfig(self, key, default=None, component=None):
      return self.proxyObject.GetConfig(key, default=default,
                                        component=component)

   def SetConfig(self, key, val):
      return self.proxyObject.SetConfig(key, val)

   def DelConfig(self, key):
      return self.proxyObject.DelConfig(key)

   def GetManifestValue(self, key, default=None):
      """ Pass Manifest info to component """
      return self.proxyObject.GetManifestValue(key, default)

   def GetFileValue(self, key):
      """
      Get the value of one of our special files.
      ie: BINDIR, LIBDIR
      """
      return self.proxyObject.GetFileValue(key)

   def PreTransactionInstall(self, old, new, upgrade):
      """
      Called before anything else during install.

      This is where global settings like branding should be set.
      """
      return self.proxyObject.PreTransactionInstall(old, new, upgrade)

   def PreTransactionUninstall(self, old, new, upgrade):
      """
      Called before anything else during uninstall.
      """
      return self.proxyObject.PreTransactionUninstall(old, new, upgrade)

   def PostTransactionInstall(self, old, new, upgrade):
      """
      Called after everything else during install.

      This function is called after the database has been committed
      for the current component.  Since no transaction is active at
      this point, external programs may modify the installer database.
      """
      return self.proxyObject.PostTransactionInstall(old, new, upgrade)

   # Note: There is no PostUninstallTransaction because there's no
   # sane way to reference a component in the database that has
   # already been deleted.  For example, if you were to call
   # PostUninstallTransaction it would fail when it tried to log the
   # component being called because its name can no longer be looked
   # up in the database.

   def InitializeQuestions(self, old, new, upgrade):
      """
      XXX: to be removed in favor of PreTransaction.

      Called for each component scheduled to be installed.

      InitializeQuestions should add (or remove) any questions to be
      asked.
      """
      return self.proxyObject.InitializeQuestions(old, new, upgrade)

   def InitializeInstall(self, old, new, upgrade):
      """
      Called for each component scheduled to be installed after
      questions have been asked.

      Initialize should perform quick, fail-fast checks on the system
      to determine whether or not the component is able to be
      installed.  It should check for dependencies on the system that
      cannot be expressed otherwise.  The state of the system should
      not be modified.

      The component should also populate its file and question sets
      here.
      """
      return self.proxyObject.InitializeInstall(old, new, upgrade)

   def InitializeUninstall(self, old, new, upgrade):
      """
      Called for each component scheduled to be uninstalled.

      Initialize should perform quick, fail-fast checks on the system
      that would prevent the component from being uninstalled.
      """
      return self.proxyObject.InitializeUninstall(old, new, upgrade)

   def PreInstall(self, old, new, upgrade):
      """
      Called before component installation commences.

      PreInstall should perform whatever tasks are necessary to put
      the system in a state where the component may be installed.

      PreInstall should rarely fail.  Any likely scenarios to cause
      failure should be checked for in Initialize instead.
      """
      return self.proxyObject.PreInstall(old, new, upgrade)

   def PostInstall(self, old, new, upgrade):
      """
      Called after a component is installed.

      PostInstall should configure the compoonent on the system.  Any
      changes made here should likely have a counterpart in
      PostUninstall.

      Example:  Making changes to a system configuration file.
      """
      return self.proxyObject.PostInstall(old, new, upgrade)

   def PreUninstall(self, old, new, upgrade):
      """
      Called before component uninstallation commences.

      PreUninstall should perform whatever tasks are necessary to
      decommission the component before its files are removed from the
      system.

      PreUninstall should rarely fail.  Any likely scenarios to cause
      failure should be checked for in Initialize instead.

      Example: Services must be stopped before Workstation can be
      uninstalled.  However, stopping services can fail if there are
      virtual machines running.  Instead of PreInstall failing because
      services failed to stop, Initialize should check if virtual
      machines are running in the first place.
      """
      return self.proxyObject.PreUninstall(old, new, upgrade)

   def PostUninstall(self, old, new, upgrade):
      """
      Called after a component is uninstalled.

      PostUninstall should unconfigure the component on the system.
      Anything changed in PostInstall should likely have a counterpart
      here.

      Example:  Undoing changes made to system configuration file.
      """
      return self.proxyObject.PostUninstall(old, new, upgrade)

   def RunCommand(self, *args, **kwargs):
      """
      Accepts a set of arguments, as they would be passed to the command
      line.

      Use as:
        RunCommand('sed', '-e', 's,foo,bar,g')
      NOT as:
        RunCommand('sed -e "s,foo,bar,g"')

      @return tuple of (retval, stdout, stderr)
      """
      return self.proxyObject.RunCommand(*args, **kwargs)

   def Log(self, logType, *args, **kwargs):
      """ Log a message """
      return self.proxyObject.Log(logType, *args, **kwargs)

   def SetBannerImage(self, banner):
      """ Set banner image for use during installation """
      return self.proxyObject.SetBannerImage(banner)

   def SetIconImages(self, filePaths):
      """ Sets the icons to be used for the window """
      return self.proxyObject.SetIconImages(filePaths)

   def SetHeaderImage(self, imagePath):
      """ Sets the header image """
      return self.proxyObject.SetHeaderImage(imagePath)

   def GetFileText(self, filePath, textMode = True):
      """ Extracts a file from the component and returns the contents """
      return self.proxyObject.GetFileText(filePath, textMode)

   def GetFilePath(self, filePath):
      """ Extracts a file from the component and returns the temp path """
      return self.proxyObject.GetFilePath(filePath)

   def UserMessage(self, text, useWrapper=True):
      """ The GUI displays a message to the user """
      return self.proxyObject.UserMessage(text, useWrapper=useWrapper)

   def SetComponent(self, component):
      """ Sets the component """
      return self.proxyObject.SetComponent(component)

   def SetUID(self, UID):
      return self.proxyObject.SetUID(UID)

   def AddQuestion(self, questType, *args, **kwargs):
      return self.proxyObject.AddQuestion(questType, *args, **kwargs)

   def AddTarget(self, targetType, src, dest):
      return self.proxyObject.AddTarget(targetType, src, dest)

   def SetPermission(self, src, perm):
      return self.proxyObject.SetPermission(src, perm)

   def SetFileType(self, src, fileType):
      return self.proxyObject.SetFileType(src, fileType)

   def LoadInclude(self, filename):
      return self.proxyObject.LoadInclude(filename)

   def CompilePythonFile(self, filePath):
      """
      Byte-compiles a Python file for the current component.

      This should only be used in PostInstall for files that are
      dynamically generated and cannot be installed at install time.

      It's advisable to register this file with Register File if it
      needs to be removed by the installer during uninstall.
      """
      return self.proxyObject.CompilePythonFile(filePath)

   def RegisterFile(self, filename, mtime=None, fileType='File'):
      """
      Register a file with the installer.
      """
      return self.proxyObject.RegisterFile(filename, mtime=mtime, fileType=fileType)

   def RegisterDirectory(self, dirname, mtime=None, fileType='File'):
      """
      Recursively register all files in a directory with the installer.
      """
      return self.proxyObject.RegisterDirectory(dirname, mtime=mtime,
                                                fileType=fileType)

   def RegisterService(self, name, src, start, stop):
      """
      Register a service to be installed.  Caller is still responsible
      for start/stopping services.  This *must* be called in PreInstall or
      earlier in order to register the symlinks with the installer.  If it's
      done later, they won't be laid down.

      @param name: base init script name
      @param src: component source path
      @param start: start priority
      @param stop: stop priority
      """
      return self.proxyObject.RegisterService(name, src, start, stop)
