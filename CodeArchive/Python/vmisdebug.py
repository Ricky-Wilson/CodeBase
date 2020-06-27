#
# Copyright 2008 VMware, Inc.  All rights reserved. -- VMware Confidential
#

"""
Some simple helper debugging methods for VMIS.
"""

import traceback
import sys

debugOn = False


def PrintException(cls, excep):
    """ Given an exception, print it's trace """
    (dontcare, dontcare2, tback) = sys.exc_info()
    traceback.print_exception(cls, excep, tback)

def PrintList(lst):
    """ Print a list """
    print('\n'.join(map(str, L)))

def PrintStack():
    """ Print the current stack """
    traceback.print_stack()

def FatalError(str):
    """ Report an error and throw RuntimeError """
    print('Fatal Error: ' + str)
    PrintStack()
    raise RuntimeError
