#!/usr/bin/env python

'''
LEGION (https://govanguard.io)
Copyright (c) 2018 GoVanguard

    This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSignal, QObject 
from app.auxiliary import *                                                 # for bubble sort

class ServicesTableModel(QtCore.QAbstractTableModel):                   # needs to inherit from QAbstractTableModel

    def __init__(self, services = [[]], headers = [], parent = None):
        QtCore.QAbstractTableModel.__init__(self, parent)
        self.__headers = headers
        self.__services = services
        
    def setServices(self, services):
        self.__services = services

    def rowCount(self, parent):
        return len(self.__services)

    def columnCount(self, parent):
        if not len(self.__services) is 0:
            return len(self.__services[0])
        return 0
        
    def headerData(self, section, orientation, role):
        if role == QtCore.Qt.DisplayRole:           
            if orientation == QtCore.Qt.Horizontal:             
                if section < len(self.__headers):
                    return self.__headers[section]
                else:
                    return "not implemented"

    def data(self, index, role):                                        # this method takes care of how the information is displayed

        if role == QtCore.Qt.DecorationRole:                            # to show the open/closed/filtered icons
            if index.column() == 0 or index.column() == 2:
                tmp_state = self.__services[index.row()]['state']

                stateMap = {'open':'open', 'closed':'closed', 'filtered':'filtered'}
                defaultState = 'filtered'

                stateIconName = stateMap.get(str(tmp_state)) or defaultState
                stateIcon = "./images/{stateIconName}.gif".format(stateIconName=stateIconName)
                return QtGui.QIcon(stateIcon)

        if role == QtCore.Qt.DisplayRole:                               # how to display each cell
            value = ''
            row = index.row()
            column = index.column()

            if column == 0:             
                value = '   ' + self.__services[row]['ip']              # the spaces are needed for spacing with the icon that precedes the text
            elif column == 1:
                value = self.__services[row]['portId']
            elif column == 2:
                value = '   ' + self.__services[row]['portId']         # the spaces are needed for spacing with the icon that precedes the text
            elif column == 3:
                value = self.__services[row]['protocol']
            elif column == 4:
                value = self.__services[row]['state']
            elif column == 5:
                value = self.__services[row]['hostId']
            elif column == 6:
                value = self.__services[row]['serviceId']
            elif column == 7:
                value = self.__services[row]['name']
            elif column == 8:
                value = self.__services[row]['product']
            elif column == 9:
                if not self.__services[row]['product'] == None and not self.__services[row]['product'] == '':
                    value = str(self.__services[row]['product'])
                
                if not self.__services[row]['version'] == None and not self.__services[row]['version'] == '':
                    value = value + ' ' + self.__services[row]['version']

                if not self.__services[row]['extrainfo'] == None and not self.__services[row]['extrainfo'] == '':
                    value = value + ' (' + self.__services[row]['extrainfo'] + ')'
            elif column == 10:
                value = self.__services[row]['extrainfo']
            elif column == 11:
                value = self.__services[row]['fingerprint']
            return value

    def flags(self, index):                                             # method that allows views to know how to treat each item, eg: if it should be enabled, editable, selectable etc
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable

    def sort(self, Ncol, order):                                        # sort function called when the user clicks on a header
        self.layoutAboutToBeChanged.emit()
        array = []
        
        if Ncol == 0:                                                   # if sorting by ip (and by default)
            for i in range(len(self.__services)):
                array.append(IP2Int(self.__services[i]['ip']))

        elif Ncol == 1:                                                 # if sorting by port
            for i in range(len(self.__services)):
                array.append(int(self.__services[i]['portId']))

        elif Ncol == 2:                                                 # if sorting by port
            for i in range(len(self.__services)):
                array.append(int(self.__services[i]['portId']))
                
        elif Ncol == 3:                                                 # if sorting by protocol
            for i in range(len(self.__services)):
                array.append(self.__services[i]['protocol'])
                
        elif Ncol == 4:                                                 # if sorting by state
            for i in range(len(self.__services)):
                array.append(self.__services[i]['state'])
                
        elif Ncol == 7:                                                 # if sorting by name
            for i in range(len(self.__services)):
                array.append(self.__services[i]['name'])
            
        elif Ncol == 9:                                                 # if sorting by version
            for i in range(len(self.__services)):           
                value = ''
                if not self.__services[i]['product'] == None and not self.__services[i]['product'] == '':
                    value = str(self.__services[i]['product'])
                
                if not self.__services[i]['version'] == None and not self.__services[i]['version'] == '':
                    value = value + ' ' + self.__services[i]['version']

                if not self.__services[i]['extrainfo'] == None and not self.__services[i]['extrainfo'] == '':
                    value = value + ' (' + self.__services[i]['extrainfo'] + ')'
                array.append(value)

        sortArrayWithArray(array, self.__services)                      # sort the services based on the values in the array
        
        if order == Qt.AscendingOrder:                                  # reverse if needed
            self.__services.reverse()   
            
        self.layoutChanged.emit()                           # update the UI (built-in signal)

    ### getter functions ###
    
    def getPortForRow(self, row):
        return self.__services[row]['portId']
        
    def getServiceNameForRow(self, row):
        return self.__services[row]['name']
            
    def getIpForRow(self, row):
        return self.__services[row]['ip']
        
    def getProtocolForRow(self, row):
        return self.__services[row]['protocol']     

    ####################################################################

class ServiceNamesTableModel(QtCore.QAbstractTableModel):

    def __init__(self, serviceNames = [[]], headers = [], parent = None):
        QtCore.QAbstractTableModel.__init__(self, parent)
        self.__headers = headers
        self.__serviceNames = serviceNames
        
    def setServices(self, serviceNames):
        self.__serviceNames = serviceNames

    def rowCount(self, parent):
        return len(self.__serviceNames)

    def columnCount(self, parent):
        if not len(self.__serviceNames) is 0:
            return len(self.__serviceNames[0])
        return 0
        
    def headerData(self, section, orientation, role):
        if role == QtCore.Qt.DisplayRole:           
            if orientation == QtCore.Qt.Horizontal:             
                if section < len(self.__headers):
                    return self.__headers[section]
                else:
                    return "not implemented"

    def data(self, index, role):                                        # This method takes care of how the information is displayed

        if role == QtCore.Qt.DisplayRole:                               # how to display each cell
            value = ''
            row = index.row()
            column = index.column()
            if column == 0:
                return self.__serviceNames[row]['name']

    def flags(self, index):                                             # method that allows views to know how to treat each item, eg: if it should be enabled, editable, selectable etc
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable

    def sort(self, Ncol, order):                                        # sort function called when the user clicks on a header
        
        self.layoutAboutToBeChanged.emit()
        array = []
        
        if Ncol == 0:                                                   # if sorting by service name (and by default)
            for i in range(len(self.__serviceNames)):
                array.append(self.__serviceNames[i]['name'])

        sortArrayWithArray(array, self.__serviceNames)                  # sort the services based on the values in the array

        if order == Qt.AscendingOrder:                                  # reverse if needed
            self.__serviceNames.reverse()   
            
        self.layoutChanged.emit()                            # update the UI (built-in signal)

    ### getter functions ###

    def getServiceNameForRow(self, row):
        return self.__serviceNames[row]['name']

    def getRowForServiceName(self, serviceNames):
        for i in range(len(self.__serviceNames)):
            if self.__serviceNames[i]['name'] == serviceNames:
                return i
