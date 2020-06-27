"""
Copyright 2008,2019 VMware, Inc.  All rights reserved. -- VMware Confidential

A null UI useful for doing automated installs whose output is
captured.
"""

import sys

from vmis.core.errors import EULAError
from vmis.ui import base
from vmis.ui.uiAppControl import UIAppControl
from vmis.util import Format

class Wizard(base.Wizard):
   """ Non-interactive UI wizard """
   def __init__(self, txn):
      # This initializier was originally overridden so that the curses
      # setup doesn't get called.
      # Now also set up App Control.
      try:
         self.appControl = UIAppControl()
      except:
         self.appControl = None

   def ShowFinish(self, success, message):
      """ Prints finish message """
      if success:
         print(Format(message))
      else:
         print(Format(message), file=sys.stderr)

   def UserMessage(self, messageType, message, useWrapper=False):
      """ In null console, a passthrough to ShowMessage """
      ShowMessage(messageType, message, useWrapper=useWrapper)

   def ShowPromptInstall(self):
      pass

   def SetProgress(self, fraction):
      """ Print a progress bar at the given fraction """
      pass

   def ShowProgress(self):
      pass

   def SetPrimaryProgressMessage(self, text):
      print(text)

   def SetSecondaryProgressMessage(self, text):
      print(text)

EULA = base.EULA
CPUCheck = base.CPUCheck
Question = base.Question
Finish = base.Finish
PromptInstall = base.PromptInstall
ShowMessage = base.ShowMessage
