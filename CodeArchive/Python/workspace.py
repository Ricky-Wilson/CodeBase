#!/usr/bin/env python
"""
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

"""
from __future__ import absolute_import

import time

from faraday.config.configuration import getInstanceConfiguration
CONF = getInstanceConfiguration()


class Workspace:
    """
    Handles a complete workspace (or project)
    It contains a reference to the model and the command execution
    history for all users working on the same workspace.
    It has a list with all existing workspaces just in case user wants to
    open a new one.
    """
    class_signature = "Workspace"

    def __init__(self, name, desc=None, manager=None, shared=None):
        if not shared:
            shared = CONF.getAutoShareWorkspace()
        self.name = name
        self.description = desc
        self.customer = ""
        self.start_date = int(time.time() * 1000)
        self.finish_date = int(time.time() * 1000)
        self._id = name
        self._command_history = None
        self.shared = shared
        self.hosts = {}

    def getID(self):
        return self._id

    def setID(self, id):
        self._id = id

    def getName(self):
        return self.name

    def setName(self, name):
        self.name = name

    def getDescription(self):
        return self.description

    def setDescription(self, desc):
        self.description = desc

    def getCustomer(self):
        return self.customer

    def setCustomer(self, customer):
        self.customer = customer

    def getStartDate(self):
        return self.start_date

    def setStartDate(self, start_date):
        self.start_date = start_date

    def getEndDate(self):
        return self.end_date

    def setEndDate(self, edate):
        self.end_date = edate

    def isActive(self):
        return self.name == self._workspace_manager.getActiveWorkspace().name

    def getHosts(self):
        return list(self.hosts.values())

    def setHosts(self, hosts):
        self.hosts = hosts



# I'm Py3
