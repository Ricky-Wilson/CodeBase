"""
Copyright 2008 VMware, Inc.  All rights reserved. -- VMware Confidential
"""

# XXX 5-2-2008: prevent internal breakage, get rid of it later
class Permissions(object):
   """ Standard permissions """
   DEFAULT = 0o644
   BINARY  = 0o755
   SETUID  = 0o4755
