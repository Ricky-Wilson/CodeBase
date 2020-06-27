"""
Copyright 2007-2016,2020 VMware, Inc.  All rights reserved. -- VMware Confidential

@todo: consolidate logging formatting for components
"""

import imp
import fnmatch
import os

from vmis import vmisdebug, VERSION
from vmis.db import db, IntegrityError
from vmis.util.log import getLog
from vmis.util.path import path
from vmis.core.dependency import Version
from vmis.core.component import ComponentError, ComponentTypes
from vmis.core.env import LoadInstaller
from vmis.core.files import File, CONFDIR, INITDIR, INITSCRIPTDIR, LIBDIR, BINDIR
from vmis.core.installer import Installer, IType

import vmis.core.installers     # Must be loaded for importing installers

from pprint import pformat

log = getLog('vmis.core.install')

class Action(object):
   """ Generic install action """
   def __init__(self, component, old, new):
      self.component = component

      self.old = old
      self.new = new

      # If both old and new are set, we are upgrading.  This has been
      # set by transaction.py:ActionsFromComponents
      if self.old is None or self.new is None:
         self.upgrade = False
      else:
         self.upgrade = True

      # Make sure our arguments are not complex types.  (str, str, bool) is
      # acceptable for pickling back to the component.
      self.args = dict(old=str(self.old.version) if self.old else None,
                       new=str(self.new.version) if self.new else None,
                       upgrade=self.upgrade)

   def IsUpgrading(self):
      return self.upgrade

   def __cmp__(self, other):
      if not self.component:
         return -1
      elif not other:
         return 1
      else:
         return (self.component.name > other.component.name) - (self.component.name < other.component.name)

   def __repr__(self):
      return '[%s] %s %s (%s %s %s)' % (self.__class__.__name__,
                                        self.component.name,
                                        self.component.version,
                                        self.new and self.new.version or None, # ** See comment below
                                        self.old and self.old.version or None,
                                        self.upgrade)
      # ** This line is the equivalent of:
      #      if self.new is valid, pass in self.new.version, else pass in None

class ChangeBonus(Action):
   """
   This class defines the action that changes the product bonus of
   a component after install or uninstall.
   XXX: Fold into installation/uninstallation.
   """
   def __init__(self, component, db, bonus):
      super(ChangeBonus, self).__init__(component, None, None)
      self.component = component
      self.name = self.component.name
      self.bonus = bonus

   def __cmp__(self, other):
      if all((self.component == other.component,
              self.name == other.name,
              self.bonus == other.bonus)):
         return 0
      else:
         return 1

   def __eq__(self, other):
      return self.__cmp__(other) == 0

   def Execute(self):
      """
      Set or unset the bonus on a component in the database.
      """
      # Set the bonus for the component.  This happens to already installed
      # components during uninstallation, or to components that have completed
      # the installation process, so it is safe to touch the database with their
      # uid.
      if self.bonus:
         db.database.components.SetType(self.component.uid, ComponentTypes.PRODUCT)
      else:
         db.database.components.SetType(self.component.uid, ComponentTypes.REGULAR)

class Uninstall(Action):
   def __init__(self, component, db, old=None, new=None):
      """
      @param component: component to uninstall
      @param db: database to uninstall component from
      """
      super(Uninstall, self).__init__(component, old, new)
      self.purgeDirs = set()

   def Load(self, temp):
      """ Load and create component installer """
      # If we are unable to load the component's installer we will
      # instead create a blank one so that at least its files may be
      # properly removed.
      try:
         # When uninstalling, we prefer to use the same VMIS
         # as is when the component was installed.
         self._module, self._installer = LoadInstaller(self.component,
                                                       self.component.installDir,
                                                       preferInstalledVmis=True,
                                                       upgrading=self.IsUpgrading())
      except (ImportError, SyntaxError):
         # We may be unable to load the file or it may be syntactically invalid.
         log.error('[%s %s] Unable to load component installer for uninstallation.  '
                   'Only files will be removed.  Tried directory %s.',
                   self.component.name, self.component.version, self.component.installDir)
         self._installer = Installer()
         self._installer.SetInstallerType(IType.LOCALOPS)

      # For Python3.2+, the compiled python files are versioned. And the
      # installer may use newer Python runtime to execute the old components
      # during upgrading process. So, compiled files of newer version may be
      # created on disk, but not recorded in the sqlite database. To resolve
      # this issue, during the upgrading process, manually create compiled
      # files, and register them to sqlite database. In this way, they can
      # be removed in PostUninstall().
      if self.IsUpgrading():
         installedPyVersion = db.config.Get(
            'vmware-installer',
            '%s.pyver' % os.environ.get('VMWARE_VMISVERSION_INSTALLED', None),
            None)
         installingPyVersion = os.environ.get('VMISPYVERSION', None)
         if installedPyVersion > '30' and \
            installingPyVersion > installedPyVersion:
            for f in self.component.installDir.walkfiles('*.py'):
               compiled = self._installer.CompilePythonFile(f)
               self._installer.RegisterFile(compiled)

   def PreTransaction(self):
      log.debug('[%s %s] PreTransactionUninstall', self.component.name,
                                                    self.component.version)
      self._installer.PreTransactionUninstall(**self.args)

   def Initialize(self, temp):
      log.debug('[%s %s] InitializeUninstall', self.component.name, self.component.version)
      self._installer.InitializeUninstall(**self.args)

   def PreUninstall(self):
      log.debug('[%s %s] PreUninstall', self.component.name, self.component.version)
      self._installer.PreUninstall(**self.args)

   def _removeFiles(self, files, onProgress):
      """
      Remove files

      @param files: list of file id's to be removed
      @param onProgress: function to be called for each file removed
      """
      for uid in files:
         filePath = path(db.files.GetPath(uid))
         mtime = db.files.GetMtime(uid)
         fileType = db.files.GetType(uid)

         try:
            if fileType == File.id or not self.upgrade:
               log.debug('[%s] Removing file %s', self.component.name, filePath)
               filePath.remove()
               self.purgeDirs.add(filePath.dirname())
         except OSError:
            log.info('[%s] %s did not exist', self.component.name, filePath)

         db.files.Remove(uid)
         onProgress()

   def PostUninstall(self, onProgress=lambda: None):
      """"
      Run PostUninstall in the installer and remove remaining
      support files on success

      @param onProgress: function to be called for each file removed
      """
      log.debug('[%s %s] PostUninstall', self.component.name, self.component.version)
      self._installer.PostUninstall(**self.args)

      # Remove the files from the DB
      self._removeFiles(db.database.components.GetFiles(self.component.uid), onProgress)
      self.deleteEmptyDirs()

      # Assume everything was successful and remove the component from the DB
      db.database.components.Remove(self.component.uid)

   def Execute(self, temp, onProgress=lambda: None):
      """
      Uninstall all files that the component installed except
      supporting files located in CONFDIR.
      """
      log.debug('[%s %s] Uninstall', self.component.name, self.component.version)

      self._removeFiles(db.database.components.GetInstalledFiles(self.component.uid), onProgress)

   def deleteEmptyDirs(self):
      """ Deletes all empty directories left behind """
      purge = []

      for i in self.purgeDirs:
         dirname = i

         # XXX hack: don't recursively rmdir the rc*.d or init.d directories.
         # See the details in bug #303275.
         if fnmatch.fnmatch(i, str(INITDIR/'rc[0-6S].d')) or \
            i.startswith(str(INITSCRIPTDIR)):
            log.debug('Skipping removal of %s directory' % i)
            continue

         while dirname != '/':
            if dirname not in purge:
               purge.append(dirname)

            dirname = dirname.dirname()

      # Clean up empty directories left behind.  Don't even think
      # about using a function that recursively deletes!
      #
      # The set will look something like this:
      #
      # /a/b/c
      # /a/b
      # /a
      #
      # / is ommited
      purge.sort(key=len, reverse=True)

      log.debug('Deleting empty directories:\n%s', pformat(purge))

      for d in purge:
         # @fixme: Is there a more efficient way to check for an empty
         # directory?  Seems like path.files() and path.dirs() could
         # be expensive for directories with a lot of files but
         # throwing exceptions is also expensive.
         try:
            d.rmdir()
         except OSError:
            # Either doesn't exist or the directory isn't empty.
            log.debug('Unable to remove %s', d)
            pass

   def Count(self):
      """ Returns the number of files to be uninstalled """
      return len(db.database.components.GetFiles(self.component.uid))

class Install(Action):
   """ Installation action """

   def __init__(self, component, db, old=None, new=None):
      """
      @param component: loaded component
      @param db: database to install component to
      """
      super(Install, self).__init__(component, old, new)
      if db == None:
         print('Install self: ', end=' ')
         print(self)
         print('DB: ', end=' ')
         print(db)
         vmisdebug.FatalError('install.py: Install: Database is None!')

   def PreCopy(self, filePath):
      """ Called before a file is to be installed onto the system """
      # exists() returns False for broken symlinks so check them
      # explicitly.
      if filePath.islink() or filePath.exists():   # Check if configuration file, etc.
         log.warning('destination %s already exists, overwriting.' % filePath)
         filePath.remove(ignore_errors=True)

      # If the file needs a directory path and it doesn't already exist, create it.
      destDir = filePath.dirname()
      if destDir.exists() and not destDir.isdir():
         # If it already exists, but as a file, remove the file to pave the
         # way for our directory.
         log.warning('destination %s already exists as a file, recreating as a directory.' % filePath)
         destDir.remove()
      destDir.exists() or destDir.makedirs()

   def PreTransaction(self):
      log.debug('[%s %s] PreTransactionInstall', self.component.name,
                                                  self.component.version)
      self._installer.PreTransactionInstall(**self.args)

   def PostTransaction(self):
      log.debug('[%s %s] PostTransactionInstall', self.component.name,
                                                   self.component.version)
      self._installer.PostTransactionInstall(**self.args)

   def InitializeQuestions(self):
      """ Initialize component installer questions """
      self._installer.InitializeQuestions(**self.args)

   def Load(self, temp):
      """ Load and create component installer """
      # Load in installer files from component file into temp directory
      for entry in self.component.Glob('.installer/*', showHidden=True):
         dest = temp.joinpath(entry.path)
         self.PreCopy(dest)
         self.component.CopyFile(entry, dest)

      try:
         componentDir = (temp/'.installer')/str(self.component.version)
         # When Installing, we prefer to use the VMIS packed in our package.
         self._module, self._installer = LoadInstaller(self.component,
                                                       componentDir,
                                                       preferInstalledVmis=False,
                                                       upgrading=False)
      except:
         # If something goes wrong, this is a fairly fatal error.
         # Explicitly print a message and re-raise the exception.
         log.error('Error: Cannot load installer for component: %s.' % self.component.name)
         raise

   def Initialize(self, temp):
      """ Initialize component installer """
      log.debug('[%s] Initializing' % self.component.name)
      self._installer.InitializeInstall(**self.args)

   def PreInstall(self):
      log.debug('[%s] PreInstall' % self.component.name)
      self._installer.PreInstall(**self.args)

   def PostInstall(self):
      log.debug('[%s] PostInstall' % self.component.name)
      self._installer.PostInstall(**self.args)

   def Execute(self, temp, onProgress=lambda: None):
      """ Installs and registers the component and its files """
      log.debug('[%s] Install' % self.component.name)

      c = self.component

      # Component was given a bonus so record as a product component.
      if c.bonus:
         cType = ComponentTypes.PRODUCT
      else:
         cType = ComponentTypes.REGULAR

      # Register component.
      self.component.uid = db.database.components.Add(c.name, c.version, c.buildNumber, cType, c.coreVersion,
                                             c.longName, c.description)
      uid = self.component.uid

      # Register dependencies for components
      for dep in self.component.dependencies:
         db.database.components.AddDependency(uid, dep)

      # Register reverse dependencies for components
      for revdep in self.component.reverseDependencies:
         db.database.components.AddReverseDependency(uid, revdep)

      # Register conflicts with the DB
      for conf in self.component.conflicts:
         db.database.components.AddConflict(uid, conf) # Add conflict to DB as string

      # Install component installer files.
      for entry in self.component.Glob('.installer/*', showHidden=True):
         dest = CONFDIR.joinpath('components').joinpath(
            self.component.name).joinpath(
            entry.path.replace('.installer/', '', 1))

         self.PreCopy(dest)

         # XXX: this can leave empty directories behind if Add() fails
         # Write a usable error to the log in case of a problem.
         try:
            self.component.CopyFile(entry, dest)
            db.files.Add(dest, int(dest.mtime), File.id, uid) # Add file dest to component uid
         except IntegrityError:
            log.error('Error: Adding file %s with mtime %s, fileType %s,'
                       ' and uid %s.', dest, int(dest.mtime), File.id, uid)
            dest.remove(ignore_errors=True)
            raise

         if self.component.name == "vmware-ovftool" and\
            ("update.py" in str(dest) or "initscript.py" in str(dest)):
            pass
         else:
            compiled = self._installer.CompilePythonFile(dest)
            self._installer.RegisterFile(compiled)

      # Copy files.
      for mapping in self._installer.files:
         source, dest = list(mapping.items())[0] # There's only one entry per map right now.

         for filePath in source.Install(self._installer.component, dest, self.PreCopy):
            try:
               fileMtime = int(filePath.mtime)
            except OSError:
               log.exception('Could not get mtime for %s' % filePath)
               fileMtime = 0
            # Write a usable error to the log in case of a problem.
            try:
               db.files.Add(filePath, fileMtime, dest.fileType.id, uid)
            except IntegrityError:
               log.error('Integrity Error: Adding file %s with mtime %s, fileType %s,'
                          ' and uid %s.', filePath, fileMtime, dest.fileType.id, uid)
               raise
            onProgress()

      # Register file types.
      for ft in self._installer.filetypes:
         filePath = str(ft)

         fuid = db.files.FindByPath(filePath)

         # @todo: make sure it doesn't belong to another component
         if not fuid:
            fuid = db.files.Add(filePath, 0, ft.fileType.id, uid)
         else:
            db.files.SetType(fuid, ft.fileType.id)

      # Apply permissions.
      for permission in self._installer.permissions:
         for dest, perm in permission.items():
            # Just treat everything as a glob.
            dest = path(dest) # @fixme: have to coerce it to a
                              # string type instead of Path
                              # Template or isinstance will fail

            for fuid in db.files.FindByGlob(dest):
               # Only apply to files belonging to the comoponent.
               if db.files.GetComponent(fuid) != self.component.uid:
                  continue

               filePath = path(db.files.GetPath(fuid))

               # Do not apply permissions to symlinks.  They will apply
               # to the file they point to.
               if filePath.islink():
                  log.warning('Attempting to change symlink %s to permission %o.'
                              ' Operation is not allowed, skipping.' % (filePath, perm))
                  continue

               log.debug('Changing %s to permission %d', filePath, perm)
               filePath.chmod(perm)

      return self.component.uid

   def Count(self):
      """ Returns the number of files to be installed """
      count = 0

      for mapping in self._installer.files:
         source, dest = list(mapping.items())[0] # There's only one entry per map right now.
         count += source.Count(self.component)

      return count
