#!/usr/bin/env python
'''
Copyright (C) 2019, WAFW00F Developers.
See the LICENSE file for copying permission.
'''

NAME = 'Tencent Cloud Firewall (Tencent Technologies)'


def is_waf(self):
    schemes = [
        self.matchContent(r'waf\.tencent\-?cloud\.com/')
    ]
    if any(i for i in schemes):
        return True
    return False