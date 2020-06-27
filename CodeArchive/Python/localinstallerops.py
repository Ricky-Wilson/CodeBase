#
#Copyright 2009,2020 VMware, Inc.  All rights reserved. -- VMware Confidential
#

"""
Module for handling the installation side of components in the main
VMIS installer.
"""
from tempfile import NamedTemporaryFile

from .installer import Installer, IType

import vmis.core.files as files
import vmis.core.questions as questions

from vmis import vmisdebug
from vmis.db import db
from vmis import ui
from vmis.core.errors import DoesNotExistError
from vmis.core.files import File, Link, INITDIR, INITSCRIPTDIR
from vmis.util.log import getLog
from vmis.util.path import path
from vmis.util import CompilePython
from vmis.core.questions import LEVELS

import vmis.util.shell as shell

log = getLog('vmis.core.installer')

class LocalInstallerOps(Installer):
    """ Implementation of the Installer methods for local access"""

    def __init__(self, installer):
       self._installer = installer

       # Files is a list of mapping between one-to-many sources and one
       # destination.  Files are a list because order of installation
       # sometimes matters (e.g., with symlinks).  This means the order
       # of installation between a mapping of sources and destinations
       # is not guaranteed.
       self._files = []
       self._permissions = []
       self._filetypes = []
       self._questions = []
       self._banner = None
       self._iconImagePaths = []
       self._headerImagePath = None

    def PreTransactionInstall(self, old, new, upgrade):
       """
       Called before anything else during install.

       This is where global settings like branding should be set.
       """
       pass

    def PreTransactionUninstall(self, old, new, upgrade):
       """
       Called before anything else during uninstall.
       """
       pass

    def PostTransactionInstall(self, old, new, upgrade):
       """
       Called after everything else during install.

       This function is called after the database has been committed
       for the current component.  Since no transaction is active at
       this point, external programs may modify the installer database.
       """
       pass

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
       pass

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
       pass

    def InitializeUninstall(self, old, new, upgrade):
       """
       Called for each component scheduled to be uninstalled.

       Initialize should perform quick, fail-fast checks on the system
       that would prevent the component from being uninstalled.
       """
       pass

    def PreInstall(self, old, new, upgrade):
       """
       Called before component installation commences.

       PreInstall should perform whatever tasks are necessary to put
       the system in a state where the component may be installed.

       PreInstall should rarely fail.  Any likely scenarios to cause
       failure should be checked for in Initialize instead.
       """
       pass

    def PostInstall(self, old, new, upgrade):
       """
       Called after a component is installed.

       PostInstall should configure the compoonent on the system.  Any
       changes made here should likely have a counterpart in
       PostUninstall.

       Example:  Making changes to a system configuration file.
       """
       pass

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
       pass

    def PostUninstall(self, old, new, upgrade):
       """
       Called after a component is uninstalled.

       PostUninstall should unconfigure the component on the system.
       Anything changed in PostInstall should likely have a counterpart
       here.

       Example:  Undoing changes made to system configuration file.
       """
       pass

    def GetConfig(self, key, default=None, component=None):
       if not component:
          component = self._component.name
       val = db.config.Get(component, key, default)
       # XXX: It looks like this version of pickle is unsure of how to
       # handle a unicode object of raw-unicode-escape encoding, but
       # is fine with a str object, so explicitly convert it if it's not
       # None
       # This may have an impact on future internationalization.
       if val is None:
          val = default
       else:
          val = str(val)

       return val

    def SetConfig(self, key, val):
       db.config.Set(self._component.name, key, val)

    def DelConfig(self, key):
       db.config.Remove(self._component.name, key)

    def GetManifestValue(self, key, default=None):
       """
       Pass Manifest info to component
       XXX: Fix this up so the Manifest is all I need
       """
       # First, get info from the manifest dict.
       val = self._component.manifestDict.get(key, default)

       # XXX: Put the right things into the Manifest dict.
       # XXX: And remove this bit of code.
       # If it's not there, then look on the component.
       if val == default:
          val = getattr(self._component, key, default)

       # We got an XML Element object back.  Convert it to
       # a string before returning.
       return str(val)

    def GetFileValue(self, key):
       """
       Get the value of one of our special files.
       ie: BINDIR, LIBDIR
       """
       # Create a destination for the key
       val = files.Destination(key)
       # Force expansion back to a string and return to the remote side.
       retval = str(val)
       return retval

    def RunCommand(self, *args, **kwargs):
       """ Run an arbitrary command """
       return shell.run(*args, **kwargs)

    def Log(self, logType, *args, **kwargs):
       """ Log a message """
       # Get the log type from our logging object
       try:
          localLog = getLog(self._component.name)
       except DoesNotExistError as e:
           # If the component no longer exists (PostUninstall for example)
           # use the installer's log.
           localLog = log
       ltype = getattr(localLog, logType, None)
       if not ltype:
          raise InvalidLogTypeException('Log Type %s does not exist! ' \
                                        'Check your component!' % logType)

       # Log the message
       ltype(*args, **kwargs)

    def SetBannerImage(self, banner):
       """ Set banner image for use during installation """
       self._banner = banner

    def SetIconImages(self, filePaths):
       """ Sets the icons to be used for the window """
       self._iconImagePaths = filePaths

    def SetHeaderImage(self, imagePath):
       """ Sets the header image """
       self._headerImagePath = imagePath

    def GetFileText(self, filePath, textMode = True):
       """ Extracts a file from the component and returns the contents """
       # Create a temporary file and extract the contents into it
       namedtempfile = NamedTemporaryFile()
       self._component.CopyFile(filePath, namedtempfile.name)

       # Read in the contents of that file to memory
       tempfile = path(namedtempfile.name)
       if textMode:
          filetxt = tempfile.text()
       else:
          filetxt = tempfile.bytes()

       # Close our temp file, which also deletes it
       namedtempfile.close()

       # Return the file contents
       return filetxt

    def GetFilePath(self, filePath):
       """ Extracts a file from the component and returns the temp path """
       # Create a temporary file and extract the contents into it
       namedtempfile = NamedTemporaryFile()
       self._component.CopyFile(filePath, namedtempfile.name)
       tempfile = namedtempfile.name + ".bak"
       path(namedtempfile.name).copy(tempfile)
       namedtempfile.close()

       # Return the temp file path
       return tempfile

    def SetComponent(self, component):
       self._component = component;

    def UserMessage(self, text, useWrapper=True):
       """ The GUI displays a message to the user """
       ui.instance.UserMessage(ui.MessageTypes.INFO, text, useWrapper)

    def AddQuestion(self, questType, *args, **kwargs):
       # questType and level are now always strings.  Convert them to real objects for storage
       #  in self._questions

       # Map questType to a real Question class.
       qtype = getattr(questions, questType, None)
       if not qtype:
          raise ValueError('Question Type %s does not exist! ' \
                           'Check your component!' % questType)

       # Map level in kwargs to a real level object.
       # Get the value for kwargs key: level
       leveltxt = kwargs.get('level')
       if leveltxt is None:  # Log a warning
          # XXX: Level keyword is required.  This will catch it.
          text = kwargs.get('text')
          if text is None:
             text = 'No text provided'
             log.warning('Non-Fatal Error: No level keyword provided to AddQuestion: %s,' \
                         'skipping question', text)

       # Map it to a real LEVEL and re-store it
       level = LEVELS.get(leveltxt)
       if level is None:
          raise ValueError('Level %s does not exist for '\
                          'Question %s.' % (leveltxt, leveltxt,))
       # Modify kwargs to point to the real level.
       kwargs['level'] = level

       self._questions.append(qtype(self._component.name, *args, **kwargs))

    def AddTarget(self, targetType, src, dest):
       # targetType is always a string.  Convert it to a real object
       #  for storage in self._files

       # Map targetType to a real Type class.
       ttype = getattr(files, targetType, None)
       if not ttype:
          raise ValueError('Target Type %s does not exist! ' \
                           'Check your component!' % targetType)

       self._files.append({ttype(src): dest})

    def SetPermission(self, src, perm):
       self._permissions.append({src: perm})

    def SetFileType(self, src, fileType):
       # fileType is always a string.  Convert it to a real object
       #  for storage in self._files

       # Map fileType to a real Type class.
       ftype = getattr(files, fileType, None)
       if not ftype:
          raise ValueError('File Type %s does not exist! ' \
                           'Check your component!' % targetType)
       src.fileType = ftype
       self._filetypes.append(src)

    def CompilePythonFile(self, filePath):
       """
       Byte-compiles a Python file for the current component.

       This should only be used in PostInstall for files that are
       dynamically generated and cannot be installed at install time.

       It's advisable to register this file with Register File if it
       needs to be removed by the installer during uninstall.
       """
       compiled = path(CompilePython(filePath))
       return compiled

    def RegisterFile(self, filename, mtime=None, fileType='File'):
       """
       Register a file with the installer.
       """
       # fileType is always a string.  Convert it to a real object
       #  for storage in self._files
       if not isinstance(fileType, str):
          raise TypeError('File Type %s was not provided as a string.  '
                          'Check your component!' % fileType)

       # Map fileType to a real Type class.
       ftype = getattr(files, fileType, None)
       if not ftype:
          raise ValueError('File Type %s does not exist! ' \
                           'Check your component!' % fileType)
       # We want the integer id of this file type to store in the database
       ftype = ftype.id

       # If no mtime was given, grab it now
       regfile = path(filename)
       if not mtime:
          mtime = int(regfile.mtime)

       db.files.Add(regfile, mtime, ftype, self._component.uid)

    def RegisterDirectory(self, dirname, mtime=None, fileType='File'):
       """
       Recursively register all files in a directory with the installer.
       """
       dirname = path(dirname)
       itr = dirname.walk()
       for filename in itr:
          if filename.isfile():  # Don't register directories.
             self.RegisterFile(filename, mtime, fileType)

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
       # If no INITDIR has been provided, log a warning and return.
       if not INITDIR:
           log.warning('INITDIR has not been set.  No rc?.d style dirs '
                       'to populate.')
           return

       script = INITSCRIPTDIR/name

       self._files.append({File(src): script})

       pattern = 'rc%(runlevel)d.d/%(letter)s%(priority)02d%(name)s'

       for runlevel in (2, 3, 5):
          self._files += [
             {Link(script): INITDIR/(pattern % {'runlevel': runlevel, 'letter': 'S',
                                                'priority': start, 'name': name})},
             {Link(script): INITDIR/(pattern % {'runlevel': runlevel, 'letter': 'K',
                                                'priority': stop, 'name': name})},
             ]

    def MessageIn(self, uid, str):
       """
       Should not be called on this class.  Here to be sure local and remote
       calls don't get crossed.
       """
       raise NotImplementedError
