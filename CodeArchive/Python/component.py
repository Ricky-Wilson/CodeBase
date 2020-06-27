"""
Copyright 2007 VMware, Inc.  All rights reserved. -- VMware Confidential

Component loading and file extraction.

@todo: map dependencies after loading (and reverse deps)
"""



from xml import etree
from io import StringIO
from binascii import crc32
from gzip import GzipFile
import struct
import sys
import os
import tempfile
from fnmatch import fnmatch
from weakref import WeakValueDictionary

from vmis import db, core, vmisdebug
from vmis.core.dependency import Dependency, Conflict
from vmis.core.errors import *
from vmis.core.files import CONFDIR
from vmis.core.version import Version, LongVersion
from vmis.util.path import path
from vmis.util.log import getLog

log = getLog('vmis.core.component')

class FileEntry(object):
   """
   Represents a file that is stored as part of the fileset
   """
   def __init__(self, filePath, uncompressedSize, compressedSize, offset):
      """
      @param filePath:         relative path of stored file
      @param uncompressedSize: the uncompressed size of the file in bytes
      @param compressedSize:   the compressed size of the file in bytes
      @param offset:           the beginning of the file offset from the beginning of the data
                               section (relative from 0)
      """
      self.path             = filePath
      self.uncompressedSize = uncompressedSize
      self.compressedSize   = compressedSize
      self.offset           = offset

   def __repr__(self):
      return self.path

   @staticmethod
   def CreateFromXML(fileEntry):
      """
      Creates a FileEntry from the <file> element

      @param fileEntry: file element
      @returns:         created FileEntry
      """
      filePath         = fileEntry.attrib['path']
      offset           = int(fileEntry.attrib['offset'])
      compressedSize   = int(fileEntry.attrib['compressedSize'])
      uncompressedSize = int(fileEntry.attrib['uncompressedSize'])

      return FileEntry(filePath, uncompressedSize, compressedSize, offset)

class FileSet(dict):
   """ Mapping of # {'path': FileEntry} """
   def __iter__(self):
      return iter(self.items())

   @staticmethod
   def CreateFromXML(fileset):
      """
      Creates a FileSet from the <fileset> element

      @param fileset: fileset element
      @returns:       created FileSet
      """
      f = FileSet()
      for fileEntry in fileset.findall('file'):
         e = FileEntry.CreateFromXML(fileEntry)
         f[e.path] = e

      return f

   # XXX: showHidden files.  This should be separated into
   # component specific files that the component can access
   # and installer specific files such as the .installer
   # directory.  The installer should handle these correctly.
   # This will keep installer files out of the staging area.
   def Glob(self, pattern, showHidden=False):
      """
      Yields a FileEntry for each match in the FileSet

      @param pattern:    a shell-like pattern (see fnmatch)
      @param showHidden: return paths that begin with '.' if True
      """
      for (filePath, entry) in self.items():
         if fnmatch(filePath, pattern) and \
         (showHidden or not entry.path.startswith('.')):
            yield entry

class ComponentTypes(object):
   """ Types of components """
   PRODUCT = 0
   REGULAR = 1

class Component(object):
   """ Component class """
   def __init__(self, name, longName, version, buildNumber, description, platform,
                architecture, coreVersion, dependencies=None, conflicts=None,
                optionalDependencies = None, reverseDependencies=None, eula=None,
                fileset=None, local=None):
      self.bonus = False        # Whether or not the component gets a
                                # refcount bonus when its removal is
                                # being considered.  This is only used
                                # for product components right now
                                # when they are installed from a
                                # bundle.
      self.cachedBonus = False  # Bonus that is not saved, used for
                                # resolving dependencies and choosing
                                # how to install/uninstall components.
      self.name = name			        # Text
      self.longName = longName		        # Text
      self.version = Version(version)	        # Version
      self.longVersion = LongVersion(version,buildNumber) # LongVersion
      self.buildNumber = buildNumber	        # Text
      self.description = description	        # Text
      self.eula = eula			        # Text
      self.platform = platform		        # Text
      self.architecture = architecture	        # Text
      self.coreVersion = Version(coreVersion)	# Version

      # Set up dependencies and conflicts
      self.dependencies = dependencies or []
      self.optionalDependencies = optionalDependencies or []
      self.reverseDependencies = reverseDependencies or []
      self.conflicts = conflicts or []

      self.fileset = fileset
      self.local = local

      self.uid = None

      self.manifestDict = {}

      # Set up manifest dict available to the component.  These are values that
      # the product component files may need to access before the component is
      # installed.  Ensure that they are converted to basic types, as these will
      # be pickled and passed back to the component side.  Complex types will not
      # survive the pickling.
      self.manifestDict = dict(name         = str(self.name),
                               longName     = str(self.longName),
                               version      = str(self.version),
                               buildNumber  = str(self.buildNumber),
                               description  = str(self.description),
                               platform     = str(self.platform),
                               architecture = str(self.architecture))
      # XXX: Future enhancement.  Allow the user to provide a snippet of XML that can
      # be appended to the manifest in a simple key-value format.  Those values will
      # be loaded into this dict.

   def Glob(self, pattern, showHidden=False):
      """
      Return all files in the component matching the given pattern.

      @param pattern: a Source or glob pattern
      """
      return self.fileset.Glob(pattern, showHidden)

   def CopyFile(self, source, dest):
      """
      Copy the file to the given absolute destination path (ie, with filename).  If its
      directory or parent directories do not exist, they are created.
      XXX: No, this doesn't work right now (i.e., missing directories are
           not created.

      @bug:  this can leave empty directories behind if the file copy fails.

      @param source: FileEntry in the component or file path
      @param dest: destination to copy file to that does not already exist
      """
      def doit(self, source, dest):
         fileobj = None

         try:
            fileobj = self.GetFile(source)
            log.debug('[%s] Copying file from %s to %s', self, source, dest)

            try:
               filename = tempfile.mktemp(prefix=os.path.basename(dest) + ".",
                                          dir=os.path.dirname(dest))
               with open(filename, 'wb') as write:
                  data = " ";
                  while data != b'':
                     data = fileobj.read(10485760) # Read 10 MB at once.  Not too large to fill
                                                   # memory, good enough for efficiency.
                     # XXX: Does this not raise an interrupted system
                     # call exception (EINTR)?  Why not?
                     if core.ABORTED:
                        raise AbortError('Installation was canceled')
                     write.write(data)
                  write.flush()
                  os.fsync(write)
                  os.rename(filename, dest)
               log.debug('[%s] Copied file from %s to %s', self, source, dest)
            except Exception as e:
               log.exception('[%s] Failed to copy file from %s to %s', self, source, dest)
               dest.remove(ignore_errors=True)
               raise
         finally:
            fileobj and fileobj.close()

      if core.ABORTED:
         raise AbortError('Installation was canceled')

      doit(self, source, dest)

   def _getInstallDir(self):
      """ Return component files install directory """
      return CONFDIR.joinpath('components').joinpath(self.name).joinpath(self.version)

   installDir = property(_getInstallDir)

   def GetFile(self, file):
      """
      Returns a file-like object from the given file.  The caller must
      close this file when they are done with it.

      @param file:  file path in the component
      """
      raise NotImplementedError('GetFile must be implemented by a concrete component')

   @staticmethod
   def ParseManifest(manifest):
      """ Parse manifest from XML and return dictionary """
      tree = etree.ElementTree.fromstring(manifest)
      component = tree.find('.')

      name           = component.find('name').text
      longName       = component.find('longName').text
      version        = component.find('version').text
      buildNumber    = component.find('buildNumber').text
      coreVersion    = component.find('coreVersion').text

      # Convert versions from XML text to Version objects.
      #version = Version(version);
      #coreVersion = Version(coreVersion);

      description = None # description not required
      try:
         description  = component.find('description').text
      except ValueError:
         pass

      eula          = None      # EULA not required
      try:
         eula      = component.find('eula').text
      except ValueError:
         pass

      dependencies = []

      deps = component.findall('dependencies/dependency')
      try:
         for dep in deps:
            optional = False
            depName = dep.get('name')
            depOpt = dep.get('optional')
            if depOpt == 'true':
               optional = True
            dependencies.append(Dependency(depName, optional=optional))
      except VersionError as e:
         vmisdebug.PrintException(VersionError, e)
         raise VersionError('Error %s in component %s.' % (e, name))

      reverseDependencies = []
      revdeps = component.findall('reverseDependencies/dependency/[@name]')
      try:
         reverseDependencies.extend([Dependency(revdep.get('name')) for revdep in revdeps])
      except VersionError as e:
         vmisdebug.PrintException(VersionError, e)
         raise VersionError('Error %s in component %s.' % (e, name))

      conflicts = []
      confs = component.findall('conflicts/conflict/[@name]')
      try:
         conflicts.extend([Conflict(conf.get('name')) for conf in confs])
      except VersionError as e:
         vmisdebug.PrintException(VersionError, e)
         raise VersionError('Error %s in component %s.' % (e, name))

      platform     = component.find('platform').text
      architecture = component.find('architecture').text

      xmlFileset = component.find('fileset')
      fileset = FileSet.CreateFromXML(xmlFileset)

      local = None              # local not required
      try:
         local = component.findall('local')
      except ValueError:
         pass

      buildNumber = int(buildNumber)

      return dict(name=name, longName=longName, version=version, buildNumber=buildNumber,
                  description=description, platform=platform, architecture=architecture,
                  coreVersion=coreVersion, dependencies=dependencies, conflicts=conflicts,
                  reverseDependencies=reverseDependencies, eula=eula, fileset=fileset, local=local)

   @classmethod
   def LoadComponent(cls, manifest, source):
      """
      Deserializes a component from the given manifest file and
      attaches the source to it.

      @param manifest:  text of manifest
      @param source:    source used by the specific component type
                        (eg, ComponentFileObj for FileComponent)
      @returns:         deserialized Component
      """
      manifestDict = cls.ParseManifest(manifest)
      component = cls(**manifestDict)
      component.source = source
      component.manifest = manifest
      return component

   def SameAs(self, other):
      """
      This is like eq, but only checks name and version.
      """
      return self.name == other.name and self.version == other.version

   def __str__(self):
      # Return our string as Component.vXX
      return self.name + ' ' + self.version

   def __repr__(self):
      return '(%s) %s %s' % (self.__class__.__name__, self.name, self.version)

   def __cmp__(self, other):
      # Guard against None's
      if isinstance(other, self.__class__) and self.__eq__(other):
         return 0
      else:
         return 1

   def __eq__(self, other):
      return self.name == other.name and self.version == other.version and isinstance(other, self.__class__)

   def __hash__(self):
      return hash(self.__repr__())

class HTTPComponent(Component):
   @classmethod
   def LoadComponent(cls, source):
      # retrieve manifest
      c = super(HTTPComponent, cls).LoadComponent(manifest, source)

   def GetFile(self, file):
      """ Returns a file-like object for the given file in the component """
      pass

class FileSystemComponent(Component):
   @classmethod
   def LoadComponent(cls, source):
      """ Load the component from the given source directory """
      source = path(source)

      if not source.isdir():
         raise ComponentError('%s is not a directory' % source)

      fileobj = None
      try:
         fileobj = open(source.joinpath('manifest.xml'), 'rb')
         manifest = fileobj.read()
      except:
         fileobj and fileobj.close()
         raise

      return super(FileSystemComponent, cls).LoadComponent(manifest, source)

   def GetFile(self, file):
      """ Returns a file-like object to the given file in the component """
      if isinstance(file, FileEntry):
         entry = file.path
      elif isinstance(file, str):
         entry = file
      else:
         raise TypeError('file must be either a FileEntry or file path')

      if not entry:
         raise IOError('%s is not in the component' % file)
      else:
         return open(self.source.joinpath(entry), 'rb')

class FileComponent(Component):
   """ A specialization of a component that is self-contained within a single file """
   HEADER_FORMAT = '=IIcIIIQ'
   HEADER_SIZE   = struct.calcsize(HEADER_FORMAT)
   MAGIC_NUMBER  = 0x1350b09

   @classmethod
   def LoadComponent(cls, fileobj):
      """
      Loads the component from a file.

      @param fileobj: file object containing the component
      """
      fileobj.seek(0)
      header = fileobj.read(FileComponent.HEADER_SIZE)

      try:
         magicNumber, checksum, version, manifestOffset, manifestSize, \
         dataOffset, dataSize = struct.unpack(FileComponent.HEADER_FORMAT, header)
      except struct.error:
         raise ComponentManifestError('Unable to unpack header')

      if magicNumber != FileComponent.MAGIC_NUMBER:
         raise ComponentManifestError('Magic number of %#x does not match' % magicNumber)

      calcChecksum = crc32(header[8:len(header)]) & 0xffffffff
      if calcChecksum != checksum:
         raise ComponentManifestError('Calculated checksum %d does not match expected %d' % \
                              (calcChecksum, checksum))

      fileobj.seek(manifestOffset)
      manifest = fileobj.read(manifestSize)
      if len(manifest) != manifestSize:
         raise ComponentManifestError('Unable to read manifest')

      c = super(FileComponent, cls).LoadComponent(manifest, fileobj)
      c.dataOffset = dataOffset
      c.dataSize = dataSize

      return c

   def GetFile(self, file):
      """
      Retrieves a file from the component.

      @param file: One of either FileEntry or a file path
      @returns: file-like object
      """
      if isinstance(file, FileEntry):
         entry = file
      elif isinstance(file, str):
         entry = self.fileset.get(file)
      else:
         raise TypeError('file must be either a FileEntry or file path')

      if not entry:
         raise IOError('%s is not in the component' % file)
      else:
         start = self.dataOffset + entry.offset

         return GzipFile(fileobj=ComponentFileObj(self.source,
                                                  start,
                                                  start + entry.compressedSize - 1),
                         mode='rb')

class InstalledComponent(Component):
   """ Installed component """

   def __init__(self, database, uid):
      self._uid = uid

      # Used for dependency checking.  Changing this variable doesn't actually
      # modify the DB, unlike bonus=, which does so through _setBonus(...)
      self.cachedBonus = self._getBonus()

   def _getBonus(self):
      return db.database.components.GetType(self._uid) == ComponentTypes.PRODUCT

   def _setBonus(self, bonus):
      if bonus:
         db.database.components.SetType(self._uid, ComponentTypes.PRODUCT)
      else:
         db.database.components.SetType(self._uid, ComponentTypes.REGULAR)

   def _getDependencies(self):
      deps = getattr(self, '_temp_deps', None)
      if deps is not None:
         return deps

      # Get dependencies from the DB as strings of form: "DependencyOpTarget"
      deps = db.database.components.GetDependencies(self._uid)
      # Map them to Dependency objects
      return list(map(Dependency, deps))

   def _setDependencies(self, deps):
      self._temp_deps = deps

   def _getReverseDependencies(self):
      deps = getattr(self, '_temp_revdeps', None)
      if deps is not None:
         return deps

      # Get dependencies from the DB as strings of form: "DependencyOpTarget"
      deps = db.database.components.GetReverseDependencies(self._uid)
      # Map them to Dependency objects
      return list(map(Dependency, deps))

   def _setReverseDependencies(self, deps):
      self._temp_revdeps = deps

   def _getConflicts(self):
      conf = getattr(self, '_temp_conf', None)
      if conf is not None:
         return conf

      # Get conflicts from the DB and map them to Conflict objects
      conf = db.database.components.GetConflicts(self._uid)
      return list(map(core.dependency.Conflict, conf))
      # NOTE: dependency.py imports this file so we can not import it.
      #    Must reference the class explicitly

   def _setConflicts(self, conflicts):
      self._temp_conf = conflicts

   name = property(lambda self: db.database.components.GetName(self._uid))
   uid = property(lambda self: self._uid)
   version = property(lambda self: Version(db.database.components.GetVersion(self._uid)),
                           lambda self: db.database.components.SetVersion(self._uid))
   buildNumber = property(lambda self: db.database.components.GetBuildNumber(self._uid))
   longVersion = property(lambda self: LongVersion(db.database.components.GetVersion(self._uid), self.buildNumber))
   type = property(lambda self: db.database.components.GetType(self._uid),
                           lambda self, setType: db.database.components.SetType(self._uid, setType))
   bonus = property(_getBonus, _setBonus)
   longName = property(lambda self: db.database.components.GetLongName(self._uid))
   description = property(lambda self: db.database.components.GetDescription(self._uid))
   coreVersion  = property(lambda self: Version(db.database.components.GetCoreVersion(self._uid)))
   dependencies = property(_getDependencies, _setDependencies)
   reverseDependencies = property(_getReverseDependencies, _setReverseDependencies)
   conflicts = property(_getConflicts, _setConflicts)
   files = property(lambda self: db.database.components.GetFiles(self._uid))

class ComponentFileObj(object):
   """
   Wrapper around a file object to provide file-like access to
   arbitrary bounded locations within a single file source.

   While multiple ComponentFileObj's can share the same source,
   multiple ones cannot read at the same time.  This could probably be
   easily fixed by adding an internal lock around read().
   """

   def __init__(self, source, start, end):
      self.source = source
      self.start = start

      self.relativeEnd = end - start
      self.current = 0

   def seek(self, offset, whence=0):
      if whence == 0:
         new = offset
      elif whence == 1:
         new = self.current + offset
      elif whence == 2:
         new = self.relativeEnd + 1 + offset
      else:
         raise ValueError('Invalid whence of %d' % whence)

      if new < 0:
         raise IOError('Cannot seek to negative offset')

      self.current = new

   def tell(self):
      return self.current

   def _relativeToAbsolute(self, relative):
      return self.start + relative

   def read(self, n=-1):
      self.source.seek(self._relativeToAbsolute(self.current))
      bytesRemaining = (self.relativeEnd - self.current) + 1

      read = bytesRemaining if n < 0 else min(n, bytesRemaining)

      self.current += read

      return self.source.read(read)

