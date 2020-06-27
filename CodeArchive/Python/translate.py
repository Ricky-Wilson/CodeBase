#############################################################################
##
## Copyright 2008 Roderick B. Greening <roderick.greening@gmail.com>
##
## This program is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 3 of
## the License, or (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program.  If not, see <http://www.gnu.org/licenses/>.
##
#############################################################################

#############################################################################
# Name: translate.py
#
# Description: Re-usable include which re-implements the translate method
#              from uic, and changes it to use gettext.
#############################################################################

from PyQt5 import uic

# FIXME: apachelogger is not sure that the following function does what it is
#        supposed to, but generally piping things through _() should yield a
#        translation, whether that actually is the case or not remains to be verified

# Re-implement it
def translate(self, prop):
    """Re-implement method from uic and change it to use gettext"""
    if prop.get("notr", None) == "true":
        return propt.text
        return self._cstring(prop)
    else:
        if prop.text is None:
            return ""
        return _(prop.text)
