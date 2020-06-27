#!/usr/bin/env python
'''
Copyright (C) 2019, WAFW00F Developers.
See the LICENSE file for copying permission.
'''

NAME = 'NexusGuard Firewall (NexusGuard)'


def is_waf(self):
    schemes = [
        self.matchContent(r'Powered by Nexusguard'),
        self.matchContent(r'nexusguard\.com/wafpage/.+#\d{3};')
    ]
    if any(i for i in schemes):
        return True
    return False