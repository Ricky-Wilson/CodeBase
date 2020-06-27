# -*- coding: utf-8 -*-
#
# (c) Copyright 2003-2015 HP Development Company, L.P.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307 USA
#
# Author: Don Welch
#


from base.sixext import  to_unicode

# Qt
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

class FABNameTable(QTableWidget):
    def __init__(self, parent):
        QTableWidget.__init__(self, parent)
        
        
    def mimeData(self, items):
        data = QMimeData()
        data.setText(to_unicode('|').join([to_unicode(i.text()) for i in items]))
        return data
    
