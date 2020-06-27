#!/usr/bin/env python

"""
Pandoc filter to convert definition lists to bullet
lists with the defined terms in strong emphasis (for
compatibility with standard markdown).
"""

from pandocfilters import toJSONFilter, BulletList, Para, Strong


def deflists(key, value, format, meta):
    if key == 'DefinitionList':
        return BulletList([tobullet(t, d) for [t, d] in value])


def tobullet(term, defs):
    return([Para([Strong(term)])] + [b for d in defs for b in d])


if __name__ == "__main__":
    toJSONFilter(deflists)
