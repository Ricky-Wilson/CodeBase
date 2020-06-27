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
#              Ken VanDine <ken.vandine@canonical.com>
#

from gi.repository import Dee
from gi.repository import GObject

class Master:
  def __init__(self):
    self.model = Dee.SharedModel.new("com.canonical.Dee.Model.Example")
    self.model.set_schema ("i", "s")
    self.model.connect("row-added", self.on_row_added)
    GObject.timeout_add_seconds(1, self.add)

  def on_row_added (self, model, itr):
    print "SIG", self, model, itr
    i = self.model.get_int32 (itr, 0)
    s = self.model.get_string (itr, 1)
    print "Master:", i, s
  
  def add(self):
    itr = self.model.append(10, "Rooney")
    print "ADDED", itr
    print "GET(i)", self.model.get_int32 (itr, 0), self.model.get_string (itr, 1)
    
    return True

if __name__ == "__main__":
  master = Master ()
  GObject.MainLoop().run()
