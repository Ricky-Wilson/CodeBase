"""
Copyright 2007 VMware, Inc.  All rights reserved. -- VMware Confidential

Files.
"""

from string import Template
from vmis.util.path import path

""" Standard permissions """
DEFAULT = 0o644
BINARY  = 0o755
SETUID  = 0o4755

def ComponentOnly():
   """
   Check to see if VMIS_COMPONENT_ONLY is defined.  Return true if it is,
   false otherwise.
   """
   return 'VMIS_COMPONENT_ONLY' in globals()


# XXX: This could be handled better.
# Set up logging and import vmis if we are not in component-only mode.
# XXX: Logging may be able to be passed over to the main installer, but
#  that can come later.
if not ComponentOnly():
   import vmis
   from vmis.util.log import getLog
   log = getLog('vmis.core.files')


class PathTemplate(object):
   """
   A file path that can contain predefined variables that are lazily
   expanded when a string representation is requested.
   """
   MAX_DEPTH = 5

   def __new__(cls, dest, *args, **kwargs):
      """ Custom __new__ to gobble up extra arguments that are used by subclasses """
      return super(PathTemplate, cls).__new__(cls)

   def __init__(self, dest, *args, **kwargs):
      if isinstance(dest, PathTemplate):
         self.rawText = dest.rawText
      else:
         self.rawText = dest

   def _expand(self):
      """
      Expand Path variables with values from the database.
      """
      # Check for the component only environment.  If we're in it,
      # then there is no need to expand, it has already been done
      # for us.  We want to keep the database out of the component side.
      if ComponentOnly():
         return self.rawText

      # Otherwise, go on as normal and import the database
      from vmis.db import database
      from vmis import INSTALLER_INTERNAL
      DEFAULTS = {
         'prefix'        : database.config.Get(INSTALLER_INTERNAL, 'prefix', '/usr'),
         'confdir'       : database.config.Get(INSTALLER_INTERNAL, 'confdir', vmis.CONFDIR), # VMware's etc database..configuration directory
         'sysconfdir'    : database.config.Get(INSTALLER_INTERNAL, 'sysconfdir', '/etc'),
         'bindir'        : database.config.Get(INSTALLER_INTERNAL, 'bindir', '${prefix}/bin'),
         'sbindir'       : database.config.Get(INSTALLER_INTERNAL, 'sbindir', '${prefix}/sbin'),
         'libdir'        : database.config.Get(INSTALLER_INTERNAL, 'libdir', '${prefix}/lib'),
         'datadir'       : database.config.Get(INSTALLER_INTERNAL, 'datadir', '/usr/share'),
         'mandir'        : database.config.Get(INSTALLER_INTERNAL, 'mandir', '${prefix}/share/man'),
         'includedir'    : database.config.Get(INSTALLER_INTERNAL, 'includedir', '${prefix}/include'),
         'initdir'       : database.config.Get(INSTALLER_INTERNAL, 'initdir', ''),
         'initscriptdir' : database.config.Get(INSTALLER_INTERNAL, 'initscriptdir', ''),
      }

      expanded = Template(self.rawText)

      # Expand path up to MAX_DEPTH times
      #
      # @todo: This is pretty lame and the lazy expansion makes it
      # even worse.  Profile it.
      for i in range(self.MAX_DEPTH - 1):
         expanded = Template(expanded.substitute(DEFAULTS))

      # `substitute` will raise an error if we didn't expand enough times
      return expanded.substitute()

   def __getattr__(self, attr):
      """
      For attributes that don't exist in this class, pass them through
      to path.
      """
      func = getattr(path, attr, None)

      if func and callable(func):
         return lambda *args, **kwargs: func(path(self._expand()), *args, **kwargs)
      elif func:
         return getattr(path(self._expand()), attr)
      else:
         raise AttributeError('type object %s has no attribute %s' % (self.__name__, attr))

   def __len__(self):
      return len(self._expand())

   def __getitem__(self, i):
      return self._expand()[i]

   def __unicode__(self):
      return self._expand()

   def __str__(self):
      return self._expand()

   def __repr__(self):
      return repr(self._expand())

   def __eq__(self, other):
      return self._expand() == other

   def __cmp__(self, other):
      return (self._expand() > other) - (self._expand() < other)

   def __hash__(self):
      return hash(self._expand())

class Source(PathTemplate):
   """ Generic component file source """
   def __new__(cls, source):
      return super(Source, cls).__new__(cls, source)

   def __init__(self, source):
      super(Source, self).__init__(dest=source)

   def IsAbsolute(self):
      """ Is absolute source path """
      return self.isabs()

   def IsRelative(self):
      """ Is component-relative source path """
      return not self.IsAbsolute()

   def Install(self, component, dest, precopy=None):
      """
      Installs the file(s) to the system.

      Files are copied to the system but are not registered.  For each
      file copied, the absolute file path should be yielded back.

      @param component: component to install from
      @param dest: a destination path
      @param precopy: function to call before file is copied to system
      with param of the full file path
      @returns: None (yields each installed file)
      """
      raise NotImplementedError('Install must be implemented by a concrete source')

   def Count(self, component):
      """
      Returns the number of files it will install.
      """
      return 1

def makePath(src, dest, glob=None):
   """
   Format a destination path

   @param src: component or system path
   @param dest: destination path
   @param glob: glob str if there was one, otherwise None
   @returns: absolute destination path
   """
   src = path(src)
   dest = path(dest)

   if not glob or not glob.endswith('*'):
      if glob and '*' in glob:
         return dest.joinpath(src.basename())
      else:
         return dest
   else:
      strip = glob.replace('*', '', 1)

      # Remove leading glob.  Example: foo/*
      if strip.endswith('/'):
         src = src.replace(strip, '', 1)

      # Otherwise, maintain lead because it's part of the path.
      # Example: foo*
      return dest.joinpath(src)

class File(Source):
   """
   Component or system file source

   A regular file is one whose changes are never considered when
   installing, uninstalling, or overwriting it.  If a regular file
   exists on the system it is always overwritten. """
   id = 0

   def Install(self, component, dest, precopy=None):
      if self.IsRelative():
         entries = list(component.Glob(str(self)))

         if '*' in self:
            glob = self
         else:
            glob = None

         for entry in entries:
            fileDest = makePath(entry.path, dest, glob)
            precopy and precopy(fileDest)

            component.CopyFile(entry, fileDest)
            fileDest.chmod(dest.perm)
            yield fileDest
      else:
         # Resolve dest to a concrete path (convert any BINDIR or SBINDIR
         # entries to the actual path.) and copy.
         path(self).copy2(str(dest))

         yield dest

   def Count(self, component):
      if self.IsAbsolute():
         return 1
      else:
         return len(list(component.Glob(str(self))))

class ConfigFile(File):
   """ A configuration file is one whose changes are taken into
   consideration during install and uninstall.

   Install
   =======

   The file is always laid down and overwrites the file on the system
   if it exists.  Because it is a brand-new install, any configuration
   files from previous installations should have been removed anyway.

   Upgrade
   =======

   If the file exists on the system AND its timestamp has changed then
   skip.  Else copy the file to the system.

   Uninstall
   =========

   The file is always removed. """
   id = 1

class SystemFile(File):
   """ A system file is a type of file that is not always owned by a
   component.  An example of this would be the vmmouse.so driver for X
   which is sometimes installed by a distribution but for which we
   need to install our own copy.

   Install
   =======

   If $file.vmware.bak exists already, install our copy to the system
   and record the timestamp.  This is done because the original system
   file could have already been backed up to $file.vmware.bak and our
   file laid down but the transaction failed.

   Otherwise, if the file on the system exists it is moved to
   $file.vmware.bak.  Our file is then installed on the system and its
   modified timestamp is recorded.

   Upgrade
   =======

   Identical to install.

   Uninstall
   =========

   If the recorded timestamp of $file matches $file on the system,
   copy $file.vmware.bak to $file.  Otherwise, leave $file alone
   because the user or system has changed it.

   Delete $file.vmware.bak. """
   id = 2

useRelativeSymlinks = False

class Link(Source):
   """ Symbolic link """
   def __init__(self, source):
      super(Link, self).__init__(source)

      if not self.IsAbsolute():
         raise ValueError('Symbolic link source must be an absolute path')

   def Install(self, component, dest, precopy=None):
      if ComponentOnly() is False:
         log.debug('Creating symlink from %s to %s', self, dest)

      if precopy:
         precopy(dest)

      dest = path(dest) # @fixme: have to coerce it to a string type
                        # instead of Path Template or isinstance will
                        # fail

      # Use relative paths during package creation (staging) to avoid
      # creating the wrong hard-coded paths.  This is false by default
      # but set to True during component creation.
      if useRelativeSymlinks:
         dest.dirname().relpathto(self).symlink(dest)
      else:
         self.symlink(dest)
      yield dest

class Destination(PathTemplate):
   """ File destination on the system """
   def __init__(self, dest, perm=DEFAULT, fileType=File):
      if isinstance(dest, Destination):
         super(Destination, self).__init__(dest)
         self.perm=dest.perm
         self.fileType=dest.fileType
      else:
         super(Destination, self).__init__(dest)
         self.perm = perm
         self.fileType = fileType

   def __div__(self, divisor):
      ret = Destination(path(self.rawText)/divisor)
      ret.perm = self.perm
      ret.fileType = self.fileType
      return ret

   # Make the / operator work even when true division is enabled.
   __truediv__ = __div__

   def IsDirectory(self):
      """ Is absolute source path """
      return self.endswith('/')

   def IsFile(self):
      """ Is component-relative source path """
      return not self.IsDirectory()

class Permission(Destination):
   """ Custom permission """
   def __init__(self, perm=BINARY):
       self._perm = perm

   def Install(self, source, component, precopy=None):
      if ComponentOnly() is False:
         log.debug('Changing permission of %s to %d', self, self._perm)
      self.chmod(self._perm)
      yield self

# XXX: I don't like these globals sitting here, but they work for the moment.
PREFIX        = Destination('${prefix}')
CONFDIR       = Destination('${confdir}')
BINDIR        = Destination('${bindir}', perm=BINARY)
SBINDIR       = Destination('${sbindir}', perm=BINARY)
LIBDIR        = Destination('${libdir}')
DATADIR       = Destination('${datadir}')
SYSCONFDIR    = Destination('${sysconfdir}')
DOCDIR        = Destination('${datadir}/doc')
MANDIR        = Destination('${mandir}')
INCLUDEDIR    = Destination('${includedir}')
INITDIR       = Destination('${initdir}')
INITSCRIPTDIR = Destination('${initscriptdir}', perm=BINARY)
