"""
Copyright 2008-2019 VMware, Inc.  All rights reserved. -- VMware Confidential

Module for handling answers.

TODO
====
check_is_running
check_file_exists
check_yes_no
check_answer_username
check_diskspace
"""

import os
import re
import socket

from vmis import ui
from vmis.util.log import getLog
from vmis.util.path import path
from vmis.util.shell import run
from vmis.db import db
from vmis.core.errors import ValidationError, ValidationErrorNonFatal, EULAError, EULADeclinedError
from vmis.core.errors  import IgnoreCPUCheckError, CPUCheckError
from vmis.core.errors import AbortError
from vmis.core.files import INITDIR, INITSCRIPTDIR
import vmis.util.shell as shell

LEVELS = {}

class Level(object):
   def __init__(self, level, name):
      self.level = level
      self.name = name

      LEVELS[self.name] = self

   def Applies(self, runLevel):
      """ Return True if the level applies to the current level """
      return self.level <= runLevel.level

   def __repr__(self):
      return '%s (%d)' % (self.name, self.level)

# Question levels
REQUIRED = Level(0, 'REQUIRED')
REGULAR  = Level(5, 'REGULAR')
CUSTOM   = Level(10, 'CUSTOM')

log = getLog('vmis.core.questions')

def Filter(questions, level, requireEulas=False):
   """
   Remove questions that are not to be shown at this level and have
   valid default answers.

   @param questions: list of questions (modified)
   @param level: current question level
   """
   closeProgramsFound = False # Don't allow more than one of these questions
   for q in list(questions): # Duplicate list since we have to remove from it.
      log.debug('Checking question: %s, %s, %s, %s.', q.component, q.key, q.type, q.level)
      askedKey = "%s.asked" % q.key
      db.config.Set(q.component, askedKey, "")
      # On upgrade, both the uninstall and install components will ask this
      # question.  We need to ensure that there is only a single check.
      if isinstance(q, ClosePrograms):
         if closeProgramsFound:
            questions.remove(q)
            continue
         closeProgramsFound = True

      if isinstance(q, EULA):
         if requireEulas:
            if 'deferred-gtk' in ui.TYPE:
               questions.remove(q)
               if 'ovftool' in q.component:
                  db.config.Set(q.component, 'ovftool.eula.deferred', 'yes')
               else:
                  db.config.Set(q.component, 'eula.deferred', 'yes')
         else:
            questions.remove(q)

         continue

      if q.level.Applies(level):
         db.config.Set(q.component, askedKey, 'yes')
         if db.config.Get(q.component, '%s.deferred' % q.key):
            db.config.Remove(q.component, '%s.deferred' % q.key)
      else:
         try:
            default = q.GetDefault()
            q.Validate(default)
            db.config.Set(q.component, q.key, default)

            if ui.TYPE == 'deferred-gtk' and q.deferrable and not q.existing:
               db.config.Set(q.component, '%s.deferred' % q.key, 'yes')

            log.debug('%s with level %s does not apply for %s', q, q.level, level)
            questions.remove(q)
         except (ValidationError, ValidationErrorNonFatal): # Keep in list
            if db.config.Get(q.component, '%s.deferred' % q.key):
               db.config.Remove(q.component, '%s.deferred' % q.key)

# Define our question types.  Strings rather than a set of enumerated integers
# make it easier to debug when we need to.
QUESTION_INVALID = 'QUESTION_INVALID'

QUESTION_FILE = 'QUESTION_FILE'
QUESTION_DIRECTORY = 'QUESTION_DIRECTORY'
QUESTION_YESNO = 'QUESTION_YESNO'
QUESTION_TEXTENTRY = 'QUESTION_TEXTENTRY'
QUESTION_NUMERIC = 'QUESTION_NUMERIC'
QUESTION_CLOSEPROGRAMS = 'QUESTION_CLOSEPROGRAMS'
QUESTION_SHUTDOWNPROGRAM = 'QUESTION_SHUTDOWNPROGRAM'
QUESTION_PORTENTRY = 'QUESTION_PORTENTRY'
QUESTION_DUALPORTENTRIES = 'QUESTION_DUALPORTENTRIES'

# EULA is special.  It does not need a Show* function in the GUI as it's
# handled separately.
# XXX: Maybe fix this.  EULA is fairly specialized right now.  It would be
# nice to have it as just another generic question.
QUESTION_EULA = 'QUESTION_EULA'
QUESTION_DEPRECATEDCPU = 'QUESTION_DEPRECATEDCPU'

class Validator(object):
   """
   Base validator

   Any types that inherit from this class *MUST* provide at least:
   key, text, required, and component.
   """
   def __init__(self, component, key, text, required, level=CUSTOM, default='',
                deferrable=False, existing=False):
      self.component = component
      self.text = text
      self.key = key
      self._required = required
      self._default = default
      self.level = level
      self.deferrable = deferrable
      self.existing = existing

      # This *must* be set by __init__ in the child class to a valid type.
      self.type = QUESTION_INVALID

   def __repr__(self):
      return '%s(%s)' % (
            self.__class__.__name__,
            ', '.join([repr(x) for x in [
                  self.component, self.key, self.text, self._required,
                  self.level, self._default]
                  ]))

   def __str__(self):
      return str((self.__class__.__name__, self.component, self.key))

   def GetDefault(self):
      existing = db.config.Get(self.component, self.key)
      return existing if existing else self._default

   def Validate(self, answer):
      raise NotImplementedError

class NumericEntry(Validator):
   """ Validate a numeric entry """
   def __init__(self, component, key, text, required, level=CUSTOM, default='0',
                deferrable=False, existing=False, min=-9999999, max=9999999):
      super(NumericEntry, self).__init__(component, key, text, required, level=level,
                                         default=default, deferrable=deferrable,
                                         existing=existing)

      self.min = min;
      self.max = max;

      self.type = QUESTION_NUMERIC

   def Validate(self, answer):
      try:
         answer = int(answer)
      except ValueError:
         raise ValidationError('Value entered must be an integer.')

      if answer < self.min or answer > self.max:
         raise ValidationError('The value must be greater than %d and less than %d.' % (self.min, self.max))

      return answer

class ClosePrograms(Validator):
   """ Close a list of programs """
   def __init__(self, component, key, text, required, level=CUSTOM, default='0', proglist=[]):
      super(ClosePrograms, self).__init__(component, key, text, required, level=level, default=default)

      self.min = min;
      self.max = max;

      self.type = QUESTION_CLOSEPROGRAMS
      self.initscript = None

      # XXX: Workaround
      # We need to stash this for later use.  Explicitly force it to a string,
      # then create a new path object from it.  If we don't, then the
      # INITSCRIPTDIR object will be evauluated later in the GUI thread, requiring
      # database access.  Since sqlite3 runs in the main installer thread and refuses
      # to run in more than one thread, it will throw an exception.
      #
      # If it's not set to anything, don't store it.
      if INITSCRIPTDIR:
         self.initscript = path(str(INITSCRIPTDIR/'vmware'))

   def checkVMsRunning(self):
      """ Check if there are VMs currently running """
      # XXX: Not really what I want to do, but I can't see a good way out of this.  We
      # XXX: need to verify that VMs really have been closed before continuing.
      # XXX: It would be better if we could keep this code in the component files.
      # XXX: Figure out a way to do this for Nitrogen.
      ret = shell.run(self.initscript, 'stoppable', ignoreErrors=True)
      if self.initscript and self.initscript.exists() and self.initscript.isfile() and os.stat(self.initscript).st_mode & 64 and ret['retCode'] != 0:
         return True
      if ret['retCode'] != 0:
         # Something in our fallback failed... Now go on to our absolute fallback.
         # pgrep against the known path to the VMX to make sure we don't pick up any other stray
         # processes that happen to have vmware-vmx in the name
         ret = shell.run('pgrep', '-f', 'vmware/bin/vmware-vmx', ignoreErrors=True)
         if ret['retCode'] == 0:
            # We found some still running vmware-vmx-* processes.
            return True

      # Either we detected no running VMs, or all of our detection methods have failed.  Allow
      # installation to continue.
      return False

   def Validate(self, answer):
      # XXX: Set the default for console mode.
      if answer != None:
         raise AbortError('Installation was aborted.')

      answer = 'Press enter to continue.'
      return answer

class YesNo(Validator):
   """ Validate a yes/no question """
   def __init__(self, component, key, text, required, default='', deferrable=False,
                existing=False, html=None, level=CUSTOM, secondaryText=None):
      """
      @param component: The component that asked this question
      @param key: The key to set in the database to the answer
      @param text: Text to display
      @param required: bool - Whether this is a required question or not
      @param html: A list ["link text to display", "Web page to display when link is clicked"]
      @param level: The question level
      """
      super(YesNo, self).__init__(component, key, text, required, level, default, deferrable, existing)

      self.type = QUESTION_YESNO
      self.linktext = None
      self.linkhtml = None
      if html:
         self.linktext = html[0]
         self.linkhtml = html[1]
      self.secondaryText = secondaryText

   def Validate(self, answer):
      answer = answer.lower()

      # Yes!
      if answer in ['y']:
         answer = 'yes'

      # No!
      if answer in ['n']:
         answer = 'no'

      if answer in ['quit', 'q']:
         raise AbortError()

      if answer not in ['yes', 'no']:
         raise ValidationError('Answer must be yes, y, no, or n')
      return answer

class TextEntry(Validator):
   """ Validate a text input """
   def __init__(self, component, key, text, required, default='', deferrable=False,
                existing=False, header=None, footer=None, level=CUSTOM, secondaryText=None):
      """
      @param component: The component that asked this question
      @param key: The key to set in the database to the answer
      @param text: Text to display
      @param required: bool - Whether this is a required question or not
      @param html: A list ["link text to display", "Web page to display when link is clicked"]
      @param level: The question level
      """
      super(TextEntry, self).__init__(component, key, text, required, level, default, deferrable, existing)

      self.type = QUESTION_TEXTENTRY
      self.header = header
      self.footer = footer
      self.secondaryText = secondaryText

   def Validate(self, answer):
      if answer is None:
         return None

      if not isinstance(answer, str):
         raise ValidationError('TextEntry must be a string')

      return answer.strip()

class Directory(Validator):
   """ Validate a directory path """
   def __init__(self, component, key, text, required, mustExist, default='', deferrable=False, existing=False,
               writeable=True, level=CUSTOM, secondaryText=None):
      super(Directory, self).__init__(component, key, text, required, level, default, deferrable, existing)

      self._mustExist = mustExist
      self._writeable = writeable
      self.type = QUESTION_DIRECTORY
      self.secondaryText = secondaryText

   def GetDefault(self):
      existing = db.config.Get(self.component, self.key)
      return existing if existing else str(self._default)

   def Validate(self, answer):
      if not isinstance(answer, str):
         raise ValidationError('Directory must be a string')

      # If it's not required accept the given answer as long as it is
      # empty.
      if not self._required and not answer.strip():
         return ''

      answer = path(answer.strip())

      if not answer:
         raise ValidationError('Directory must be non-empty')

      if not answer.isabs():
         raise ValidationError('Directory is not an absolute path')

      if answer.isfile():
         raise ValidationError('Path is an existing file')

      if not answer.exists() and self._mustExist:
         raise ValidationError('Directory path does not exist')

      if not answer.isdir() and self._mustExist:
         raise ValidationError('Directory path is not a directory')

      if not answer.access(os.W_OK) and self._writeable and self._mustExist:
         raise ValidationError('Directory path is not writeable')

      return answer

class File(Validator):
   """ Validate a file path """
   def __init__(self, component, key, text, required, mustExist, default='', deferrable=False,
                existing=False, writeable=True, level=CUSTOM, secondaryText=None):
      super(File, self).__init__(component, key, text, required, level, default, deferrable, existing)

      self._mustExist = mustExist
      self._writeable = writeable
      self.type = QUESTION_FILE
      self.secondaryText = secondaryText

   def GetDefault(self):
      existing = db.config.Get(self.component, self.key)
      return existing if existing else str(self._default)

   def Validate(self, answer):
      if not isinstance(answer, str):
         raise ValidationError('File must be a string')

      # If it's not required accept the given answer as long as it is
      # empty.
      if not self._required and not answer.strip():
         return ''

      answer = path(answer.strip())

      if not answer:
         raise ValidationError('File must be non-empty')

      if not answer.isabs():
         raise ValidationError('File is not an absolute path')

      if not answer.isfile():
         raise ValidationError('File path is not a file')

      if not answer.exists() and self._mustExist:
         raise ValidationError('File path does not exist')

      if not answer.access(os.W_OK) and self._writeable and self._mustExist:
         raise ValidationError('File path is not writeable')

      return answer

class InitDir(Directory):
   """ Validator for a directory containing init runlevels """
   def __init__(self, component, key, text, level, **kwargs):
      super(InitDir, self).__init__(component=component, key=key, text=text, level=level, mustExist=False,
                                          required=False, default=INITDIR, **kwargs)
      self.type = QUESTION_DIRECTORY

   def Validate(self, answer):
      """
      Validate that the given answer contains the expected directories

      @raises: ValidationError
      """
      super(InitDir, self).Validate(answer)

      # Accept a blank entry for those systems that don't have rc?.d style
      # init directories.
      if answer == '':
         return answer

      rcdirs = ('rc0.d', 'rc1.d', 'rc2.d', 'rc3.d', 'rc4.d', 'rc5.d', 'rc6.d')
      answer = path(answer)

      if all([(answer/rc).exists() for rc in rcdirs]):
         return answer
      else:
         raise ValidationError('%s is not an init directory' % answer)

   def GetDefault(self):
      """
      Locate the init directory by looking in known locations

      @returns: directory when found, otherwise empty string
      """
      default = db.config.Get(self.component, self.key)
      if default:
         return default

      initdirs = ('/etc/init.d',  # The "SuSE version >= 7.1" way
                  '/sbin/init.d', # The "SuSE version < 7.1" way
                  '/etc/rc.d',    # The "RedHat" way
                  '/etc',)        # The "Debian" way

      for i in initdirs:
         try:
            self.Validate(i)
            return i
         except (ValidationError, ValidationErrorNonFatal):
            continue

      return ''

class InitScriptDir(Directory):
   """ Validator for a directory containing init scripts """
   def __init__(self, component, key, text, level):
      super(InitScriptDir, self).__init__(component=component, key=key, text=text, level=level, mustExist=False,
                                          required=True, default=INITSCRIPTDIR)
      self.type = QUESTION_DIRECTORY

   def GetDefault(self):
      """ Locate init script directory using INITDIR """
      # INITDIR must be asked first since this question is based off
      # the answer for INITDIR.
      if str(INITDIR):
         init = INITDIR.abspath()  # strip off any weird /'s

         if not init.endswith('init.d'):
            init = init/'init.d'

         return init
      else:
         # Try /etc/init.d as a default.  If it doesn't exist, then we give up and use no default.
         init = path('/etc/init.d')
         if init.exists():
            return init
         else:
            log.warning('No init script directory was able to be located')
            return ''

class ShutdownProgram(Validator):
   """ Ensure a running program is shut down before continuing """
   def __init__(self, component, key, text, required, level=CUSTOM, program=None, programName=None):
      super(ShutdownProgram, self).__init__(component, key, text, required, level=level, default=CUSTOM)

      self.program = program
      self.programName = programName or program

      self.type = QUESTION_SHUTDOWNPROGRAM

   def Validate(self, answer):
      ret = run('/bin/sh', '-c', '/bin/ps -e | grep %s' %self.program)['stdout']

      if ret:
         # Found some processes that match the criteria.  Return a false.
         return False

      # Otherwise we're good, no matching processes were found.
      return True

class PortEntry(Validator):
   """ Validate a port entry """
   def __init__(self, component, key, text, required, default='', deferrable=False,
                existing=False, label='', level=CUSTOM, process=''):
      """
      @param component: The component that asked this question
      @param key: The key to set in the database to the answer
      @param text: Text to display
      @param required: bool - Whether this is a required question or not
      @param default: The default entry
      @param label: Label for the entry
      @param level: The question level
      @param process: The process name that will be holding this port (as shown by netstat -nvpa)
      """
      super(PortEntry, self).__init__(component, key, text, required, level, default, deferrable, existing)

      self.type = QUESTION_PORTENTRY
      self.label = label
      self.process = process

   def Validate(self, answer):
      # Validate format
      try:
         port = int(answer)
      except ValueError:
         raise ValidationError('Value entered must be digits.')

      # Validate range
      if port < 1 or port > 65535:
         raise ValidationError('Port values must be within 1 and 65535.')

      # Validate whether the port is available. We try to open the port and
      # listen, and if it fails, we use netstat to try to figure out what's
      # using it.
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      error = ''
      try:
         sock.bind(('', port))
      except socket.error:
         netstat = run('/bin/netstat', '-nvpa', ignoreErrors=True, noLogging=True)
         error = 'port %s is in use' % port
         if netstat['retCode'] == 0:
            for procPort, procPID, procName in re.findall(
                  '^\S+\s+\S+\s+\S+\s+\S+\:(\d+)\s+\S+\s+\S+\s+(\d+)\/(\S+)',
                  netstat['stdout'], re.MULTILINE):
               if port == int(procPort):
                  name = run('/bin/ps', '-o', 'comm=', procPID,
                             ignoreErrors=True, noLogging=True)['stdout']
                  name = name.rstrip() or procName

                  # If we're scanning for a process, allow the port to be used
                  # if it's in use by a process matching the given name.
                  if self.process and self.process in name:
                     error = ''
                  else:
                     error = 'port %s is in use by %s' % (port, name)
                  break
      finally:
         # Make sure to release the port.
         sock.close()

      if error and not 'deferred-gtk' in ui.TYPE:
         raise ValidationError('The VMware Installer has detected that %s. '
                               'The installing product will not run '
                               'properly if its port is in use.' % error)

      return answer

class DualPortEntries(Validator):
   """ Validate dual port entries 80/443 for example """
   def __init__(self, component, key, text, required, default='', deferrable=False,
                existing=False, label1='', label2='', level=CUSTOM, process=''):
      """
      @param component: The component that asked this question
      @param key: The key to set in the database to the answer
      @param text: Text to display
      @param required: bool - Whether this is a required question or not
      @param default: The default entry
      @param label1: Label for the first entry
      @param label2: Label for the second entry
      @param level: The question level
      @param process: The process name that will be holding this port (as shown by netstat -nvpa)
      """
      super(DualPortEntries, self).__init__(component, key, text, required, level, default, deferrable, existing)

      self.type = QUESTION_DUALPORTENTRIES
      self.label1 = label1
      self.label2 = label2
      self.process = process

   def Validate(self, answer):
      ports = answer.split('/')
      # Validate integers
      try:
         for i in range(2):
            num = int(ports[i])
      except ValueError:
         raise ValidationError('Values entered must be digits.')
      # Now validate range
      try:
         for i in range(2):
            num = int(ports[i])
            if num < 1 or num > 65535:
               raise ValueError
      except ValueError:
         raise ValidationError('Port values must be within 1 and 65535.')

      # Now check to be sure the ports are free.
      http = ports[0]
      https = ports[1]

      # run this just once and use the results in the following loop
      self.netstat = run('/bin/netstat', '-nvpa', ignoreErrors=True, noLogging=True)

      errorString = ''
      inUse = []
      for port in ports:
         # Try to open the port for listening.  If we fail, assume it's taken and use netstat to
         # try and figure out what's using it.
         sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
         try:
            sock.bind(('', int(port)))
         except socket.error as e:
            # If we've already found an error, add an " and " to the error message.
            if errorString:
               errorString = errorString + ' and ';

            # Cannot bind the socket.  Use netstat to find out why.
            if self.netstat['retCode'] == 0:
               txt = self.netstat['stdout']
               # Scan ports in use to find our port
               allPorts = re.findall('^\S+\s+\S+\s+\S+\s+\S+\:(\d+)\s+\S+\s+\S+\s+(\d+)\/(\S+)',
                                  txt, re.MULTILINE)
               for procs in allPorts:
                  if port == procs[0]:
                     # Find the real name of the process
                     name = run('/bin/ps', '-o', 'comm=', procs[1],
                                ignoreErrors=True, noLogging=True)['stdout']
                     if name:
                        name = name.rstrip()

                        # If we're scanning for a process, allow the port to be used
                        # if it's in use by a process matching the given name.
                        if self.process and self.process in name:
                           continue

                        errorString = errorString + 'port %s is in use by %s' % (procs[0], name)
                     else:
                        errorString = errorString + 'port %s is in use' % procs[0]
                     break
            else:
               errorString = errorString + 'port %s is in use' % port
         finally:
            # Make sure to release the port.
            sock.close()

      if errorString:
         errorString = 'The VMware Installer has detected that ' + errorString + \
                       '.  The installing product will not run properly if its ports are in use.'
         raise ValidationErrorNonFatal(errorString)

      return answer

class EULA(Validator):
   """ Validate the acceptance of a EULA """
   def __init__(self, component, key, text, componentName, existing=False):
      super(EULA, self).__init__(component=component, key=key , text=text, required=True,
                                 level=REQUIRED, deferrable=True, existing=existing)
      self.componentName = componentName

      self.type = QUESTION_EULA

   def Validate(self, answer):
      """
      Validate acceptance

      @raises EULAError
      """
      answer = answer and answer.strip().lower()

      if answer in ('n', 'no'):
         raise EULADeclinedError('EULA was not accepted')

      if not answer or answer not in ('y', 'yes'):
         raise EULAError('The EULA must be accepted by typing either y or yes')

      return answer

class CPUCheck(Validator):
   """ Validate the choice when encoutering deprecated CPUs """
   def __init__(self, component):
      super(CPUCheck, self).__init__(component=component, key='' , text='', required=True, level=REQUIRED)

   def Validate(self, answer):
      """
      Validate acceptance

      @raises CPUCheckError or IgnoreCPUCheckError
      """
      answer = answer and answer.strip().lower()

      if answer in ('n', 'no'):
         raise CPUCheckError('Stop the installation')

      if not answer or answer not in ('y', 'yes'):
         raise IgnoreCPUCheckError('If you still want to install the product, please type either y or yes')

      return answer
