#!/usr/bin/env python
"""
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

"""
from __future__ import absolute_import

from faraday.client.managers.reports_managers import ReportManager

from faraday.config.configuration import getInstanceConfiguration
CONF = getInstanceConfiguration()


class UiFactory:
    @staticmethod
    def create(model_controller, plugin_manager, workspace_manager, plugin_controller, gui="gtk"):
        if gui == "gtk":
            from faraday.client.gui.gtk.application import GuiApp  # pylint:disable=import-outside-toplevel
        else:
            from faraday.client.gui.nogui.application import GuiApp  # pylint:disable=import-outside-toplevel

        return GuiApp(model_controller, plugin_manager, workspace_manager, plugin_controller)


class FaradayUi:
    def __init__(self, model_controller, plugin_manager,
                 workspace_manager, plugin_controller, gui="gtk"):
        self.model_controller = model_controller
        self.plugin_manager = plugin_manager
        self.workspace_manager = workspace_manager
        self.plugin_controller = plugin_controller
        self.report_manager = None

    def getModelController(self):
        return self.model_controller

    def getPluginManager(self):
        return self.plugin_manager

    def getWorkspaceManager(self):
        return self.workspace_manager

    def setSplashImage(self, ipath):
        pass

    def startSplashScreen(self):
        pass

    def stopSplashScreen(self):
        pass

    def splashMessage(self, message):
        pass

    def loadWorkspaces(self):
        pass

    def run(self, args):
        pass

    def quit(self):
        pass

    def postEvent(self, receiver, event):
        pass

    def createLoggerWidget(self):
        pass

    def openWorkspace(self, name):
        """Open a workspace by name. Returns the workspace of raises an
        exception if for some reason it couldn't.
        """
        if self.report_manager:
            self.report_manager.stop()
            self.report_manager.join()
        try:
            ws = self.getWorkspaceManager().openWorkspace(name)
            self.report_manager = ReportManager(
                10,
                name,
                self.plugin_controller
            )
            self.report_manager.start()
        except Exception as e:
            raise e
        return ws


# I'm Py3
