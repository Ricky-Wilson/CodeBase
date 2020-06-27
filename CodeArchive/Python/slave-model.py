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



class Slave:
  def __init__(self):
    model_name = "com.canonical.Dee.Model.Example"
    print ("Joining model %s" % model_name)
    self.model = Dee.SharedModel.new(model_name)
    self.model.connect("row-added", self.on_row_added, None)

  def print_row (self, model, iter):
    while i < self.model.get_n_columns ():
      s = str(self.model.get_value (model, iter, i))
      if (i == 0):
        print "ADDED: %s" % s
      else:
        print ", %s" % s
      i = i + 1

  def on_row_added(self, model, iter):
    print_row(model, iter)

if __name__ == "__main__":

  s = Slave ()
  GObject.MainLoop().run()

