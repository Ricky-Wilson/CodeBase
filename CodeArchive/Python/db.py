"""
Copyright 2007-2017 VMware, Inc.  All rights reserved. -- VMware Confidential

VMware Installer Service database to handle registration of products,
components, files, and settings across all VMware products.
"""

import errno
import fcntl
import os
import sqlite3 as sqlite

from functools import wraps
from xml.etree.ElementTree import Element, SubElement

from vmis import CONFDIR, DATABASE_PATH, INSTALLER_INTERNAL
from vmis.core.errors import *
from vmis.util.log import getLog
from vmis.util.path import path

log = getLog('vmis.db.settings')

def wrapIntegrityError(func):
   """
   Raise our own IntegrityError to instead of SQLite's to maintain
   a consistent interface.
   """
   @wraps(func)
   def decorator(*args, **kwargs):
      try:
         return func(*args, **kwargs)
      except sqlite.IntegrityError as e:
         raise IntegrityError(str(e))

   return decorator

class Settings(object):
   """
   Class that manages globally shared settings.

   Scopes keys and values to components by name.
   """
   def __init__(self, db):
      self._db = db

   def Get(self, component, key, default=None):
      res = self._db.execute('SELECT value FROM settings WHERE key=? and component_name=?', (key, str(component)), log=False);
      row = res.fetchone()
      value = row and row['value']

      if value:
         return value
      else:
         return default
         # XXX: Used to: raise KeyError('Key %s does not exist' % key)
         # Is returning the default the right behavior?

   def Contains(self, component, key):
      if self.Get(component, key) is not None:
         return True

      return False

   def Set(self, component, key, val):
      self._db.execute('INSERT OR REPLACE INTO settings(key, value, component_name) VALUES(?, ?, ?)',
                       (key, str(val), str(str(component))))

   def Remove(self, component, key):
      """
      Deletes the key with the given key if it exists.

      @param key: key name
      """
      # We don't check for rows affected since we don't want to bother
      # raising a KeyError anyway.
      self._db.execute('DELETE FROM settings WHERE key=? and component_name=?', (key, str(component)))

class Database(object):
   """
   Database object.

   @todo: add migration support
   """
   SCHEMA_VERSION = 2
   SCHEMA_KEY = 'db.schemaVersion'
   # XXX: Maybe also add the version of the installer that produced this DB.

   def _lock(self, lockFile):
      """
      Acquire the installer lock if locking is enabled

      @param lockFile: path to the lock file
      """
      if not self._useLock:
         return

      self._lockFileName = path(lockFile)
      self._lockFileName.touch()
      log.debug('Created lock file: %s', self._lockFileName)

      self._lockFile = self._lockFileName.open()
      fcntl.flock(self._lockFile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

   def _unlock(self):
      """
      Release the installer lock if locking is enabled

      Note: If locking is enabled, this should only be called if the
      installer previously acquired the lock.
      """
      if not self._useLock:
         return

      fcntl.flock(self._lockFile.fileno(), fcntl.LOCK_UN)
      self._lockFile.close()
      self._lockFileName.remove(ignore_errors=True)

      # Attempt to prune the directory as the lock file is likely to
      # be the last thing to be removed in the directory.
      try:
         CONFDIR.rmdir()
      except OSError as e:
         # Ignore error if it was because the directory doesn't exist
         # or if there were still files in it.
         if e.errno not in (errno.ENOTDIR, errno.ENOTEMPTY):
            raise

   def __init__(self, dbFile, lock, cleanup=True):
      """
      Initializer

      @param dbFile: path to the database
      @param lock: True if to acquire installer lock, otherwise False
      @param cleanup: If True, and a .cleanup file is present, clear the DB.

      Note: The installer lock is completely separate from the
      database lock.  The database will still do its own internal
      locking.
      """
      self._dbFile = dbFile
      self._log_query = getLog('vmis.db.queries')
      self._useLock = lock

      # Create directory structure for lockfile and database.
      #
      # Catch OSError instead of checking exists() to prevent race
      # conditions where multiple processes may try to create the
      # directory structure and only one will win.
      self._db = None
      self.components = None
      self.config = None
      self.files = None
      try:
         dbFile.dirname().makedirs()
      except OSError:
         pass

      # Lock the database if necessary
      try:
         self._lock('%s.lck' % dbFile)
      except EnvironmentError:
         log.exception('Unable to acquire database lock')
         raise MultipleInstallersError

      try:
         # First cleanup after any previous installations that failed
         # catastrophically.
         cleanup and self._cleanup()

         # .cleanup is used as a flag to indicate that the database
         # should be deleted.  It is imperative that it is accurately
         # managed.  Otherwise, the database file can be left behind
         # and new products can come along that don't know how to
         # handle an old database.
         #
         # The process that creates the database and owns the database
         # lock is responsible for creating and managing the .cleanup
         # flag as well as checking for the .cleanup flag and invoking
         # cleanup if found.
         #
         # On success the file is removed after vmware-installer is
         # successfully installed.  Otherwise, the file will get
         # cleaned up by the next install that launches.
         if not dbFile.exists():
            # If the database file doesn't exist we're in trouble if
            # locking isn't requested.
            assert lock, "The database file does not exist and locking wasn't requested"
            (CONFDIR/'.cleanup').touch()

         log.info('Opening database file %s', dbFile)
         self._db = sqlite.connect(dbFile, timeout=0)
         self._db.row_factory = sqlite.Row # use named rows instead of indexes
         self._migrate()
         # Link the components, config, and files to the database.
         self.components = Components(self)
         self.config = Settings(self)
         self.files = Files(self)
         # This is here to catch problem cases with the database.  At one point
         # it wasn't initialized right...  Keeping in the check to catch future
         # errors because it was a pain to track down.
         if self.config._db is None:
            vmisdebug.FatalError('config._db is not set!')
      except sqlite.OperationalError:
         log.exception('Unable to open database file %s', dbFile)

         cleanup and self._cleanup()
         self._unlock()
         raise DatabaseError('Unable to open database')
      except:
         cleanup and self._cleanup()
         self._unlock()
         raise

   def Commit(self):
      """ Commit database transaction """
      if self._db:
         self._log_query.debug('Committing transaction')
         self._db.commit()

   def Rollback(self):
      if self._db:
         self._log_query.debug('Rolling back transaction')
         self._db.rollback()

   def execute(self, query, args=(), log=True):
      """
      Wrapper to sqlite.Connection.execute

      @log: True to log the query, otherwise False
      @returns: sqlite result
      """
      log and self._log_query.debug('%s %s', query, args)
      return self._db.execute(query, args)

   def executemany(self, query, args=()):
      """ Wrapper to sqlite3.Connection.executemany """
      self._log_query.debug('%s %s', query, args)
      return self._db.executemany(query, args)

   def GetSchemaVersion(self):
      """
      Lookup schema version.

      @returns: 0 if the schema is not loaded, otherwise the schema version
      """
      res = self.execute('SELECT COUNT(*) AS count FROM sqlite_master WHERE '
                             'type=? AND name=?', ('table', 'settings'))
      settingsExists = bool(res.fetchone()['count'])

      if settingsExists:
         res = self.execute('SELECT value FROM settings WHERE key=? and component_name=?',
                                   (self.SCHEMA_KEY, INSTALLER_INTERNAL))
         row = res.fetchone()
         vers = row and row['value']
         if vers:
            return int(vers)
         else:
            raise DatabaseError('settings table exists but schema version is missing')
      else:
         return 0

   def _migrate(self):
      version = self.GetSchemaVersion()

      for i in range(version + 1, self.SCHEMA_VERSION + 1):
         getattr(self, '_migrate%d' % i)()

      self.Commit()

   def _migrate1(self):
      script = """
      CREATE TABLE files(id INTEGER PRIMARY KEY,
                         path VARCHAR NOT NULL UNIQUE,
                         mtime INTEGER NOT NULL,
                         type INTEGER NOT NULL,
                         component_id INTEGER);

      CREATE TABLE components(id INTEGER PRIMARY KEY,
                              name VARCHAR NOT NULL,
                              version VARCHAR NOT NULL,
                              buildNumber INTEGER NOT NULL,
                              component_core_id INTEGER NOT NULL,
                              longName VARCHAR NOT NULL,
                              description VARCHAR,
                              type INTEGER NOT NULL);

      CREATE TABLE component_dependencies(component_id INTEGER NOT NULL,
                                          dependency VARCHAR NOT NULL);

      CREATE TABLE component_reverse_dependencies(component_id INTEGER NOT NULL,
                                                  name VARCHAR NOT NULL);

      CREATE TABLE component_conflicts(component_id INTEGER NOT NULL,
                                       conflict VARCHAR NOT NULL);
      """
      self._log_query.debug('Executing migration 1:\n%s', script)
      self._db.executescript(script)

   def _migrate2(self):
      # XXX: Bind settings to either global, or to a component.
      script = """
      CREATE TABLE settings(key VARCHAR PRIMARY KEY,
                            value VARCHAR NOT NULL,
                            component_name VARCHAR NOT NULL);
      """
      self._log_query.debug('Executing migration 2:\n%s', script)
      self._db.executescript(script)
      self._db.execute('INSERT INTO settings(key, value, component_name) VALUES(?, ?, ?)',
                       (self.SCHEMA_KEY, self.SCHEMA_VERSION, INSTALLER_INTERNAL))

   def _cleanup(self):
      """ Cleans up after the database before and after installation (with lock only) """
      # Cleanup is only done if we have the database lock.  Otherwise
      # we're probably being called reentrantly in which case we don't
      # own the creation of the database.
      if self._useLock and (CONFDIR/'.cleanup').exists():
         for i in ('database', '.cleanup', 'database-journal'):
            (CONFDIR/i).remove(ignore_errors=True)

   def _import2(self, xml):
      """
      Import version 2 of the database format

      @param xml: an ElementTree object containing the database
      """
      root = xml.getroot()
      for table in root.findall('table'):
         # Begin constructing the query
         genQuery = 'INSERT INTO %s(' % table.text
         columns = []
         columnsElt = table.find('columns')
         for columnElt in columnsElt.findall('column'):
            columns.append(columnElt.text)
            genQuery += '%s, ' % columnElt.text
         genQuery = genQuery[:-2] + ') VALUES('
         for rowElt in table.findall('row'):
            # This row should not be inserted here, as it is inserted in _migrate2
            if table.text == 'settings' and \
                  rowElt.findtext('key') == 'db.schemaVersion':
               continue
            query = genQuery
            rowVals = []
            for column in columns:
               rowVals.append(rowElt.findtext(column))
               query += '?, '
            query = query[:-2] + ')'
            self._db.execute(query, rowVals)

   def Close(self, cleanup=True):
      """
      Close database if opened

      @param cleanup: If True, and a .cleanup file is present, clear the DB.
      """
      if self._db:
         self._db.close()
         cleanup and self._cleanup()

         self._unlock()

   def DumpToXML(self):
      """
      Dump the database to XML.  This is used to get the database information
      out of an older installer by a newer version for database upgrades.
      """
      # XXX: Future enhancement: It seems like these could only be set
      # once, and then used to create the tables above in _migrate1,
      # as well as in here.  This will keep them from accidentally going
      # out of sync.  Rework this when migration code is fully implemented.
      # "select name from sqlite_master where type='table'" will give
      # a list of tables. If we were running Python 2.6, we could simply select
      # * from each table and use the keys() function to get these.  Since we're
      # in 2.5, we do it the hard way for now.  Replace this if we upgrade.
      columns = {}
      columns['files'] = ['id', 'path', 'mtime', 'type', 'component_id']
      columns['components'] = ['id', 'name', 'version', 'buildNumber',
                               'component_core_id', 'longName', 'description',
                               'type']
      columns['component_dependencies'] = ['component_id', 'dependency']
      columns['component_reverse_dependencies'] = ['component_id',
                                                   'name']
      columns['component_conflicts'] = ['component_id', 'conflict']
      columns['settings'] = ['key', 'value', 'component_name']

      root = Element('Database')
      SubElement(root, 'version').text = str(self.SCHEMA_VERSION)

      # Loop through our tables and output both the column headings
      # and the data in each of the rows.
      for t in columns.keys():
         table = SubElement(root, 'table')
         table.text = t
         fileCols = columns[t]

         cols = SubElement(table, 'columns')
         for col in fileCols:
            SubElement(cols, 'column').text = col

         cur = self.execute('SELECT * FROM %s' % t);
         rows = cur.fetchall()
         for row in rows:
            data = SubElement(table, 'row')
            for col in fileCols:
               SubElement(data, col).text = str(row[col])

      return root

   def ImportXML(self, xml):
      """
      Import XML into the database

      @param xml: an ElementTree object containing the database
      """
      root = xml.getroot()
      version = root.findtext('version')

      getattr(self, '_import%s' % version)(xml)

      self.Commit()

   def GetAttribute(self, table, attr, uid):
      """
      Generic function to look up a single attribute.

      @param table: table name
      @param attr: attribute name
      @param uid: id to lookup
      @returns: attribute value if it exists, otherwise None
      """
      cur = self.execute('SELECT %s FROM %s WHERE id=?' % (attr, table), (uid,))
      row = cur.fetchone()
      cur.close()

      if row:
         return row[attr]
      else:
         raise DoesNotExistError('Attribute %s in table %s does not exist with id %d' % (attr, table, uid))

   def SetAttribute(self, table, attr, value, uid):
      """
      Generic function to set a single attribute.

      @param table: table name
      @param attr: attribute name
      @param value: attribute value
      @param uid: id to set
      """
      self.execute('UPDATE %s SET %s=? WHERE id=?' % (table, attr), (value, uid))

class Files(object):
   """ Manages adding and removal of files from database """
   TABLE = 'files'

   def __init__(self, db):
      self._db = db
      self.GetMtime     = lambda uid: self._db.GetAttribute(self.TABLE, 'mtime', uid)
      self.GetComponent = lambda uid: self._db.GetAttribute(self.TABLE, 'component_id', uid)
      self.GetPath      = lambda uid: self._db.GetAttribute(self.TABLE, 'path', uid)
      self.GetType  = lambda uid: self._db.GetAttribute(self.TABLE, 'type', uid)
      self.SetType  = lambda uid, type: self._db.SetAttribute(self.TABLE, 'type', uid, type)

   @wrapIntegrityError
   def Add(self, path, mtime, fileType, component, replace=False):
      """
      Add file to database.

      @param path: file path
      @param mtime: modification time of the file
      @param fileType: type of file
      @param component: component id
      @param replace: if True, replace the file path with the new entry
      @returns: new file id
      """
      clause = 'OR REPLACE' if replace else ''
      statement = 'INSERT %s INTO files(path, mtime, type, component_id) ' \
                  'VALUES(?, ?, ?, ?)' % clause
      try:
         cur = self._db.execute(statement, (path, mtime, fileType, component))
         cur.close()
      except IntegrityError as e:
         log.info('Integrity error adding file %s in component %s.' % (path, component))
         raise
      return cur.lastrowid

   def FindByPath(self, filePath):
      """ Return component owning the given filePath otherwise 0 """

      cur = self._db.execute('SELECT id FROM files WHERE path=?', (filePath,))
      row = cur.fetchone()
      cur.close()

      if row:
         return row['id']
      else:
         return 0

   def FindByGlob(self, glob):
      """ Returns all files matching the given glob expression """
      cur = self._db.execute('SELECT id FROM files WHERE path GLOB ?', (glob,))
      rows = cur.fetchall()
      cur.close()

      return [row['id'] for row in rows]

   def Remove(self, uid):
      """
      Remove file

      @raises DoesNotExistError: when the file does not exist
      """
      cur = self._db.execute('DELETE FROM files WHERE id=?', (uid,))
      cur.close()

      if cur.rowcount != 1:
         raise DoesNotExistError('File with id %d does not exist' % uid)

class Components(object):
   """ Manages adding and removal of components from database """
   TABLE = 'components'

   def __init__(self, db):
      self._db = db
      self.GetName        = lambda uid: self._db.GetAttribute(self.TABLE, 'name', uid)

      self.GetVersion     = lambda uid: self._db.GetAttribute(self.TABLE, 'version', uid)
      self.GetBuildNumber = lambda uid: self._db.GetAttribute(self.TABLE, 'buildNumber', uid)
      self.SetVersion     = lambda uid, version: self._db.SetAttribute(self.TABLE, 'version', version, uid)

      self.GetType        = lambda uid: self._db.GetAttribute(self.TABLE, 'type', uid)

      self.GetLongName    = lambda uid: self._db.GetAttribute(self.TABLE, 'longName', uid)
      self.GetDescription = lambda uid: self._db.GetAttribute(self.TABLE, 'description', uid)


   # Allow coreVersion to be "-1", meaning this component is not tied to
   #  any other.  It needs to come in as a string representation of Version.
   # All versions must be passed in as something that can be cast to str.
   @wrapIntegrityError
   def Add(self, name, version, buildNumber, type, coreVersion, longName,
           description):
      """
      Add a component to the database.  All versions must be passed in as
      something that can be cast to a string.  Version objects comply.
      """

      # Check for integers here and do not allow them.
      assert(not isinstance(version, int))
      assert(not isinstance(coreVersion, int))
      # Cast incoming Versions to strings.
      version = str(version);
      coreVersion = str(coreVersion);
      # Translate coreVersion to a uid here and store THAT in the DB.
      #  If it can't be done, raise an exception.
      #
      # Look up the installer component that corresponds to this coreVersion.
      #  If it can't be found, there is no installer installed that is able
      #  to handle this component.  Raise an error.
      # vmware-installer is allowed as a special case where a component does not
      #  need to link to a core version because it is the core.
      coreID = -1;
      # If this is an installer, it has no core version, no need to look it up
      if name == 'vmware-installer':
         pass
      else:
         if coreVersion:
            log.debug('Seeking installer with version: %s', coreVersion)
            # XXX: Would be better not to hardcode vmware-installer.
            cur = self._db.execute('SELECT id FROM components WHERE name="vmware-installer" AND version=?', (coreVersion, ))
            row = cur.fetchone();
            cur.close();

            if row:
               coreID = row['id'];
            else:
               cur = self._db.execute('SELECT id, name, version FROM components WHERE name="vmware-installer"')
               rows = cur.fetchone();
               cur.close();
               raise CoreVersionDoesNotExistError('Could not find vmware-installer core version %s for: %s.' % (coreVersion, name))

      cur = self._db.execute('INSERT INTO components(name, version, buildNumber, type, '
                             'component_core_id, longName, description) VALUES(?, ?, ?, ?, ?, ?, ?)',
                             (name, version, buildNumber, type, coreID, longName,
                              description))
      cur.close()
      return cur.lastrowid

   def RemapCoreVersions(self, oldUID, newUID):
      """
      Find all components with the core version oldUID and change it to newUID.
      This is needed when an installer upgrades, changing its UID.
      """
      self._db.execute('UPDATE components SET component_core_id=? WHERE component_core_id=?',
                       (newUID, oldUID))

   def GetCoreVersion(self, uid):
      """ Return Version of the Core component used by this component. """
      # Use this UID to look up the version.
      # Don't bother with the lookup if the core UID is -1.
      #  This is a core component.  Return its own UID.
      if self.GetCoreUID(uid) == -1:
         return uid

      cur = self._db.execute('SELECT version FROM components WHERE id=?', (self.GetCoreUID(uid), ))
      # Pull the version itself from the result
      row = cur.fetchone()
      return row['version']

   def GetRootID(self):
      """ Return the id whose core id is -1 """
      cur = self._db.execute('SELECT id FROM components WHERE component_core_id=-1')
      row = cur.fetchone()
      cur.close()

      if row:
         return row['id']
      else:
         raise DoesNotExistError('Component with core id -1 does not exist')

   def GetCoreUID(self, uid):
      """ Return the core uid of an component """
      # As bug 1702685 reported, when the core uid of a component doesn't exist,
      # the product fails to uninstall. So, after getting the core id, check if it
      # really exists.
      coreUID = self._db.GetAttribute(self.TABLE, 'component_core_id', uid)
      cur = self._db.execute('SELECT id FROM components WHERE id=?', (coreUID, ))
      row = cur.fetchone();
      cur.close()

      if row:
         return coreUID
      else:
         return self.GetRootID()

   def SetType(self, uid, ctype):
      self._db.execute('UPDATE components SET type=? WHERE id=?', (ctype, uid))

   def AddDependency(self, uid, dep):
      """ Add dependency to component """
      self._db.execute('INSERT INTO component_dependencies(component_id, dependency)'
                       'VALUES(?, ?)', (uid, str(dep)))

   def AddReverseDependency(self, uid, name):
      """ Add reverse dependency to component """
      self._db.execute('INSERT INTO component_reverse_dependencies(component_id, name)'
                       'VALUES(?, ?)', (uid, str(name)))

   def AddConflict(self, uid, conf):
      """ Add conflict to component """
      self._db.execute('INSERT INTO component_conflicts(component_id, conflict)'
                       'VALUES(?, ?)', (uid, str(conf)))

   def FindByName(self, name):
      """ Returns the component id with the given name if exists, otherwise 0 """
      cur = self._db.execute('SELECT id FROM components WHERE name=?', (name,))
      row = cur.fetchone()
      cur.close()

      if row:
         return row['id']
      else:
         return 0

   def Remove(self, uid):
      """
      Remove the component.  All its files must already be deleted.

      @raises DependencyError: when files are still installed for the component
      @raises DoesNotExistError: when the component does not exist
      """
      cur = self._db.execute('SELECT COUNT(*) AS count FROM files WHERE component_id=?', (uid,))
      count = cur.fetchone()['count']
      cur.close()

      if count == 0:
         cur = self._db.execute('DELETE FROM components WHERE id=?', (uid,))
         count = cur.rowcount
         cur.close()

         self._db.execute('DELETE FROM component_dependencies WHERE component_id=?', (uid,))
         self._db.execute('DELETE FROM component_reverse_dependencies WHERE component_id=?', (uid,))
         self._db.execute('DELETE FROM component_conflicts WHERE component_id=?', (uid,))

         if count != 1:
            raise DoesNotExistError('Component %d does not exist' % uid)
      else:
         raise DependencyError('Unable to remove component %d because %d files are '
                               'still installed.' % (uid, count))

   def GetComponents(self):
      """ Returns all components. """
      cur = self._db.execute('SELECT id, name FROM components')
      rows = cur.fetchall()
      cur.close()
      return [row['id'] for row in rows]

   # XXX: Added this for debugging, not used in the rest of the code
   def GetNames(self):
      """ Returns all components. """
      cur = self._db.execute('SELECT name FROM components')
      rows = cur.fetchall()
      cur.close()
      return [row['name'] for row in rows]

   def GetDependencies(self, uid):
      """ Returns component dependencies by name. """
      cur = self._db.execute('SELECT dependency FROM component_dependencies WHERE component_id=?',
                             (uid,))
      rows = cur.fetchall()
      cur.close()
      return [row['dependency'] for row in rows]

   def GetReverseDependencies(self, uid):
      """ Returns component reverse dependencies by name. """
      cur = self._db.execute('SELECT name FROM component_reverse_dependencies WHERE component_id=?',
                             (uid,))
      rows = cur.fetchall()
      cur.close()
      return [row['name'] for row in rows]

   def GetConflicts(self, uid):
      """ Returns component conflicts by name. """
      cur = self._db.execute('SELECT conflict FROM component_conflicts WHERE component_id=?',
                             (uid,))
      rows = cur.fetchall()
      cur.close()
      return [row['conflict'] for row in rows]

   def GetFiles(self, uid):
      """ Return list of file ids associated with the component """
      cur = self._db.execute('SELECT id FROM files WHERE component_id=?',
                             (uid,))
      rows = cur.fetchall()
      cur.close()
      return [row['id'] for row in rows]

   def GetInstalledFiles(self, uid):
      """
      Returns a list of file ids for files in a component that are
      non-supporting files (ie, those in /etc/vmware).

      This is so that component installer scripts are not removed even
      if they happen to fail to execute.
      """
      cur = self._db.execute('SELECT id FROM files WHERE component_id=? AND '
                             'path NOT LIKE ?', (uid, CONFDIR/'%',))
      rows = cur.fetchall()
      cur.close()
      return [row['id'] for row in rows]

   def FindByFile(self, fuid):
      """ Return component owning the given file id, otherwise 0 """
      cur = self._db.execute('SELECT component_id FROM files WHERE id=?', (fuid,))
      row = cur.fetchone()
      cur.close()

      if row:
         return row['component_id']
      else:
         return 0

database = None

class Wrapper(object):
   """
   Since we can't import database directly, as it changes, define
   a Wrapper class and a single instance, db to cut down on the
   indirection elsewhere.  This makes usage a little nicer outside
   this file.

   ie:  from vmis.db import db
      db.files.Add(...)

          instead of:

      from vmis import db
      db.database.files.Add(...)

   """
   def __getattribute__(self, name):
      # Can't just store these in a dict...  It has to look up the
      #  object each time
      if name == 'config':
         return database.config
      elif name == 'components':
         return database.components
      elif name == 'files':
         return database.files
      elif name == 'database':
         return database
      else:
         assert(False)

db = Wrapper()

def Load(lock, dbfile=DATABASE_PATH, cleanup=True):
   global database

   database = Database(dbfile, lock, cleanup=cleanup)
