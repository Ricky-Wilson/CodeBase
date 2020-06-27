"""
Copyright 2007 VMware, Inc.  All rights reserved. -- VMware Confidential

Repository to lookup installed and loaded components.
"""

from weakref import WeakValueDictionary

from vmis import db, vmisdebug
from vmis.core.component import InstalledComponent

class Repository(object):
   """ Maintains a list of loaded components that are weakly
   referenced and are removed when no longer loaded elsewhere. """

   def Add(self, component):
      """ Add component to the repository """
      self._available[component.name] = component

   def _getAvailable(self):
      return list(self._available.values())


   def _getInstalled(self):
      return [InstalledComponent(self._db, uid) for uid in self._db.components.GetComponents()]

   available = property(_getAvailable) #: available components
   installed = property(_getInstalled) #: installed components

   def __init__(self, database):
      self._available = WeakValueDictionary()
      if isinstance(database, int):
         vmisdebug.FatalError('INTEGER passed in for database!')
      self._db = database
