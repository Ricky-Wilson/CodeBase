"""
Copyright 2012-2019 VMware, Inc.  All rights reserved. -- VMware Confidential
"""
import shutil

def UpdateIconCache(inst, DATADIR):
   """ Updates the Gtk+ icon cache """
   icons = DATADIR/'icons/hicolor'

   # Signal icon update
   inst.RunCommand('touch', '-m', icons, ignoreErrors=True)

   # Ubuntu doesn't seem to do this by default
   # It also causes gnome-panel 2.16.x or lower to freeze,
   # but is fixed in GTK+ 2.10.13/gnome-panel 2.18.0
   # Original bug report: http://bugzilla.gnome.org/show_bug.cgi?id=426987
   # Check to make sure we're running a new enough version before doing this
   updateCache = True
   panelPath = shutil.which('gnome-panel')
   if panelPath != None and panelPath != '':
      panelres = inst.RunCommand('gnome-panel', '--version')
      match = re.search(r'\d+(\.\d+)+', panelres.stdout)
      versions = inst.LoadInclude('versions')
      if match and versions.CompareVersionString(match.group(), '2.18') < 0:
         log.Info(u'Buggy version of gnome-panel found, not updating icon cache')
         updateCache = False

   if updateCache:
      if inst.RunCommand('gtk-update-icon-cache', '--force', '--quiet', icons,
                         ignoreErrors=True).retCode != 0:
         log.Error(u'Unable to update icon cache')

def UpdateMIME(inst, DATADIR):
   """ Updates the MIME database """
   if inst.RunCommand('update-mime-database', DATADIR/'mime',
                      ignoreErrors=True).retCode != 0:
      log.Error('Unable to update MIME database')
   if inst.RunCommand('update-desktop-database', DATADIR/'applications',
                      ignoreErrors=True).retCode != 0:
      log.Error('Unable to update Desktop database')
