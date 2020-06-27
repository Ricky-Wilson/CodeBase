"""
Copyright 2012 VMware, Inc.  All rights reserved. -- VMware Confidential
"""

def CompareVersionString(version0, version1):
   """
   Compare two version strings

   @param version0: The left-hand version
   @param version1: The right-hand version

   @returns: -1 if version0 < version1
   @returns:  0 if version0 = version1
   @returns:  1 if version0 > version1
   """
   v0 = version0.split('.')
   v1 = version1.split('.')
   v0 = [int(x) for x in v0]
   v1 = [int(x) for x in v1]
   return (v0 > v1) - (v0 < v1)
