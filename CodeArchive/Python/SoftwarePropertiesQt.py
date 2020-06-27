# -*- coding: utf-8 -*-
#
#  Qt 4 based frontend to software-properties
#
#  Copyright © 2009 Harald Sitter <apachelogger@ubuntu.com>
#  Copyright © 2007 Canonical Ltd.
#
#  Author: Jonathan Riddell <jriddell@ubuntu.com>
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as
#  published by the Free Software Foundation; either version 2 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
#  USA

# FIXME: why does this pass kapps around?????

from __future__ import absolute_import, print_function

import apt_pkg
import tempfile
from gettext import gettext as _
import os

import gi
gi.require_version('PackageKitGlib', '1.0')
from gi.repository import PackageKitGlib as packagekit
from gi.repository import Gio

from PyQt5 import uic
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

import softwareproperties
import softwareproperties.distro
from softwareproperties.SoftwareProperties import SoftwareProperties
import softwareproperties.SoftwareProperties
from .I18nHelper import *

from aptsources.sourceslist import SourceEntry
from .DialogEdit import DialogEdit
from .DialogAdd import DialogAdd
from .DialogMirror import DialogMirror
from .CdromProgress import CdromProgress

from UbuntuDrivers import detect
import sys
import apt
from functools import partial
import aptsources.distro
import logging

class DetectDriverThread(QThread):
  #WARNING class to run detect_drivers() in separate thread
  #so GUI won't freeze.
  def __init__(self, swprop):
    QThread.__init__(self)
    self.swprop = swprop

  def __del__(self):
    self.wait()

  def run(self):
    self.swprop.detect_drivers()

class SoftwarePropertiesQtUI(QWidget):
  def __init__(self, datadir):
      QWidget.__init__(self)
      uic.loadUi("%s/designer/main.ui" % datadir, self)

class SoftwarePropertiesQt(SoftwareProperties):
  def __init__(self, datadir=None, options=None, parent=None, file=None, attachWinID=None):
    """ Provide a Qt-based graphical user interface to configure
        the used software repositories, corresponding authentication keys
        and update automation """
    SoftwareProperties.__init__(self, options=options, datadir=datadir)

    self.options = options
    self.datadir = datadir

    global kapp
    kapp = QApplication.instance()
    kapp.setWindowIcon(QIcon.fromTheme("applications-other"))

    self.userinterface = SoftwarePropertiesQtUI(datadir)
    self.userinterface.setWindowIcon(QIcon.fromTheme("applications-other"))
    self.userinterface.button_auth_restore.setIcon(QIcon.fromTheme("edit-undo"))
    self.userinterface.button_add_auth.setIcon(QIcon.fromTheme("list-add"))
    self.userinterface.button_auth_remove.setIcon(QIcon.fromTheme("list-remove"))
    self.userinterface.button_remove.setIcon(QIcon.fromTheme("list-remove"))
    self.userinterface.button_edit.setIcon(QIcon.fromTheme("document-edit"))
    self.userinterface.button_add.setIcon(QIcon.fromTheme("list-add"))
    self.userinterface.button_add_cdrom.setIcon(QIcon.fromTheme("media-optical"))
    translate_widget(self.userinterface)
    self.userinterface.show()
    # FIXME: winid not handled
    #if attachWinID is not None:
        #KWindowSystem.setMainWindow(self.userinterface, int(attachWinID))

    # rejected() signal from Close button
    self.userinterface.buttonBox.rejected.connect(self.on_close_button)

    self.userinterface.buttonBox.button(QDialogButtonBox.Reset).setEnabled(False)

    # Put some life into the user interface:
    self.init_server_chooser()
    self.init_popcon()
    self.init_auto_update()
    self.init_release_upgrades()
    self.show_auto_update_level()
    # Setup the key list
    self.init_keys()
    self.show_keys()
    # Setup the ISV sources list
    self.init_isv_sources()
    self.show_isv_sources()
    self.show_cdrom_sources()
    # Setup and show the Additonal Drivers tab
    self.init_drivers()

    # Connect to switch-page before setting initial tab. Otherwise the
    # first switch goes unnoticed.
    self.userinterface.tabWidget.currentChanged.connect(self.tab_switched)

    self.userinterface.checkbutton_source_code.clicked.connect(self.on_checkbutton_source_code_toggled)
    self.userinterface.button_auth_restore.clicked.connect(self.on_restore_clicked)
    self.userinterface.button_add_auth.clicked.connect(self.add_key_clicked)
    self.userinterface.button_auth_remove.clicked.connect(self.remove_key_clicked)
    self.userinterface.checkbutton_popcon.toggled.connect(self.on_checkbutton_popcon_toggled)
    self.userinterface.checkbutton_auto_update.toggled.connect(self.on_auto_update_toggled)
    self.userinterface.combobox_update_interval.currentIndexChanged.connect(self.on_combobox_update_interval_changed)
    self.userinterface.button_remove.clicked.connect(self.on_remove_clicked)
    self.userinterface.button_edit.clicked.connect(self.on_edit_clicked)
    self.userinterface.button_add_cdrom.clicked.connect(self.on_button_add_cdrom_clicked)
    self.userinterface.button_add.clicked.connect(self.on_add_clicked)
    self.userinterface.treeview_sources.itemChanged.connect(self.on_isv_source_toggled)
    self.userinterface.treeview_sources.itemClicked.connect(self.on_treeview_sources_cursor_changed)
    self.userinterface.treeview_cdroms.itemChanged.connect(self.on_cdrom_source_toggled)
    self.userinterface.treeview2.itemClicked.connect(self.on_treeview_keys_cursor_changed)

    self.button_close = self.userinterface.buttonBox.button(QDialogButtonBox.Close)
    self.button_close.setIcon(QIcon.fromTheme("dialog-close"))
    self.button_revert = self.userinterface.buttonBox.button(QDialogButtonBox.Reset)
    self.button_revert.setIcon(QIcon.fromTheme("edit-undo"))
    self.button_revert.clicked.connect(self.on_button_revert_clicked)

    self.init_distro()
    self.show_distro()

    if options and options.open_tab:
      self.userinterface.tabWidget.setCurrentIndex(int(options.open_tab))

  def tab_switched(self):
    # On the additional drivers page, don't show the backend revert button.
    if self.userinterface.tabWidget.currentIndex() == 4: #vbox_drivers is 4
      self.button_revert.setVisible(False)
      if not self.detect_called:
        #WARNING detect_drivers() runs in separate thread
        #in DetectDriverThread class so GUI won't freeze
        #after finish show_drivers() has to run in main thread because it updates the GUI
        self.detect_driver_thread = DetectDriverThread(self)
        self.detect_driver_thread.finished.connect(self.show_drivers)
        self.detect_driver_thread.start()

    else:
      self.button_revert.setVisible(True)

  def init_popcon(self):
    """ If popcon is enabled show the statistics tab and an explanation
        corresponding to the used distro """
    is_helpful = self.get_popcon_participation()
    if is_helpful != None:
      text = softwareproperties.distro.get_popcon_description(self.distro)
      text = text.replace("\n", "<br />") #silly GTK mixes HTML and normal white space
      self.userinterface.label_popcon_desc.setText(text)
      self.userinterface.checkbutton_popcon.setChecked(is_helpful)
    else:
      self.userinterface.tabWidget.removeTab(5)

  def init_server_chooser(self):
    """ Set up the widgets that allow to choose an alternate download site """
    # nothing to do here, set up signal in show_distro()
    pass

  def init_release_upgrades(self):
    " setup the widgets that allow configuring the release upgrades "
    i = self.get_release_upgrades_policy()

    self.userinterface.combobox_release_upgrades.setCurrentIndex(i)
    self.userinterface.combobox_release_upgrades.currentIndexChanged.connect(self.on_combobox_release_upgrades_changed)

  def init_auto_update(self):
    """ Set up the widgets that allow to configure the update automation """
    # this maps the key (combo-box-index) to the auto-update-interval value
    # where (-1) means, no key
    self.combobox_interval_mapping = { 0 : 1,
                                       1 : 2,
                                       2 : 7,
                                       3 : 14 }

    self.userinterface.combobox_update_interval.insertItem(99, _("Daily"))
    self.userinterface.combobox_update_interval.insertItem(99, _("Every two days"))
    self.userinterface.combobox_update_interval.insertItem(99, _("Weekly"))
    self.userinterface.combobox_update_interval.insertItem(99, _("Every two weeks"))

    update_days = self.get_update_interval()

    # If a custom period is defined add a corresponding entry
    if not update_days in self.combobox_interval_mapping.values():
        if update_days > 0:
            self.userinterface.combobox_update_interval.insertItem(99, _("Every %s days") % update_days)
            self.combobox_interval_mapping[4] = update_days

    for key in self.combobox_interval_mapping:
      if self.combobox_interval_mapping[key] == update_days:
        self.userinterface.combobox_update_interval.setCurrentIndex(key)
        break

    if update_days >= 1:
      self.userinterface.checkbutton_auto_update.setChecked(True)
      self.userinterface.combobox_update_interval.setEnabled(True)
      self.userinterface.radiobutton_updates_inst_sec.setEnabled(True)
      self.userinterface.radiobutton_updates_download.setEnabled(True)
      self.userinterface.radiobutton_updates_notify.setEnabled(True)
    else:
      self.userinterface.checkbutton_auto_update.setChecked(False)
      self.userinterface.combobox_update_interval.setEnabled(False)
      self.userinterface.radiobutton_updates_inst_sec.setEnabled(False)
      self.userinterface.radiobutton_updates_download.setEnabled(False)
      self.userinterface.radiobutton_updates_notify.setEnabled(False)

    self.userinterface.radiobutton_updates_download.toggled.connect(self.set_update_automation_level)
    self.userinterface.radiobutton_updates_inst_sec.toggled.connect(self.set_update_automation_level)
    self.userinterface.radiobutton_updates_notify.toggled.connect(self.set_update_automation_level)

  def show_auto_update_level(self):
    """Represent the level of update automation in the user interface"""
    level = self.get_update_automation_level()
    if level == None:
        self.userinterface.radiobutton_updates_inst_sec.setChecked(False)
        self.userinterface.radiobutton_updates_download.setChecked(False)
        self.userinterface.radiobutton_updates_notify.setChecked(False)
    if level == softwareproperties.UPDATE_MANUAL or\
       level == softwareproperties.UPDATE_NOTIFY:
        self.userinterface.radiobutton_updates_notify.setChecked(True)
    elif level == softwareproperties.UPDATE_DOWNLOAD:
        self.userinterface.radiobutton_updates_download.setChecked(True)
    elif level == softwareproperties.UPDATE_INST_SEC:
        self.userinterface.radiobutton_updates_inst_sec.setChecked(True)

  def init_distro(self):
    text = _("Software updates")
    self.userinterface.groupBox_updates.setTitle(text)
    text = _("Ubuntu Software")
    self.userinterface.tabWidget.setTabText(0, text)

    # Setup the checkbuttons for the components
    for child in self.userinterface.vbox_dist_comps_frame.children():
        if isinstance(child, QGridLayout):
            self.vbox_dist_comps = child
        elif isinstance(child, QObject):
            print("passing")
        else:
            print("child: " + str(type(child)))
            child.hide()
            del child
    self.checkboxComps = {}
    for comp in self.distro.source_template.components:
        # TRANSLATORS: Label for the components in the Internet section
        #              first %s is the description of the component
        #              second %s is the code name of the comp, eg main, universe
        label = _("%s (%s)") % (comp.get_description(), comp.name)
        checkbox = QCheckBox(label, self.userinterface.vbox_dist_comps_frame)
        checkbox.setObjectName(comp.name)
        self.checkboxComps[checkbox] = comp

        # setup the callback and show the checkbutton
        checkbox.clicked.connect(self.on_component_toggled)
        self.vbox_dist_comps.addWidget(checkbox)

    # Setup the checkbuttons for the child repos / updates
    for child in self.userinterface.vbox_updates_frame.children():
        if isinstance(child, QGridLayout):
            self.vbox_updates = child
        else:
            del child
    if len(self.distro.source_template.children) < 1:
        self.userinterface.vbox_updates_frame.hide()
    self.checkboxTemplates = {}
    for template in self.distro.source_template.children:
        # Do not show source entries in there
        if template.type == "deb-src":
            continue

        checkbox = QCheckBox(template.description,
                             self.userinterface.vbox_updates_frame)
        checkbox.setObjectName(template.name)
        self.checkboxTemplates[checkbox] = template
        # setup the callback and show the checkbutton
        checkbox.clicked.connect(self.on_checkbutton_child_toggled)
        self.vbox_updates.addWidget(checkbox)

    # If no components are enabled there will be no need for updates
    if len(self.distro.enabled_comps) < 1:
        self.userinterface.vbox_updates_frame.setEnabled(False)
    else:
        self.userinterface.vbox_updates_frame.setEnabled(True)

    self.init_mirrors()
    self.userinterface.combobox_server.activated.connect(self.on_combobox_server_changed)

  def init_mirrors(self):
    # Intiate the combobox which allows the user to specify a server for all
    # distro related sources
    seen_server_new = []
    self.mirror_urls = []
    self.userinterface.combobox_server.clear()
    for (name, uri, active) in self.distro.get_server_list():
        ##server_store.append([name, uri, False])
        self.userinterface.combobox_server.addItem(name)
        self.mirror_urls.append(uri)
        if [name, uri] in self.seen_server:
            self.seen_server.remove([name, uri])
        elif uri != None:
            seen_server_new.append([name, uri])
        if active == True:
            self.active_server = self.userinterface.combobox_server.count() - 1
            self.userinterface.combobox_server.setCurrentIndex(self.userinterface.combobox_server.count() - 1)
    for [name, uri] in self.seen_server:
        self.userinterface.combobox_server.addItem(name)
        self.mirror_urls.append(uri)
    self.seen_server = seen_server_new
    # add a separator and the option to choose another mirror from the list
    ##FIXME server_store.append(["sep", None, True])
    self.userinterface.combobox_server.addItem(_("Other..."))
    self.other_mirrors_index = self.userinterface.combobox_server.count() - 1

  def show_distro(self):
    """
    Represent the distro information in the user interface
    """
    # Enable or disable the child source checkbuttons
    for child in self.userinterface.vbox_updates_frame.children():
        if isinstance(child, QCheckBox):
            template = self.checkboxTemplates[child]
            (active, inconsistent) = self.get_comp_child_state(template)
            if inconsistent:
                child.setCheckState(Qt.PartiallyChecked)
            elif active:
                child.setCheckState(Qt.Checked)
            else:
                child.setCheckState(Qt.Unchecked)

    # Enable or disable the component checkbuttons
    for child in self.userinterface.vbox_dist_comps_frame.children():
        if isinstance(child, QCheckBox):
            template = self.checkboxComps[child]
            (active, inconsistent) = self.get_comp_download_state(template)
            if inconsistent:
                child.setCheckState(Qt.PartiallyChecked)
            elif active:
                child.setCheckState(Qt.Checked)
            else:
                child.setCheckState(Qt.Unchecked)

    # If no components are enabled there will be no need for updates
    # and source code
    if len(self.distro.enabled_comps) < 1:
        self.userinterface.vbox_updates_frame.setEnabled(False)
        self.userinterface.checkbutton_source_code.setEnabled(False)
    else:
        self.userinterface.vbox_updates_frame.setEnabled(True)
        self.userinterface.checkbutton_source_code.setEnabled(True)

    # Check for source code sources
    source_code_state = self.get_source_code_state()
    if source_code_state == True:
        self.userinterface.checkbutton_source_code.setCheckState(Qt.Checked)
    elif source_code_state == None:
        self.userinterface.checkbutton_source_code.setCheckState(Qt.PartiallyChecked)
    else:
        self.userinterface.checkbutton_source_code.setCheckState(Qt.Unchecked)

    # Will show a short explanation if no CDROMs are used
    if len(self.get_cdrom_sources()) == 0:
        self.userinterface.treeview_cdroms.hide()
        self.userinterface.textview_no_cd.show()
        self.userinterface.groupBox_cdrom.hide()
    else:
        self.userinterface.treeview_cdroms.show()
        self.userinterface.textview_no_cd.hide()
        self.userinterface.groupBox_cdrom.show()

    # Output a lot of debug stuff
    if self.options.debug == True or self.options.massive_debug == True:
        print("ENABLED COMPS: %s" % self.distro.enabled_comps)
        print("INTERNET COMPS: %s" % self.distro.download_comps)
        print("MAIN SOURCES")
        for source in self.distro.main_sources:
            self.print_source_entry(source)
        print("CHILD SOURCES")
        for source in self.distro.child_sources:
            self.print_source_entry(source)
        print("CDROM SOURCES")
        for source in self.distro.cdrom_sources:
            self.print_source_entry(source)
        print("SOURCE CODE SOURCES")
        for source in self.distro.source_code_sources:
            self.print_source_entry(source)
        print("DISABLED SOURCES")
        for source in self.distro.disabled_sources:
            self.print_source_entry(source)
        print("ISV")
        for source in self.sourceslist_visible:
            self.print_source_entry(source)

  def set_update_automation_level(self, selected):
    """Call the backend to set the update automation level to the given
       value"""
    if self.userinterface.radiobutton_updates_download.isChecked():
        SoftwareProperties.set_update_automation_level(self, softwareproperties.UPDATE_DOWNLOAD)
    elif self.userinterface.radiobutton_updates_inst_sec.isChecked():
        SoftwareProperties.set_update_automation_level(self, softwareproperties.UPDATE_INST_SEC)
    elif self.userinterface.radiobutton_updates_notify.isChecked():
        SoftwareProperties.set_update_automation_level(self, softwareproperties.UPDATE_NOTIFY)
    self.set_modified_config()

  def on_combobox_release_upgrades_changed(self, combobox):
    """ set the release upgrades policy """
    i = self.userinterface.combobox_release_upgrades.currentIndex()

    self.set_release_upgrades_policy(i)

  def on_combobox_server_changed(self, combobox):
    """
    Replace the servers used by the main and update sources with
    the selected one
    """
    combobox = self.userinterface.combobox_server
    index = combobox.currentIndex()
    if index == self.active_server:
        return
    elif index == self.other_mirrors_index:
        dialogue = DialogMirror(self.userinterface, self.datadir, self.distro, self.custom_mirrors)
        res = dialogue.run()
        if res != None:
            self.distro.change_server(res)
            self.set_modified_sourceslist()
            self.init_mirrors() # update combobox
        else:
            combobox.setCurrentIndex(self.active_server)
    else:
        uri = self.mirror_urls[index]
        if uri != None and len(self.distro.used_servers) > 0:
            self.active_server = index
            self.distro.change_server(uri)
            self.set_modified_sourceslist()
        else:
            self.distro.default_server = uri

  def on_component_toggled(self):
    """
    Sync the components of all main sources (excluding cdroms),
    child sources and source code sources
    """
    # FIXME: I find it rather questionable whether sender will work with pyqt doing weird signal handling
    tickBox = kapp.sender()
    if tickBox.checkState() == Qt.Checked:
        self.enable_component(str(tickBox.objectName()))
    elif tickBox.checkState() == Qt.Unchecked:
        self.disable_component(str(tickBox.objectName()))
    self.set_modified_sourceslist()

    # no way to set back to mixed state so turn off tristate
    tickBox.setTristate(False)

  def on_checkbutton_child_toggled(self):
    """
    Enable or disable a child repo of the distribution main repository
    """
    tickBox = kapp.sender()
    name = str(tickBox.objectName())

    if tickBox.checkState() == Qt.Checked:
        self.enable_child_source(name)
    elif tickBox.checkState() == Qt.Unchecked:
        self.disable_child_source(name)
    # no way to set back to mixed state so turn off tristate
    tickBox.setTristate(False)

  def on_checkbutton_source_code_toggled(self):
    """ Disable or enable the source code for all sources """
    if self.userinterface.checkbutton_source_code.checkState() == Qt.Checked:
        self.enable_source_code_sources()
    elif self.userinterface.checkbutton_source_code.checkState() == Qt.Unchecked:
        self.disable_source_code_sources()
    self.userinterface.checkbutton_source_code.setTristate(False)

  def on_checkbutton_popcon_toggled(self, state):
    """ The user clicked on the popcon paritipcation button """
    self.set_popcon_pariticipation(state)

  def init_isv_sources(self):
    """Read all valid sources into our ListStore"""
    """##FIXME
    # drag and drop support for sources.list
    self.treeview_sources.drag_dest_set(gtk.DEST_DEFAULT_ALL, \
                                        [('text/uri-list',0, 0)], \
                                        gtk.gdk.ACTION_COPY)
    self.treeview_sources.connect("drag_data_received",\
                                  self.on_sources_drag_data_received)
    """

  def on_isv_source_activate(self, treeview, path, column):
    """Open the edit dialog if a channel was double clicked"""
    ##FIXME TODO
    ##self.on_edit_clicked(treeview)

  def on_treeview_sources_cursor_changed(self, item, column):
    """set the sensitiveness of the edit and remove button
       corresponding to the selected channel"""
    # allow to remove the selected channel
    self.userinterface.button_remove.setEnabled(True)
    # disable editing of cdrom sources
    index = self.userinterface.treeview_sources.indexOfTopLevelItem(item)
    source_entry = self.isv_sources[index]
    if source_entry.uri.startswith("cdrom:"):
        self.userinterface.button_edit.setEnabled(False)
    else:
        self.userinterface.button_edit.setEnabled(True)

  def on_cdrom_source_toggled(self, item):
    """Enable or disable the selected channel"""
    self.toggle_source(self.cdrom_sources, self.userinterface.treeview_cdroms, item)

  def on_isv_source_toggled(self, item):
    """Enable or disable the selected channel"""
    self.toggle_source(self.isv_sources, self.userinterface.treeview_sources, item)

  def toggle_source(self, sources, treeview, item):
    """Enable or disable the selected channel"""
    index = treeview.indexOfTopLevelItem(item)
    source_entry = sources[index]
    self.toggle_source_use(source_entry)
    item = treeview.topLevelItem(index) # old item was destroyed
    if item != 0:
      treeview.setCurrentItem(item) # reselect entry after refresh
    else:
      self.userinterface.button_remove.setEnabled(False)
      self.userinterface.button_edit.setEnabled(False)

  def init_keys(self):
    """Setup the user interface parts needed for the key handling"""
    self.userinterface.treeview2.setColumnCount(1)

  def on_treeview_keys_cursor_changed(self, item, column):
    """set the sensitiveness of the edit and remove button
       corresponding to the selected channel"""
    # allow to remove the selected channel
    self.userinterface.button_auth_remove.setEnabled(True)
    # disable editing of cdrom sources
    index = self.userinterface.treeview2.indexOfTopLevelItem(item)

  #FIXME revert automation settings too
  def on_button_revert_clicked(self):
    """Restore the source list from the startup of the dialog"""
    SoftwareProperties.revert(self)
    self.set_modified_sourceslist()
    self.show_auto_update_level()
    self.userinterface.buttonBox.button(QDialogButtonBox.Reset).setEnabled(False)
    self.modified_sourceslist = False

  def set_modified_config(self):
    """The config was changed and now needs to be saved and reloaded"""
    SoftwareProperties.set_modified_config(self)
    self.userinterface.buttonBox.button(QDialogButtonBox.Reset).setEnabled(True)

  def set_modified_sourceslist(self):
    """The sources list was changed and now needs to be saved and reloaded"""
    SoftwareProperties.set_modified_sourceslist(self)
    self.show_distro()
    self.show_isv_sources()
    self.show_cdrom_sources()
    self.userinterface.buttonBox.button(QDialogButtonBox.Reset).setEnabled(True)

  def show_isv_sources(self):
    """ Show the repositories of independent software vendors in the
        third-party software tree view """
    self.isv_sources = self.get_isv_sources()[:]
    self.show_sources(self.isv_sources, self.userinterface.treeview_sources)

    if not self.isv_sources or len(self.isv_sources) < 1:
        self.userinterface.button_remove.setEnabled(False)
        self.userinterface.button_edit.setEnabled(False)

  def show_cdrom_sources(self):
    """ Show CD-ROM/DVD based repositories of the currently used distro in
        the CDROM based sources list """
    self.cdrom_sources = self.get_cdrom_sources()[:]
    self.show_sources(self.cdrom_sources, self.userinterface.treeview_cdroms)

  def show_sources(self, sources, treeview):
    # this workaround purposely replaces treeview.clear() (LP #102792)
    while treeview.topLevelItemCount() > 0:
      treeview.takeTopLevelItem(0)

    items = []
    for source in sources:
        contents = self.render_source(source)
        contents = contents.replace("<b>", "")
        contents = contents.replace("</b>", "")
        item = QTreeWidgetItem([contents])
        if not source.disabled:
            item.setCheckState(0, Qt.Checked)
        else:
            item.setCheckState(0, Qt.Unchecked)
        items.append(item)
    treeview.addTopLevelItems(items)

  def show_keys(self):
    self.userinterface.treeview2.clear()
    for key in self.apt_key.list():
      self.userinterface.treeview2.addTopLevelItem(QTreeWidgetItem([key]))

    if self.userinterface.treeview_sources.topLevelItemCount() < 1:
      self.userinterface.button_auth_remove.setEnabled(False)

  def on_combobox_update_interval_changed(self, index):
    #FIXME! move to backend
    if index != -1:
        value = self.combobox_interval_mapping[index]
        # Only write the key if it has changed
        if not value == apt_pkg.config.find_i(softwareproperties.CONF_MAP["autoupdate"]):
            apt_pkg.config.set(softwareproperties.CONF_MAP["autoupdate"], str(value))
            self.write_config()

  def on_auto_update_toggled(self):
    """Enable or disable automatic updates and modify the user interface
       accordingly"""
    if self.userinterface.checkbutton_auto_update.checkState() == Qt.Checked:
      self.userinterface.combobox_update_interval.setEnabled(True)
      self.userinterface.radiobutton_updates_inst_sec.setEnabled(True)
      self.userinterface.radiobutton_updates_download.setEnabled(True)
      self.userinterface.radiobutton_updates_notify.setEnabled(True)
      # if no frequency was specified use daily
      i = self.userinterface.combobox_update_interval.currentIndex()
      if i == -1:
          i = 0
          self.userinterface.combobox_update_interval.setCurrentIndex(i)
      value = self.combobox_interval_mapping[i]
    else:
      self.userinterface.combobox_update_interval.setEnabled(False)
      self.userinterface.radiobutton_updates_inst_sec.setEnabled(False)
      self.userinterface.radiobutton_updates_download.setEnabled(False)
      self.userinterface.radiobutton_updates_notify.setEnabled(False)
      SoftwareProperties.set_update_automation_level(self, None)
      value = 0
    self.set_update_interval(str(value))

  def on_add_clicked(self):
    """Show a dialog that allows to enter the apt line of a to be used repo"""
    dialog = DialogAdd(self.userinterface, self.sourceslist,
                       self.datadir, self.distro)
    line = dialog.run()
    if line != None:
      self.add_source_from_line(line)
      self.set_modified_sourceslist()

  def on_edit_clicked(self):
    """Show a dialog to edit an ISV source"""
    item = self.userinterface.treeview_sources.currentItem()
    if item is not None:
        index = self.userinterface.treeview_sources.indexOfTopLevelItem(item)
        dialogue = DialogEdit(self.userinterface, self.sourceslist, self.isv_sources[index], self.datadir)
        result = dialogue.run()
        if result == QDialog.Accepted:
            self.set_modified_sourceslist()
            self.show_isv_sources()

  # FIXME:outstanding from merge
  def on_isv_source_activated(self, treeview, path, column):
     """Open the edit dialog if a channel was double clicked"""
     ##FIXME TODO
     # check if the channel can be edited
     if self.button_edit.get_property("sensitive") == True:
         self.on_edit_clicked(treeview)

  def on_remove_clicked(self):
    """Remove the selected source"""
    item = self.userinterface.treeview_sources.currentItem()
    if item is not None:
        index = self.userinterface.treeview_sources.indexOfTopLevelItem(item)
        self.remove_source(self.isv_sources[index])
        self.show_isv_sources()

  def add_key_clicked(self):
    """Provide a file chooser that allows to add the gnupg of a trusted
       software vendor"""
    home = QDir.homePath()
    if "SUDO_USER" in os.environ:
        home = os.path.expanduser("~%s" % os.environ["SUDO_USER"])
    url = KUrl.fromPath(home)
    filename = KFileDialog.getOpenFileName(url, 'application/pgp-keys', self.userinterface, _("Import key"))
    if filename:
      if not self.add_key(filename):
        title = _("Error importing selected file")
        text = _("The selected file may not be a GPG key file " \
                "or it might be corrupt.")
        #KMessageBox.sorry(self.userinterface, text, title)
        QMessageBox.warning(self.userinterface, title, text)
      self.show_keys()

  def remove_key_clicked(self):
    """Remove a trusted software vendor key"""
    item = self.userinterface.treeview2.currentItem()
    if item == None:
        return
    key = item.text(0)
    if not self.remove_key(key[:16]):
      title = _("Error removing the key")
      text = _("The key you selected could not be removed. "
               "Please report this as a bug.")
      #KMessageBox.sorry(self.userinterface, text, title)
      QMessageBox.warning(self.userinterface, title, text)
    self.show_keys()

  def on_restore_clicked(self):
    """Restore the original keys"""
    self.apt_key.update()
    self.show_keys()

  def on_pktask_progress(self, progress, ptype, udata=(None,)):
    if ptype == packagekit.ProgressType.PERCENTAGE:
      perc = progress.get_property('percentage')
      self._pdialog.setValue(perc)

  def on_pktask_finish(self, source, result, udata=(None,)):
    results = None
    try:
        results = self._pktask.generic_finish(result)
    except Exception as e:
      QMessageBox.warning(self.userinterface, _("Could not refresh cache"), str(e))
    self._pdialog.hide()
    kapp.quit()

  def on_close_button(self):
    """Show a dialog that a reload of the channel information is required
       only if there is no parent defined"""
    if self.modified_sourceslist == True and self.options.no_update == False:
        messageBox = QMessageBox(self.userinterface)
        messageBox.setIcon(QMessageBox.Information)
        reloadButton = messageBox.addButton(_("Reload"), QMessageBox.AcceptRole)
        messageBox.addButton(QMessageBox.Close)
        primary = _("Your local copy of the software catalog is out of date.")
        secondary = _("A new copy will be downloaded.")
        text = "%s<br /><br /><small>%s</small>" % (primary, secondary)
        messageBox.setText(text)
        messageBox.exec_()
        if (messageBox.clickedButton() == reloadButton):
                self._pdialog = QProgressDialog("<big>{}</big>".format(_("Refreshing software cache")),
                                                "Cancel", 0, 100, self.userinterface)
                self._pdialog.setWindowTitle(_("Cache Refresh"))
                self._pdialog.setCancelButton(None)
                self._pdialog.setAutoClose(False)
                self._pdialog.setMinimumWidth(210)
                self._pdialog.setMinimumHeight(60)

                self._pktask = packagekit.Task()
                self._pdialog.show()
                self.userinterface.hide()
                try:
                    self._pktask.refresh_cache_async (False, # force
                                                  None,  # GCancellable
                                                  self.on_pktask_progress,
                                                  (None,), # user data
                                                  self.on_pktask_finish,
                                                  (None,));
                except Exception as e:
                    print("Error while requesting cache refresh: {}".format (e))
        else:
            # refresh not wanted, quit immediately
            kapp.quit()
    else:
        # no changes, no cache refresh needed.
        # we can quit.
        kapp.quit()


  def on_button_add_cdrom_clicked(self):
    '''Show a dialog that allows to add a repository located on a CDROM
       or DVD'''
    # testing
    #apt_pkg.config.set("APT::CDROM::Rename","true")

    saved_entry = apt_pkg.config.find("Dir::Etc::sourcelist")
    tmp = tempfile.NamedTemporaryFile()
    apt_pkg.config.set("Dir::Etc::sourcelist",tmp.name)
    progress = CdromProgress(self.datadir, self, kapp)
    cdrom = apt_pkg.Cdrom()
    # if nothing was found just return
    try:
      res = cdrom.add(progress)
    except SystemError as msg:
      title = _("CD Error")
      primary = _("Error scanning the CD")
      text = "%s\n\n<small>%s</small>" % (primary, msg)
      #KMessageBox.sorry(self.userinterface, text, title)
      QMessageBox.warning(self.userinterface, title, text)
      return
    finally:
      apt_pkg.config.set("Dir::Etc::sourcelist",saved_entry)
      progress.close()

    if res == False:
      return
    # read tmp file with source name (read only last line)
    line = ""
    for x in open(tmp.name):
      line = x
    if line != "":
      full_path = "%s%s" % (apt_pkg.config.find_dir("Dir::Etc"),saved_entry)
      # insert cdrom source first, so that it has precedence over network sources
      self.sourceslist.list.insert(0, SourceEntry(line,full_path))
      self.set_modified_sourceslist()

  def run(self):
    kapp.exec_()

  def on_driver_changes_progress(self, progress, ptype, data=None):
    self.button_driver_revert.setVisible(False)
    self.button_driver_apply.setVisible(False)
    self.button_driver_restart.setVisible(False)
    self.button_driver_cancel.setVisible(True)
    self.progress_bar.setVisible(True)

    self.userinterface.label_driver_action.setText("Applying changes...")
    if ptype == packagekit.ProgressType.PERCENTAGE:
        prog_value = progress.get_property('percentage')
        self.progress_bar.setValue(prog_value)

  def on_driver_changes_finish(self, source, result, installs_pending):
    results = None
    try:
      results = self.pk_task.generic_finish(result)
    except Exception as e:
      self.on_driver_changes_revert()
      QMessageBox.warning(self.userinterface, _("Error while applying changes"), str(e))

    if not installs_pending:
      self.progress_bar.setVisible(False)
      self.clear_changes()
      self.apt_cache = apt.Cache()
      self.set_driver_action_status()
      self.update_label_and_icons_from_status()
      self.button_driver_revert.setVisible(True)
      self.button_driver_apply.setVisible(True)
      self.button_driver_cancel.setVisible(False)
    #self.scrolled_window_drivers.set_sensitive(True)

  def on_driver_changes_error(self, transaction, error_code, error_details):
    self.on_driver_changes_revert()
    self.set_driver_action_status()
    self.update_label_and_icons_from_status()
    self.button_driver_revert.setVisible(True)
    self.button_driver_apply.setVisible(True)
    self.button_driver_cancel.setVisible(False)
    #self.scrolled_window_drivers.set_sensitive(True)

  def on_driver_changes_cancellable_changed(self, transaction, cancellable):
    self.button_driver_cancel.setEnabled(cancellable)

  def on_driver_changes_apply(self, button):
    self.pk_task = packagekit.Task()
    button = self.userinterface.sender()
    installs = []
    removals = []

    for pkg in self.driver_changes:
      if pkg.is_installed:
          removals.append(self.get_package_id(pkg.installed))
          # The main NVIDIA package is only a metapackage.
          # We need to collect its dependencies, so that
          # we can uninstall the driver properly.
          if 'nvidia' in pkg.shortname:
            for dep in get_dependencies(self.apt_cache, pkg.shortname, 'nvidia'):
              dep_pkg = self.apt_cache[dep]
              if dep_pkg.is_installed:
                removals.append(self.get_package_id(dep_pkg.installed))
      else:
        installs.append(self.get_package_id(pkg.candidate))

    self.cancellable = Gio.Cancellable()
    try:
      if removals:
        installs_pending = False
        if installs:
            installs_pending = True
        self.pk_task.remove_packages_async(removals,
                  False,  # allow deps
                  True,  # autoremove
                  self.cancellable,  # cancellable
                  self.on_driver_changes_progress,
                  (None, ),  # progress data
                  self.on_driver_changes_finish,  # callback ready
                  installs_pending  # callback data
         )
      if installs:
        self.pk_task.install_packages_async(installs,
              self.cancellable,  # cancellable
              self.on_driver_changes_progress,
              (None, ),  # progress data
              self.on_driver_changes_finish,  # GAsyncReadyCallback
              False  # ready data
       )
      self.button_driver_revert.setEnabled(False)
      self.button_driver_apply.setEnabled(False)
      #self.scrolled_window_drivers.set_sensitive(False)
    except Exception as e:
      print("Warning: install transaction not completed successfully: {}".format(e))

  def on_driver_changes_revert(self, button_revert=None):
    # HACK: set all the "Do not use" first; then go through the list of the
    #       actually selected drivers.
    for button in self.no_drv:
      button.setChecked(True)

    for alias in self.orig_selection:
      button = self.orig_selection[alias]
      button.setChecked(True)

    self.clear_changes()

    self.button_driver_revert.setEnabled(False)
    self.button_driver_apply.setEnabled(False)

  def on_driver_changes_cancel(self, button_cancel):
    self.transaction.cancel()
    self.clear_changes()

  def on_driver_restart_clicked(self, button_restart):
    if 'XDG_CURRENT_DESKTOP' in os.environ:
      desktop = os.environ['XDG_CURRENT_DESKTOP']
    else:
      desktop = 'Unknown'

    if (desktop == 'ubuntu:GNOME' and os.path.exists('/usr/bin/gnome-session-quit')):
      # argument presents a dialog to cancel reboot
      subprocess.call(['gnome-session-quit', '--reboot'])
    elif (desktop == 'XFCE' and
      os.path.exists('/usr/bin/xfce4-session-logout')):
      subprocess.call(['xfce4-session-logout'])
    elif (desktop == 'LXDE' and os.path.exists('/usr/bin/lubuntu-logout')):
      subprocess.call(['lubuntu-logout'])
    elif (desktop == 'LXQt' and os.path.exists('/usr/bin/lxqt-leave')):
      subprocess.call(['lxqt-leave'])

  def clear_changes(self):
    self.orig_selection = {}
    self.driver_changes = []

  def init_drivers(self):
    """Additional Drivers tab"""
    self.button_driver_revert = QPushButton("Revert")
    self.button_driver_apply = QPushButton("Apply Changes")
    self.button_driver_cancel = QPushButton("Cancel")
    self.button_driver_restart = QPushButton("Restart...")

    self.button_driver_revert.clicked.connect(self.on_driver_changes_revert)
    self.button_driver_apply.clicked.connect(self.on_driver_changes_apply)
    self.button_driver_cancel.clicked.connect(self.on_driver_changes_cancel)
    self.button_driver_restart.clicked.connect(self.on_driver_restart_clicked)

    self.button_driver_revert.setEnabled(False)
    self.button_driver_revert.setVisible(True)
    self.button_driver_apply.setEnabled(False)
    self.button_driver_apply.setVisible(True)
    self.button_driver_cancel.setVisible(False)
    self.button_driver_restart.setVisible(False)

    #self.userinterface.box_driver_action.addWidget(self.userinterface.label_driver_action)
    self.userinterface.box_driver_action.addStretch()
    self.userinterface.box_driver_action.addWidget(self.button_driver_apply)
    self.userinterface.box_driver_action.addWidget(self.button_driver_revert)
    self.userinterface.box_driver_action.addWidget(self.button_driver_restart)
    self.userinterface.box_driver_action.addWidget(self.button_driver_cancel)

    self.label_driver_detail = QLabel("Searching for available drivers...")
    self.label_driver_detail.setAlignment(Qt.AlignCenter)
    self.userinterface.box_driver_detail.addWidget(self.label_driver_detail)

    self.progress_bar = QProgressBar()

    self.userinterface.box_driver_action.addWidget(self.progress_bar)
    self.progress_bar.setVisible(False)

    self.devices = {}
    self.detect_called = False
    self.driver_changes = []
    self.orig_selection = {}
        # HACK: the case where the selection is actually "Do not use"; is a little
        #       tricky to implement because you can't check for whether a package is
        #       installed or any such thing. So let's keep a list of all the
        #       "Do not use" radios, set those active first, then iterate through
        #       orig_selection when doing a Reset.
    self.no_drv = []
    self.nonfree_drivers = 0
    self.ui_building = False

  def detect_drivers(self):
    # WARNING: This is run in a separate thread.
    self.detect_called = True
    try:
      self.apt_cache = apt.Cache()
      self.devices = detect.system_device_drivers(self.apt_cache)
    except:
      # Catch all exceptions and feed them to apport.
      #GLib.idle_add(self.label_driver_detail.set_text, _("An error occurred while searching for drivers."))
      self.label_driver_detail.setText("An error occurred while searching for drivers.")
      # For apport to catch this exception. See
      # http://bugs.python.org/issue1230540
      sys.excepthook(*sys.exc_info())
      return
  def on_driver_selection_changed(self, modalias, pkg_name=None):
    button = self.userinterface.sender()
    #print(modalias)
    #print(pkg_name)

    if self.ui_building:
      return

    pkg = None
    try:
      if pkg_name:
        pkg = self.apt_cache[pkg_name]
        # If the package depends on dkms
        # we need to install the correct linux metapackage
        # so that users get the latest headers
        if 'dkms' in pkg.candidate.record['Depends']:
          linux_meta = detect.get_linux(self.apt_cache)
          if (linux_meta and linux_meta not in self.driver_changes):
            # Install the linux metapackage
            lmp = self.apt_cache[linux_meta]
            if not lmp.is_installed:
              self.driver_changes.append(lmp)
    except KeyError:
      pass

    if button.isChecked():
      if pkg in self.driver_changes:
        self.driver_changes.remove(pkg)

      if (pkg is not None and modalias in self.orig_selection and button is not self.orig_selection[modalias]):
        self.driver_changes.append(pkg)
    else:
      if pkg in self.driver_changes:
        self.driver_changes.remove(pkg)

      # for revert; to re-activate the original radio buttons.
      if modalias not in self.orig_selection:
          self.orig_selection[modalias] = button

      if (pkg is not None and pkg not in self.driver_changes and pkg.is_installed):
          self.driver_changes.append(pkg)

    self.button_driver_revert.setEnabled(bool(self.driver_changes))
    self.button_driver_apply.setEnabled(bool(self.driver_changes))

  def gather_device_data(self, device):
    '''Get various device data used to build the GUI.

          return a tuple of (overall_status string, icon, drivers dict).
          the drivers dict is using this form:
            {"recommended/alternative": {pkg_name: {
                                                      'selected': True/False
                                                      'description':
'description'
                                                      'builtin': True/False
                                                    }
                                         }}
             "manually_installed": {"manual": {'selected': True, 'description':
description_string}}
             "no_driver": {"no_driver": {'selected': True/False, 'description':
description_string}}

             Please note that either manually_installed and no_driver are set to
None if not applicable
             (no_driver isn't present if there are builtins)
        '''

    possible_overall_status = {
            'recommended': (_("This device is using the recommended driver."),
"recommended-driver"),
            'alternative': (_("This device is using an alternative driver."),
"other-driver"),
            'manually_installed': (_("This device is using a manually-installed driver."), "other-driver"),
            'no_driver': (_("This device is not working."), "disable-device")
        }

    returned_drivers = {'recommended': {}, 'alternative': {},
'manually_installed': {}, 'no_driver': {}}
    have_builtin = False
    one_selected = False
    try:
      if device['manual_install']:
        returned_drivers['manually_installed'] = {True: {'selected': True,'description': _("Continue using a manually installed driver")}}
    except KeyError:
      pass

    for pkg_driver_name in device['drivers']:
      current_driver = device['drivers'][pkg_driver_name]

      # get general status
      driver_status = 'alternative'
      try:
        if current_driver['recommended'] and current_driver['from_distro']:
          driver_status = 'recommended'
      except KeyError:
        pass

      builtin = False
      try:
        if current_driver['builtin']:
          builtin = True
          have_builtin = True
      except KeyError:
        pass

      try:
        pkg = self.apt_cache[pkg_driver_name]
        installed = pkg.is_installed
        if pkg.candidate is not None:
          description = _("Using {} from {}").format(pkg.candidate.summary, pkg.shortname)
        else:
          description = _("Using {}").format(pkg.shortname)
      except KeyError:
        print("WARNING: a driver ({}) doesn't have any available package associated: {}".format(pkg_driver_name, current_driver))
        continue

      # gather driver description
      if current_driver['free']:
        licence = _("open source")
      else:
        licence = _("proprietary")

      if driver_status == 'recommended':
        base_string = _("{base_description} ({licence}, tested)")
      else:
        base_string = _("{base_description} ({licence})")
      description = base_string.format(base_description=description,
licence=licence)

      selected = False
      if not builtin and not returned_drivers['manually_installed']:
        selected = installed
        if installed:
          selected = True
          one_selected = True

      returned_drivers[driver_status].setdefault(pkg_driver_name, {'selected': selected,'description': description,'builtin': builtin})

    # adjust making the needed addition
    if not have_builtin:
      selected = False
      if not one_selected:
        selected = True
      returned_drivers["no_driver"] = {True: {'selected': selected, 'description': _("Do not use the device")}}
    else:
      # we have a builtin and no selection: builtin is the selected one then
      if not one_selected:
        for section in ('recommended', 'alternative'):
          for pkg_name in returned_drivers[section]:
            if returned_drivers[section][pkg_name]['builtin']:
              returned_drivers[section][pkg_name]['selected'] = True

    # compute overall status
    for section in returned_drivers:
      for keys in returned_drivers[section]:
        if returned_drivers[section][keys]['selected']:
          (overall_status, icon) = possible_overall_status[section]

    return (overall_status, icon, returned_drivers)

  def show_drivers(self):
    if not self.devices:
      # No drivers found.
      self.label_driver_detail.setText("No additional drivers available.")
      return
    else:
      self.label_driver_detail.hide()

    self.option_group = {}
    self.radio_button = {}
    self.ui_building = True
    self.dynamic_device_status = {}
    for device in sorted(self.devices.keys()):
      (overall_status, icon, drivers) = self.gather_device_data(self.devices[device])

      driver_status = QLabel()
      driver_status.setAlignment(Qt.AlignTop)
      driver_status.setAlignment(Qt.AlignHCenter)
      pixmap = QIcon.fromTheme(icon).pixmap(QSize(16, 16))
      driver_status.setPixmap(pixmap)

      device_box = QHBoxLayout()
      device_box.addWidget(driver_status)
      device_detail = QVBoxLayout()
      device_box.addLayout(device_detail,1)#1 for priority over the icon to stretch

      widget = QLabel("{}: {}".format(self.devices[device].get('vendor', _('Unknown')), self.devices[device].get('model', _('Unknown'))))
      widget.setAlignment(Qt.AlignLeft)
      device_detail.addWidget(widget)
      widget = QLabel("<small>{}</small>".format(overall_status))
      widget.setAlignment(Qt.AlignLeft)
      #widget.set_use_markup(True)
      device_detail.addWidget(widget)
      self.dynamic_device_status[device] = (driver_status, widget)

      self.option_group[device] = None
      # define the order of introspection
      for section in ('recommended', 'alternative', 'manually_installed', 'no_driver'):
        for driver in drivers[section]:
          self.radio_button = QRadioButton(drivers[section][driver]['description'])
          if self.option_group[device]:
            self.option_group[device].addButton(self.radio_button)
          else:
            self.option_group[device] = QButtonGroup()
            self.option_group[device].addButton(self.radio_button)

          device_detail.addWidget(self.radio_button)
          self.radio_button.setChecked(drivers[section][driver]['selected'])

          if section == 'no_driver':
            self.no_drv.append(self.radio_button)
          if section in ('manually_install', 'no_driver') or ('builtin' in drivers[section][driver] and drivers[section][driver]['builtin']):
            self.radio_button.toggled.connect(partial( self.on_driver_selection_changed, device))
          else:
            self.radio_button.toggled.connect(partial( self.on_driver_selection_changed, device, driver))
          if drivers['manually_installed'] and section != 'manually_installed':
            self.radio_button.setEnabled(False)

      self.userinterface.box_driver_detail.addLayout(device_box)

    self.userinterface.box_driver_detail.addStretch()
    self.ui_building = False
    #self.userinterface.box_driver_detail.show_all()
    self.set_driver_action_status()

  def update_label_and_icons_from_status(self):
    '''Update the current label and icon, computing the new device status'''

    for device in self.devices:
      (overall_status, icon, drivers) = self.gather_device_data(self.devices[device])
      (driver_status, widget) = self.dynamic_device_status[device]

      pixmap = QIcon.fromTheme(icon).pixmap(QSize(16, 16))
      driver_status.setPixmap(pixmap)
      widget.setText("<small>{}</small>".format(overall_status))

  def set_driver_action_status(self):
    # Update the label in case we end up having some kind of proprietary driver in use.
    if (os.path.exists('/var/run/reboot-required')):
      self.userinterface.label_driver_action.setText("You need to restart the computer to complete the driver changes.")
      self.button_driver_restart.setVisible(True)
      return

    self.nonfree_drivers = 0
    for device in self.devices:
      for pkg_name in self.devices[device]['drivers']:
        pkg = self.apt_cache[pkg_name]
        if not self.devices[device]['drivers'][pkg_name]['free'] and pkg.is_installed:
          self.nonfree_drivers = self.nonfree_drivers + 1

    if self.nonfree_drivers > 0:
      text = "%s proprietary driver(s) in use." % ( self.nonfree_drivers)
      self.userinterface.label_driver_action.setText(text)
    else:
      self.userinterface.label_driver_action.setText(_("No proprietary drivers are in use."))
