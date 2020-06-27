#!/usr/bin/env python
'''
Copyright (C) 2019, WAFW00F Developers.
See the LICENSE file for copying permission.
'''

NAME = 'BitNinja (BitNinja)'


def is_waf(self):
    schemes = [
        self.matchContent(r'Security check by BitNinja'),
        self.matchContent(r'Visitor anti-robot validation')
    ]
    if any(i for i in schemes):
        return True
    return False