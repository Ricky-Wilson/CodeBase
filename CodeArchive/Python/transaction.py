"""
Copyright 2007-2020 VMware, Inc.  All rights reserved. -- VMware Confidential

Manages the overall transaction of an installation.
"""

# The following must be the first import statement in this file.

from contextlib import contextmanager

import atexit
import errno
import os
import select
import signal
import sys
import tempfile
from vmis import vmisdebug, CONFDIR

from functools import partial
from tempfile import NamedTemporaryFile
from threading import Thread, Lock
import threading
from queue import Queue, Empty

from vmis import core, ui
from vmis.db import db, Load as LoadDB
from vmis.core import common
from vmis.core.errors import *
from vmis.core.component import ComponentError, FileComponent, FileSystemComponent, \
    ComponentTypes
from vmis.core import questions, install, common

from vmis.core.dependency import Resolve
from vmis.core.install import Install as InstallAction, Uninstall as UninstallAction, ChangeBonus as ChangeBonusAction

from vmis.core.component import InstalledComponent

from vmis.core.bundle import Bundle
from vmis.core.questions import REGULAR, LEVELS
from vmis.core.errors import AbortError, Error, InstallError, InstallerExit, DirectoryExistsError

from vmis.ui import MessageTypes
from vmis.util import Format, wrap
from vmis.util.path import path
from vmis.util.log import getLog

for i in ('EULA', 'CPUCheck', 'Question', 'Finish', 'Wizard', 'PromptInstall'):
   globals()[i] = getattr(ui, i)

# Default transaction options
OPTIONS = {'level': REGULAR,
           'ignoreErrors': False,
           'eulasAgreed': False,
          }

log = getLog('vmis.core.transaction')

# Global product installer component.  Used to properly brand the installer
# if there is no product being installed.  This happens when a product is
# already installed and does not need to be reinstalled, thus is never
# considered as an installable.  This is the fallback so that the GUI is
# still branded in such a case.
productComponent = None

class MainLoopQuit(Exception):
   """ Causes main loop to quit """
   pass

class MainLoop(Queue):
   """ A main loop """
   def Run(self):
      """ Process the main loop until an exception is raised """
      while True:
         try:
            # Search this file for "Documentation on txn" for a description of how
            # this works.
            self.get()()
            self.task_done()
         except MainLoopQuit:
            break

   def Quit(self):
      """ Causes the main loop to return if currently running """
      def func():
         raise MainLoopQuit

      self.put(func)

class Transaction(MainLoop):
   """
   Overall installation controller.  This should really be a state
   machine instead of trying to hack one with a list.
   """
   temp = None
   stopped = False

   def Abort(self, signal=None, frame=None):
      """ Abort the currently running action """
      log.debug('Aborting transaction')
      self.state.Abort(self)

   def Stop(self):
      """ Stop the GUI """
      if ui.TYPE == 'gtk':
         self.ui.Stop()

   def __init__(self, options):
      """
      @param options: dictionary of custom transaction options
      """
      # Queue isn't a new-style object so super doesn't work.
      MainLoop.__init__(self)

      self.count = 0            # Number of discerete steps to be executed
      self.currentCount = 0     # Number of steps executed
      self.opts = dict(OPTIONS) # Transaction options
      self.exitCode = 0         # Default exit code
      self.success = True       # Overall success
      self.backLimit = 0        # The earliest question to allow a step back to

      self.installMode = options['installMode']

      if 'level' in options:
         options['level'] = LEVELS[options['level'].upper()]

      self.opts.update(options)
      self.temp = path(tempfile.mkdtemp())

      signal.signal(signal.SIGINT, self.Abort)

      # Create the UI instance and set it.
      self.ui = Wizard(self)
      ui.instance = self.ui

      if ui.TYPE == 'gtk':
         # Now that we know we're using GTK, run initialization.
         self.ui.InitialSetup()

   def SetBackLimit(self, modifier=0):
      """
      Sets the last point in the questions the user can move back to.
      A modifier of 0 set the current question as the farthest back.

      @param modifier: + or - to the current question.
      """
      self.backLimit = self._cur + modifier

   def _brandInstaller(self, installer):
      """ Brand the installer """
      component = installer.component

      self.ui.SetPrimaryText('Welcome to the %s installer' % component.longName)

      # We use NamedTemporaryFile to create a temporary file to copy
      # the contents of the images to.  After we set the images we
      # close it which deletes the file for us.
      if installer.banner:
         bannerFile = NamedTemporaryFile()
         component.CopyFile(installer.banner, bannerFile.name)
         self.ui.SetBannerImage(bannerFile.name)
         bannerFile.close()

      if installer.headerImagePath:
         headerFile = NamedTemporaryFile()
         component.CopyFile(installer.headerImagePath, headerFile.name)
         self.ui.SetHeaderImage(headerFile.name)
         headerFile.close()

      if component.longName:
         self.ui.SetTitle(u'%s Installer' % component.longName)

      files = []

      for image in installer.iconImagePaths:
         f = NamedTemporaryFile()
         component.CopyFile(image, f.name)
         files.append(f)

      if files:
         self.ui.SetIconImages(f.name for f in files)
         [f.close() for f in files]

   def HostCPU_IsSupported(self):
      """
      Return True if the hardware has supported features to boot VM.
      Refer to #bora/lib/hostcheck/hostcheck.c
      """
      with open('/proc/cpuinfo', 'r') as cpuinfo:
         lines = cpuinfo.readlines(4096)
         for line in lines:
            if not line.strip():
               break
            if line.startswith('vendor_id\t'):
               tokens = line.split()
               vendor = tokens[len(tokens) - 1]
            elif line.startswith('cpu family\t'):
               tokens = line.split()
               family = int(tokens[len(tokens) - 1])
            elif line.startswith('model\t'):
               tokens = line.split()
               model = int(tokens[len(tokens) - 1])
         if vendor == 'GenuineIntel':
            if family != 6:
               return False
            if model < 0x25 or model in [0x26, 0x27, 0x2E, 0x35, 0x36]:
               return False
            return True
         if vendor == 'AuthenticAMD':
            if family >= 0x10 and family != 0x11:
               return True
            return False
      return False

   def Execute(self, actions = []):
      """
      Execute the transaction

      @param actions: list of actions to execute
      """
      self.state = None         # Current state object
      self._cur = 0             # Current action index
      self.actions = []         # List of actions to be run

      global productComponent

      uninstallActions = [u for u in actions if isinstance(u, install.Uninstall)] # Lame
      installActions = [i for i in actions if isinstance(i, install.Install)]     # Lame
      bonusChangeActions = [b for b in actions if isinstance(b, install.ChangeBonus)]   # Additional Lameness
      questionActions = []
      eulaActions = []

      log.debug("In Execute: installMode: %s", self.installMode)
      self.ui.EnableCancel(True)

      # Check to see if any actions are going to execute.  If there aren't any,
      # then we should adjust our message and say there is nothing to do.
      if uninstallActions or installActions or bonusChangeActions:
         self.message = '%s was successful.' % self.installMode
      else:
         self.message = 'The system is up to date.  Nothing has been modified.'

      try:
         for u in uninstallActions:
            u.Load(self.temp)  # Up to load to create the connection and set up a remote component.
            u.PreTransaction() # These just use them if needed then.
            questionActions.extend(u._installer.questions)
            wrap(u.Initialize, self.opts['ignoreErrors'], self.temp)
            self.count += u.Count()

         for i in installActions:
            i.Load(self.temp)
            i.PreTransaction()
            self.count += i.Count()

            # Only load the banner image for the component that is a
            # product.  This won't scale if a bundle includes multiple
            # products but that doesn't happen currently.
            if ui.TYPE == 'gtk' and i.component.cachedBonus:
               self._brandInstaller(i._installer)
               productComponent = None

         if productComponent:
            pca = InstallAction(productComponent, db.database)
            pca.Load(self.temp)
            pca.PreTransaction() # XXX: Can we load the GUI a different way?
            pci = pca._installer
            if ui.TYPE == 'gtk':
               self._brandInstaller(pci._installer)
               productComponent = None

         requireEulas = (os.environ.get('VMWARE_EULAS_AGREED') != 'yes' and
                         not self.opts['eulasAgreed'])

         for i in installActions:
            i.InitializeQuestions()
            questionActions.extend(i._installer.questions)

            if i.component.eula:
               key = '%s.eula' % i.component.name

               eula = questions.EULA(component=i.component.name, key=key,
                                     text=i.component.eula,
                                     componentName=i.component.longName)
               # In order to not confuse users, be sure to place the product
               # EULA, if there is one, at the front of the list.
               #
               # cachedBonus identifies a component as the main product component
               if i.component.cachedBonus:
                  eulaActions.insert(0, eula)
               else:
                  eulaActions.append(eula)

      except:
         # If we're unable to successfully initialize all the
         # components append a Finish page and bail out.
         # XXX: There needs to be much better error reporting here.
         # XXX: Right now everything just exits with no message.
         self.actions.append((Finish, None))
         self.GotoLast()
         raise

      log.debug('Unfiltered questions: %s', ', '.join([str(q) for q in questionActions]))
      questions.Filter(questionActions, self.opts['level'])
      questions.Filter(eulaActions, self.opts['level'], requireEulas)
      log.debug('Filtered questions: %s', ', '.join([str(q) for q in questionActions]))

      self.actions.extend([(Question, q) for q in questionActions])
      for eula in reversed(eulaActions):
         self.actions.insert(0, (EULA, eula))

      if not self.HostCPU_IsSupported() and installActions != []:
         cpuWarning = (CPUCheck, questions.CPUCheck('vmware-vmx'))
         self.actions.insert(0, cpuWarning)

      # Only show the prompt about installing if the question level is
      # default or above.
      if installActions and REGULAR.Applies(self.opts['level']):
         self.actions.append((PromptInstall, None))

      self.actions.append((common.Install, (uninstallActions, installActions, bonusChangeActions)))
      self.actions.append((Finish, None))


   def Finally(self):
      """ Common cleanup functionality """
      core.ABORTED = False
      self.temp and self.temp.rmtree(ignore_errors=True)

   def Show(self):
      """ Show the current state """
      self.ui.EnableBack(self._cur > self.backLimit)
      action, state = self.actions[self._cur]
      self.state = action
      self.state.Initialize(self, state)

      log.debug('Queuing show on state: %s', self.state)
      self.put(partial(self.state.Show, self, state))

   def Next(self):
      """ Go to next state """
      log.debug('Next on state: %s', self.state)
      self._cur += 1
      assert self._cur < len(self.actions)
      self.Show()

   def Back(self):
      """ Go to previous state """
      log.debug('Back on state: %s', self.state)
      self._cur -= 1
      assert self._cur >= 0

      self.Show()

   def GotoLast(self):
      """ Go to the last action """
      self._cur = len(self.actions) - 1 # Skip to last action

def ActionsFromComponents(resolveResults):
   toinstall = resolveResults["install"]
   touninstall = resolveResults["uninstall"]
   toupgrade = resolveResults["upgrade"]
   bonused = resolveResults["bonused"]

   installActions = []
   for c in toinstall:
      # toupgrade is a dict  of [old] -> new, so search toupgrade to see if we're
      # upgrading to this component.
      old = None
      for key in toupgrade.keys():
         if toupgrade[key] == c:
            old = key
      installActions.append(InstallAction(c, db.database, old=old, new=c))

   uninstallActions = []
   for c in touninstall:
      uninstallActions.append(UninstallAction(c, db.database, old=c, new=toupgrade.get(c, None)))

   # These actions will occur during install and uninstall to change the product
   # bonus on components as well as creating/deleting uninstall scripts for them.
   bonusActions = []
   for c in bonused:
      bonusActions.append(ChangeBonusAction(c, db.database, bonused[c]))

   return (installActions + uninstallActions + bonusActions)


def RunTransaction(actions, options):
   """ Run an installation with the given actions and options """
   txn = Transaction(options)

   # If we're using the GUI, we have to close the database since we're
   # going to transfer it to another thread.  sqlite3 is thread-aware
   # in that it only allows access from the thread that created it.
   if ui.TYPE == 'gtk':
      db.database.Commit()
      db.database.Close(cleanup=False)

      txn.uiThread = threading.currentThread()
      txn.installerThread = Thread(args=(txn, actions), target=RunThreadedTransaction)
      txn.installerThread.setName('InstallerThread') # Must be set for proper lock checking.
      txn.installerThread.start()

      # Give over control to GTK in this thread.  The installer continues in
      # RunThreadedTransaction
      import gi
      gi.require_version("Gtk", "3.0")
      from gi.repository import Gtk
      Gtk.main()
   else:
      RunThreadedTransaction(txn, actions)

def RunThreadedTransaction(txn, actions):
   """
   Run a transaction, but in the main installer thread.  This is the
   point of entry for this thread, or if in console mode, just a
   continuation of the only thread.
   """
   exitValue = EXIT_OK
   if ui.TYPE == 'gtk':
      # The database has been closed in what has become the main GUI thread,
      # now we need to re-open it in this new thread since sqlite3 does not
      # support multi-thread access.
      LoadDB(True, cleanup=False)
      from vmis.core.common import SetRepository
      SetRepository(db.database)

   try:
      # Documentation on txn and the event loop/actions
      # A short description of how this works, because it's complicated enough that it
      # needs documentation.
      #
      # Transaction inherits from MainLoop, which inherits from Queue.  Remember this.
      #
      # 1) txn.Execute is given a list of actions.
      #    a) It scans through these actions, running Load on each, which properly imports
      #       and starts the component code for each.  It then runs the PreTransaction
      #       code in each, and runs InitializeQuestions on all *install* actions.
      #    b) Questions are added to the actions list if needed
      #    c) A EULA is added if necessary as an action
      #    d) The install prompt is added if necessary as an action
      #    e) The install/uninstall actions are added, all under the guise of a single
      #       action: common.Install
      #
      #    self.actions itself is a list of tuples.  (class, arguments)
      #     class: A class that contains two functions:
      #         Initialize(cls, txn, arguments)
      #         Show(cls, txn, actions)
      #
      # 2) txn.Show is run.  It:
      #    a) Pulls the action, arguments pair from the current place in the action list.
      #    b) calls the Initialize function on that action, passing in txn and the arguments
      #    c) Creates a partial of action.Show(), passing in txn and the arguments and stores
      #       this *function* into txn, which is a queue if you remember.
      #
      # 3) txn.Run is now run.  It runs MainLoop.Run (Transaction inherited it)
      #    a) Pulls the first partial from the queue (See MainLoop.Run)
      #    b) Executes that function.
      #    c) It is up to that function to call txn.Next at the correct time.  GUIs do this
      #       when the Next button is checked for example.
      #       Common.install does this after it's run all the actions it was supposed to run.
      #
      # 4) tnx.Next updates the current pointer and calls txn.Show to show the next action
      #    in the action list.  (Go to step 2)
      #

      txn.Execute(actions)
      txn.Show()
      txn.Run()
   except:
      log.exception('Top level exception handler')
      # XXX: Better error reporting/handling here!
      txn.success = False

      excType, value, traceback = sys.exc_info()

      try:
         if isinstance(value, AbortError):
            message = '%s was canceled' % txn.installMode
            exitValue = EXIT_CANCELLED
         elif isinstance(value, Error):
            message = str(value)
            arr = message.split('VMIS:')
            message = arr[-1]
         else:
            message = '%s was unsuccessful.' % txn.installMode

         # If we ran out of space, inform the user.
         if isinstance(value, IOError):
            if value.errno == errno.ENOSPC:
               txn.ui.UserMessage(MessageTypes.ERROR,
                                  'Installation error: Out of disk space.  '
                                  'Attempting to roll-back installation.')
               exitValue = EXIT_OUT_OF_SPACE

         # XXX: This is terribly hacky.  Resolve the system unless it
         # is an InstallError which should only be called from an
         # Initialize and so we don't need to rollback anything.  It
         # will otherwise fail because vmware-installer is a
         # dependency but won't be available during the resolution
         # because it is not installed.
         #
         # This can be triggered by trying to uninstall Workstation
         # while a VM is running.

         # XXX: *** TESTING ***
         # XXX: Rollback happens here
         # XXX: Make sure it works correctly by introducing install
         # XXX:  errors.
         # XXX: What about uninstalls?
         # XXX: Should also supply good error reporting at this point
         # XXX:  right now it just rolls back with no message whatsoever
         # XXX:  and tells the user that installation failed.
         # XXX: Hard to debug as well ;)

         if excType is not InstallError:
            resolveResults = Resolve([], common.repository.installed, [], db.database)
            txn.Execute(ActionsFromComponents(resolveResults))
         else:
            txn.GotoLast()

         txn.message = message
         txn.Show()
         txn.Run()
      except:
         log.exception('Rollback failed')
   finally:
      txn.Stop()
      txn.Finally()
      # Make sure to close the DB before exiting.  This performs some last
      # cleanup that needs to be done.
      db.database.Close()
      # If the transaction did not succeed, exit with error, otherwise allow
      # the call stack to return.
      if exitValue != EXIT_OK:
         # We know the specific exit error value, exit with it.
         # XXX: Python 2.5 and 2.6 both suffer from a bug where the
         # return code is lost.  See http://bugs.python.org/issue6498
         # For now we have to do a hard exit to pass the return code back.
         os._exit(exitValue)
      elif not txn.success:
         # Otherwise allow the transaction object to throw an exit error or
         # to exit successfully.
         os._exit(not txn.success)

@contextmanager
def Load(components, bundlePath):
   """
   Load() is a generator function used within the context of
   a with statement. It will add to repository all the files and
   directories contained within the specified bundle and components.

   @param components: list of either file or directory components
   @param bundlePath: file path to the bundle
   """
   log.debug('Requesting component loading of %s', components)
   log.debug('Requesting bundle loading from %s', bundlePath)

   components = components or []
   close = []                   # File handles to close.
   loaded = []                  # Keep loaded components in here or
                                # they go out of scope and repository
                                # deletes them.

   try:
      for filePath in components:
         filePath = path(filePath)

         if filePath.isfile():
            fobj = open(filePath, 'rb')
            comp = FileComponent.LoadComponent(fobj)
            loaded.append(comp)
            common.repository.Add(comp)
         elif filePath.isdir():
            comp = FileSystemComponent.LoadComponent(filePath)
            loaded.append(comp)
            common.repository.Add(comp)
         else:
            raise ComponentError('%s is not a component' % filePath)

      bundle = bundlePath and open(bundlePath, 'rb')
      if bundle:
         close.append(bundle)
      bundle = bundle and Bundle.LoadBundle(bundle)
      if bundle:
         for c in bundle.components:
            common.repository.Add(c)

      yield

   finally:
      for f in close:
         f.close()

def Install(components, bundlePath, options, XXXNoLongerNeeded):
   """
   Wrapper method to perform bundle and/or component installation.

   @param components: list of either file or directory components
   @param bundlePath: file path to the bundle
   @param options: transaction options
   """
   options['installMode'] = 'Installation'
   with Load(components, bundlePath):
      global productComponent

      resolveResults = Resolve(common.repository.available, common.repository.installed, [], db.database)
      actions = ActionsFromComponents(resolveResults)

      # XXX: For now we only support artwork from bundles used for install.  This should
      # be changed so it can also be used from the uninstaller.  This means that the
      # artwork will need to be stored somewhere and if available, used when uninstalling
      # a product.

      # There will be no product installed when a product is already installed and
      # thus does not need to be reinstalled, so is never considered as an
      # installable.  In this case, search the list of available components in
      # the bundle to brand the installer properly with its product component.

      # If we are installing a product, use it for artwork, we're good.
      for comp in resolveResults["install"]:
         if comp.cachedBonus:
            productComponent = comp
            break

      # Otherwise use the bonused component in common.repository.available.  It's
      # possible that there is none, which is okay.  We will use the generic
      # unbranded GUI then since there is no branding information available at
      # that point.
      if not productComponent:
         for comp in common.repository.available:
            if comp.cachedBonus:
               productComponent = comp
               break

      # Check whether installing product is not conflicted with installed
      # products.
      if productComponent:
         conflicts_prodcuts_map = {
            'vmware-workstation' : [ 'vmware-player', 'vmware-vmrc'        ],
            'vmware-player'      : [ 'vmware-workstation', 'vmware-vmrc'   ],
            'vmware-vmrc'        : [ 'vmware-workstation', 'vmware-player' ]
         }
         product_names = {
            'vmware-workstation' : 'VMware Workstation',
            'vmware-player'      : 'VMware Player',
            'vmware-vmrc'        : 'VMware Remote Console'
         }
         uids = db.database.components.GetComponents()
         if productComponent.name in conflicts_prodcuts_map and uids:
            for uid in uids:
               if db.database.components.GetType(uid) == ComponentTypes.PRODUCT:
                  if (db.database.components.GetName(uid) in
                      conflicts_prodcuts_map[productComponent.name]):
                     # Conflicts detected, raise exception.
                     raise ProductsConflictError(
                        '%s detected; unable to proceed with %s installation.'
                        % (product_names[db.database.components.GetName(uid)],
                           product_names[productComponent.name]))

         if (os.environ.get('VMWARE_VMISVERSION_INSTALLED', None) and
             os.environ.get('VMWARE_VMISVERSION_INSTALLING', None)):
            # Possile same product, check whether python is compatible or not.
            vmisver_installed = os.environ['VMWARE_VMISVERSION_INSTALLED']
            vmisver_installing = os.environ['VMWARE_VMISVERSION_INSTALLING']
            if (int(vmisver_installing[0]) == 2 and
                int(vmisver_installed[0]) > int(vmisver_installing[0])):
               # Try to use python2 installer to upgrade python3 installer.
               # It will be failed, so abort the installation.
               raise DowngradeError(
                  'You have a new incompatible version of %s installed.\n'
                  'Please uninstall it before installing an older version.' %
                  product_names[productComponent.name])

      # PR: 469053 - For CDS
      # If we've specifically set out to install only a component and
      # it results in no actions, return an error.
      if components and not bundlePath and not actions:
         ui.ShowMessage(MessageTypes.ERROR,
                            'The specified component was either already installed'
                            ' or not accepted by any installed product.')
         os._exit(EXIT_NO_COMPONENT_INSTALLED)

      RunTransaction(actions, options)

def Extract(components, bundlePath, extractPath):
   """
   Wrapper method to perform bundle extraction.

   @param components: list of either file or directory components
   @param bundlePath: file path to the bundle
   @param extractPath: file path to write extract contents to
   """
   with Load(components, bundlePath):
      ExtractComponents(common.repository.available, extractPath)

def ExtractComponents(components, extractDir):
   """
   Actual workhorse for bundle extraction. Will take the provided list
   of components and extract them to the specified directory.

   @param components: list of either file or directory components
   @param extractDir: directory to extract components to (if it exists,
                      the directory will be deleted and recreated)
   """
   # The caller has asked to simply extract all the files in each
   # of the components. No exceptions are caught within this method,
   # so if any are raised, they will bubble up the call stack.

   # First, validate the supplied path. If something exists at the
   # specified path location, error out.
   extractDir = path(extractDir)
   if not extractDir.isabs():
      extractDir = path(os.getcwd())/extractDir
   if extractDir.exists():
      raise DirectoryExistsError('Could not extract to %s.  Directory'
                                 ' already exists.' % extractDir)

   for c in components:
      # c.fileset contains the FileEntry objects that we wish to extract.
      # The CopyFile() method will extract the files for us.
      for filePath, fileEntry in c.fileset.items():
         # Identify the absolute path for the file.
         filePath = extractDir/c.name/filePath

         # Create all directories to the file.
         filePathDir = filePath.dirname()
         if not filePathDir.exists():
            filePathDir.makedirs()

         # Create the file itself.
         c.CopyFile(fileEntry, filePath)

      # Write the manifest
      manifestFile = extractDir/c.name/'manifest.xml'
      manifestFile.write_bytes(c.manifest)

def UninstallProduct(prodIDs, options):
   """
   Uninstall the product with the given product id

   @param products: list of product names
   @param options: transaction options
   """
   log.debug('Requesting uninstallation of products:')
   log.debug(prodIDs)
   options['installMode'] = 'Uninstallation'

   # Add the products to remove to the list of components to uninstall
   productsToRemove = []
   productNotFoundID = None
   for uid in prodIDs:
      ic = InstalledComponent(db.database, uid)
      if not ic.bonus:
         productNotFoundID = uid

   if productNotFoundID or not prodIDs or len(prodIDs) == 0:
      errorMsg = ''
      if productNotFoundID:
         errorMsg = '%s is not a product.\n' \
                     % db.components.GetName(productNotFoundID)
      errorMsg += 'Available products are:\n\n'
      for uid in db.components.GetComponents():
         if db.components.GetType(uid) == ComponentTypes.PRODUCT:
            errorMsg += '  %s\n' % db.components.GetName(uid)
      ui.ShowMessage(MessageTypes.ERROR, errorMsg, useWrapper=False)
      os._exit(EXIT_ERROR)

   productsToRemove.append(ic)

   resolveResults = Resolve(common.repository.available, common.repository.installed, productsToRemove, db.database)
   actions = ActionsFromComponents(resolveResults)
   RunTransaction(actions, options)

def UninstallComponent(compIDs, options):
   """
   Uninstall the components with the given component ids

   @param compIDs: The component IDs in the database
   @param options: transaction options
   """
   options['installMode'] = 'Uninstallation'
   log.debug('Requesting uninstallation of components:')
   log.debug(compIDs)

   # Removing a component is less straightforward than a product.
   # It stays in place because another component depends on it,
   # or it has a reverse dependency on another component.
   #
   # Our components need to be explicitly marked for uninstallation.
   # It will be up to the dependency system to throw errors if
   # they cannot be uninstalled because they are needed by another
   # already installed component.

   # Create the list of InstalledComponents to mark for removal
   componentsToRemove = []
   for uid in compIDs:
      ic = InstalledComponent(db.database, uid)
      componentsToRemove.append(ic)

   resolveResults = Resolve(common.repository.available, common.repository.installed,
                                                 componentsToRemove, db.database)
   actions = ActionsFromComponents(resolveResults)
   RunTransaction(actions, options)

def ResolveSystem(options):
   """ Runs an empty transaction to force a resolve """
   # @fixme: Doesn't check for missing dependencies.
   options['installMode'] = 'Resolution'
   RunTransaction(Resolve(common.repository.available, common.repository.installed, [], db.database), options)
