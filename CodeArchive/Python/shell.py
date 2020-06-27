"""
Copyright 2007 VMware, Inc.  All rights reserved. -- VMware Confidential

Generic shell functions.
"""


import functools
import os
import signal
import time

from select import select, error as selectError
from subprocess import Popen, PIPE
from vmis import ui
from vmis.util.log import getLog
from vmis.util.path import path

log = getLog('vmis.util.shell')
stdout = getLog('vmis.stdout')
stderr = getLog('vmis.stderr')

def output(program, *args, **kwargs):
   """
   Returns the stdout output of program

   @param program: exectuable to run in PATH
   @param *args: arguments to pass to program

   @returns: A tuple of (return code, stdout, stderr)

   @raises OSError: if program is not found or something else bad happens
   """
   stdout = kwargs.get('stdout', True)
   stderr = kwargs.get('stderr', False)

   p = Popen([program] + list(args), stdout=PIPE, stderr=PIPE)
   out = p.communicate()

   ret = [p.returncode]

   stdout and ret.append(out[0])
   stderr and ret.append(out[1])

   return tuple(ret)

def run(program, *args, **kwargs):
   """
   Executes a given program.

   @todo: log stderr to log for all, log stdout for DEBUG

   @param program: exectuable to run in PATH
   @param *args: arguments to pass to program
   @param **kwargs: ignoreErrors to ignore OSError exception.  The
   rest are passed on to Popen.
   @returns: exit code

   @raises OSError: if program is not found or something else bad happens
   """
   ignoreErrors = kwargs.pop('ignoreErrors', None)
   noLogging = kwargs.pop('noLogging', None)
   timeout = kwargs.pop('timeout', None)
   stdin = kwargs.pop('stdin', None)

   def _killPipe(pipe=None, data2=None, data3=None):
      """
      Kill the current process and its children.  This is
      set either via SIGALRM.

      @param pipe: the pipe
      @param data2: signum from SIGALRM
      @param data3: frame from SIGARLM
      """
      # from SIGALRM, data=signum, data2=fram
      if not pipe:
         log.debug('No pipe registered.  Returning from _killPipe')
         return
      log.info('Timeout has expired.  Killing the running process.')
      # Kill the process and its children and its children's children,
      # and you get the idea.
      log.info('Calling kill on process tree %d', pipe.pid)
      KillProcTree(pipe.pid)
      waited = 0
      # Poll once a second for 10 seconds to see if it's exited.
      while pipe.poll() is None and waited < 10:
         time.sleep(1)
         waited = waited + 1
      # If it has not, kill it outright with a SIGKILL
      if pipe.poll() is None:
         log.info('Kill did not work, calling kill -9 on pocess tree %d', pipe.pid)
         KillProcTree(pipe.pid, 9)
      log.info('Killed process %d', pipe.pid)

   def run_(program, args, kwargs):
      log.debug('Running: %s', [program] + list(args))

      env = dict(os.environ)

      # Empty the text buffers for stdout and stderr
      stdoutList = []
      stderrList = []

      logfunc = log.info
      # Still log in debug mode if noLogging is set.
      if noLogging:
         logfunc = log.debug

      # We coerce all arguments to strings because they may be
      # Destinations or sublcasses thereof which don't convert to
      # strings automatically.
      if stdin:
         pipe = Popen([str(program)] + [str(arg) for arg in args],
                      stdout=PIPE, stderr=PIPE, stdin=PIPE, env=env,
                      close_fds=True, **kwargs)
      else:
         with open('/dev/null', 'r') as null: # Close stdin
            pipe = Popen([str(program)] + [str(arg) for arg in args],
                         stdout=PIPE, stderr=PIPE, stdin=null, env=env,
                         close_fds=True, **kwargs)

      # If we've been given a timeout, set up our signal handler and a
      # SIGALRM to run at the end of the timeout.
      sigHandler = None
      if timeout:
         # Inconveniently, when the GUI is running, this installer runs in
         # a secondary thread.  Unfortunately, Python only allows signals
         # to be used on the main thread, so we can't use the same method
         # for both console and GUI.  We'll use a GLIB timout instead.
         # (which actually is nicer ;)
         #
         # When we are in console mode, we have no GLIB available, and
         # are running in a single thread, so must fall back on using
         # SIGARLM.
         log.debug('Setting SIGALRM for %d seconds', timeout)

         # Use partial to set the argument for killpipe.
         func = functools.partial(_killPipe, pipe)
         sigHandler = signal.signal(signal.SIGALRM, func)
         signal.alarm(timeout)

      # Wait for process to exit, then read stdout and stderr via
      # the communicate function, which ensures that neither process
      # will block in I/O because of a full pipe.  Communicate returns
      # when the process exits.
      (sout, serr) = pipe.communicate(input=stdin)
      if sout != '':
         logfunc(sout)
         stdoutList.append(sout.decode('utf-8'))
      if serr != '':
         logfunc(serr)
         stderrList.append(serr.decode('utf-8'))

      ret = {}
      ret['retCode'] = pipe.wait()
      ret['stdout']  = '\n'.join(stdoutList)
      ret['stderr']  = '\n'.join(stderrList)

      log.debug('Return value: %d', ret['retCode'])

      # If we had set a timeout, disable it and restore the original
      # signal handler for SIGALRM.
      if timeout:
         # Again here, we need to reset SIGALRM or use GLIB to
         # remove our timer from the GUI thread.
         signal.alarm(0)
         signal.signal(signal.SIGALRM, sigHandler)

      return ret

   retval = []
   if ignoreErrors:
      try:
         retval = run_(program, args, kwargs)
      except OSError as e:
         log.warning('Ignored execution error: %s when running command: %s', e, [program] + list(args))
         # We are ignoring this error, but still need
         # to return something.
         retval = {}
         retval['retCode'] = None
         retval['stdout']  = None
         retval['stderr']  = None
      except selectError as e:
         # The process was killed
         log.warning('Process timed out and was killed. Ignoring error.')
   else:
      try:
         retval = run_(program, args, kwargs)
      except selectError as e:
         # The process was killed
         log.error('Command killed by timeout: %s', [program] + list(args))
         raise OSError('Process timed out and was killed.')
      except Exception as e:
         log.error('Error running command: %s', [program] + list(args))
         raise
   return retval

def KillProcTree(pid, signal=15):
   """
   Kill an entire tree of processes, with pid as the parent.

   @param pid: Parent process ID
   @param signal: Signal to sent to all processes
   """
   def AddChildren(pid, pslist, killList):
      # Add this pid
      killList.append(pid)
      for proc in pslist[1:]:
         lst = proc.split()
         if int(lst[1]) == pid:
            # Recurse on its children
            AddChildren(int(lst[0]), pslist, killList)

   pipe = os.popen('ps -eo pid,ppid')
   pslist = pipe.readlines()
   killList = []
   AddChildren(pid, pslist, killList)

   # Now that we have a list of our pid and all its children, etc.
   # Kill them all.
   if len(killList) > 0:
      cmd = 'kill -%d' % signal
      for proc in killList:
         cmd = cmd + ' ' + str(proc)
      os.system(cmd)

def Escape(string):
   """ Escapes a string for use in a shell context """
   return "'%s'" % string.replace("'", '"\'"')

def Which(program):
   """
   Gets the PATH environment variable and checks for program
   in order.

   @param program: Executable to search for
   @returns: Full path if found and executable, None otherwise
   """
   systemPath = os.environ.get('PATH')
   paths = systemPath.split(':')
   for p in paths:
      fullPath = path(p)/program
      if fullPath.isexe():
         return str(fullPath) # Return a string, not a path object

   return None
