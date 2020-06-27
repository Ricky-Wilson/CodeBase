#!/usr/bin/python
#
# Copyright (C) 2010 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as 
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Authored by
#              Mikkel Kamstrup Erlandsen <mikkel.kamstrup@canonical.com>
#

from gi.repository import Dee
from gi.repository import GLib

m = Dee.SequenceModel.new()
m.set_schema("i", "s")
m.append(27, "Hello")
m.append(68, "world")

# Pythonic iteration
for row in m:
    print row

# Python len() behaviour
print "That was %s rows right there" % len(m)

# Pythonic access-by-index
print "At position [0][0] we have: %s" % m[0][0]
print "At position [0][1] we have: %s" % m[0][1]
print "At position [1][0] we have: %s" % m[1][0]
print "At position [1][1] we have: %s" % m[1][1]

# Pythonic updates by index
m[1][1] = "Mars"
print "And we've now changed [1][1] to: %s" % m[1][1]

# Individual row handling by index or row iter
itr = m.get_iter_at_row(1)
row1 = m[itr]
row2 = m[1]
print "Is it true that rows can be compared? %s" % (row1 == row2)

# Pythonic list comprehension on the row level
print "Values in row 1: %s" % ", ".join (map(str,row1))

# And check this out - assign full rows in one go!
# Works with row iters and indexes alike
m[1] = 16, "Points for awesome Python integration"
print "And now we've done a full row assignment: %s" % m[1]

# Persistent storage of models - and Dee.Serializables in general
resources = Dee.resource_manager_get_default ()
resources.store (m, "pythontricks.testmodel")
m2 = resources.load ("pythontricks.testmodel")
print "Model stored and loaded from disk, and 2nd row still says: %s" % m2[1]

#
# Model with more advanced schemas
#
complex_model = Dee.SequenceModel.new()
complex_model.set_schema ("i", "a{sv}", "(uss)")
complex_model.append (32, { "myproperty" : GLib.Variant("i", 42) }, (52, "hello", "world"))
print "A complex model: %s" % complex_model[0]
