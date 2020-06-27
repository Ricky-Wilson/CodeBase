"""
Copyright 2007,2019 VMware, Inc.  All rights reserved. -- VMware Confidential

@todo: Can probably make it faster by moving to the right location
instead of clearing the entire line every time.  Increases in rxvt are
very choppy when it progresses very fast.  Might really show over a
slow ssh connection.
"""
import curses
import math
import sys
import time

from vmis.db import db
from vmis.ui import base
from vmis.ui.uiAppControl import UIAppControl
from vmis.util import Format
from vmis.util.log import getLog
from pathlib import Path

log = getLog('vmis.ui.console')

PRIMARY_LINE = 0
SECONDARY_LINE = 1
PROGRESS_LINE = 2

EULA = base.EULA
CPUCheck = base.CPUCheck
Question = base.Question
Finish = base.Finish
PromptInstall = base.PromptInstall
ShowMessage = base.ShowMessage

class Wizard(base.Wizard):
   """ Console UI wizard """
   HEADER = '['
   FOOTER = ']'
   PERCENT = '%4s%%'
   WIDTH = 70

   def __init__(self, txn):
      # curses must be setup here, otherwise it will fail when run
      # from a dumb terminal.
      curses.setupterm()

      COMMANDS = \
          {'CURSOR_INVISIBLE': 'civis',
           'CURSOR_RESET': 'cnorm',
           'CLEAR': 'el',
           'RESET_ATTR': 'sgr0',
           'MOVE_DOWN': 'cud1',
           'MOVE_UP': 'cuu1',
           'BOLD': 'bold',}

      for name, cmd in COMMANDS.items():
         globals()[name] = curses.tigetstr(cmd)

      self._printed = 0
      self._addNewline = False
      self._cursorEnabled = True
      self._curLine = 0         # Line 0: Primary message
                                # Line 1: Secondary message
                                # Line 2: Progress bar
      self._lowestLine = 0

      # Set up App Control.
      try:
         self.appControl = UIAppControl()
      except:
         self.appControl = None

   def ShowFinish(self, success, message):
      """ Clean up and restore console state """
      self.EnableCursor(True)
      self._moveLine(self._lowestLine)

      # Newline before printing our final message.
      print()

      if success:
         print(Format(message))
      else:
         print(Format(message), file=sys.stderr)

   def UserMessage(self, messageType, message, useWrapper=False):
      """ In console, a passthrough to ShowMessage """
      ShowMessage(messageType, message, useWrapper=useWrapper)

   def ShowPromptInstall(self):
      input(Format('The product is ready to be installed.  Press Enter to begin '
                       'installation or Ctrl-C to cancel.'))
      print()

   def SetProgress(self, fraction):
      """ Print a progress bar at the given fraction """
      self._moveLine(PROGRESS_LINE)

      percent = min(fraction * 100, 100)

      if self._cursorEnabled:
         self.EnableCursor(False)    # Disable blinking cursor
         self._cursorEnabled = False

      self._addNewline = True

      if percent < 0 or percent > 100:
         return

      percent = int(math.ceil(percent))
      scaled = int(math.ceil(percent * self.WIDTH / 100))

      self._moveBeginOfLine()

      write = self.HEADER
      self._printed += len(write)
      sys.stdout.write(write)

      write = '#' * scaled
      self._printed += len(write)
      sys.stdout.write(write)

      write = ' ' * (self.WIDTH - scaled)
      self._printed += len(write)
      sys.stdout.write(write)

      write = self.FOOTER
      self._printed += len(write)
      sys.stdout.write(write)

      write = self.PERCENT % percent
      self._printed += len(write)
      sys.stdout.write(write)

      sys.stdout.flush()

   def EnableCursor(self, enable):
      """ Enable or disable the cursor """
      if enable and not self._cursorEnabled:
         sys.stdout.buffer.write(CURSOR_RESET)
      elif not enable and self._cursorEnabled:
         sys.stdout.buffer.write(CURSOR_INVISIBLE)

      self._cursorEnabled = enable

      sys.stdout.buffer.flush()

   def _moveBeginOfLine(self):
      """ Move to the beginning of the current line """
      sys.stdout.buffer.write(curses.tparm(curses.tigetstr('hpa'), 0))
      sys.stdout.buffer.flush()

   def SetPrimaryText(self, txt):
      pass

   def SetSecondaryText(self, txt):
      pass

   def EnableBack(self, enabled):
      pass

   def EnableNext(self, enabled):
      pass

   def HideCancel(self):
      pass

   def HideBack(self):
      pass

   def HideNext(self):
      pass

   def SetTitle(self, title):
      pass

   def SetNextType(self, type):
      pass

   def _moveLine(self, line):
      """ Move the cursor to given line number at the beginning of the line """
      move = line - self._curLine

      self._moveBeginOfLine()

      if move < 0:              # up
         move = abs(move)
         cmd = MOVE_UP
      elif move > 0:            # down
         cmd = MOVE_DOWN
      else:                     # stay
         cmd = b''

      self._curLine = line
      self._lowestLine = max(self._lowestLine, line)

      sys.stdout.buffer.write(cmd * move)
      sys.stdout.buffer.flush()

   def SetPrimaryProgressMessage(self, text):
      self._moveLine(PRIMARY_LINE)

      sys.stdout.buffer.write(CLEAR)
      sys.stdout.buffer.write(BOLD)
      sys.stdout.buffer.flush()

      sys.stdout.write(text)
      sys.stdout.flush()

      sys.stdout.buffer.write(RESET_ATTR)
      sys.stdout.buffer.flush()

   def SetSecondaryProgressMessage(self, text):
      self._moveLine(SECONDARY_LINE)

      sys.stdout.buffer.write(CLEAR)
      sys.stdout.buffer.flush()
      sys.stdout.write('    %s' % text)

      sys.stdout.flush()

   def ShowProgress(self):
      """ Initialize progress display """
      sys.stdout.write('\n' * 2) # Create empty lines to display messages and progress
      sys.stdout.flush()

      self._curLine = PROGRESS_LINE

if __name__ == '__main__':
   ui = Wizard(None, None, None)

   ui.SetPrimaryProgressMessage('Primary')
   ui.SetSecondaryProgressMessage('Secondary')

   for i in range(0, 101):
      ui.SetProgress(i / 100.0)
      time.sleep(.002)

   ui.ShowFinish()
