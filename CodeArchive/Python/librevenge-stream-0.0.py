# -*- tab-width: 4; indent-tabs-mode: nil; py-indent-offset: 4 -*-
# librevenge
# Version: MPL 2.0 / LGPLv2.1+
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Alternatively, the contents of this file may be used under the terms
# of the GNU Lesser General Public License Version 2.1 or later
# (LGPLv2.1+), in which case the provisions of the LGPLv2.1+ are
# applicable instead of those above.
#

# Auto-load of all the printers.

import sys

import gdb

pythondir = '${prefix}/share/librevenge/python'

if pythondir not in sys.path:
    sys.path.insert(0, pythondir)

import librevenge.v0_0.streams
librevenge.v0_0.streams.register_pretty_printers(gdb.current_objfile())

# vim:set filetype=python shiftwidth=4 softtabstop=4 expandtab:
