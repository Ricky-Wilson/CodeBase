#!/usr/bin/env python
'''
Copyright (C) 2019, WAFW00F Developers.
See the LICENSE file for copying permission.
'''

NAME = 'TransIP Web Firewall (TransIP)'


def is_waf(self):
    schemes = [
        self.matchHeader(('X-TransIP-Backend', '.+')),
        self.matchHeader(('X-TransIP-Balancer', '.+'))
    ]
    if any(i for i in schemes):
        return True
    return False