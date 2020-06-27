#!/usr/bin/python3
__version__ = '2.2'
__mod__ = 'hp-uiscan'
__title__ = 'Scan Utility'
__doc__ = "SANE-based scan utility for HPLIP supported all-in-one/mfp devices."

from base import utils, module
#from installer import core_install
import os
from math import log
from base.g import *
import operator
try:
    from importlib import import_module
except ImportError as e:
    log.debug(e)
    from base.utils import dyn_import_mod as import_module


#from scan import sane
#import scanext



#mod = module.Module(__mod__, __title__, __version__, __doc__, None, (INTERACTIVE_MODE,))
mod = module.Module(__mod__, __title__, __version__, __doc__, None, (GUI_MODE,), (UI_TOOLKIT_QT4, UI_TOOLKIT_QT5))
mod.setUsage(module.USAGE_FLAG_NONE, extra_options=None, see_also_list = ['hp-scan'])



if __name__ == "__main__":

    opts, device_uri, printer_name, mode, ui_toolkit, lang=mod.parseStdOpts()
    #print (device_uri)
    #device_uri = mod.getDeviceUri(device_uri, printer_name, back_end_filter=['hpaio'], filter={'scan-type': (operator.gt, 0)}, devices=devicelist)
    #print (device_uri)
    '''try:
        #print (device_uri)
        device = sane.openDevice(device_uri)
        #print (device)
    except scanext.error as e:
        #sane.reportError(e.args[0])
        #sys.exit(1)'''


    #k=core_install.CoreInstall()
    #k.get_distro()
    #print k.distro_name
    #print k.distro_version
    #ui_toolkit = k.get_distro_ver_data('ui_toolkit').lower()
    '''if ui_toolkit == 'qt4':
        os.system('python ui4/scan.py')
    elif ui_toolkit == 'qt5':
        os.system('python ui5/scan.py')'''

    QApplication, ui_package = utils.import_dialog(ui_toolkit)

    ui = import_module(ui_package + ".scandialog")

    obj=ui.SetupDialog()
    #obk=obj.setupUi(devicelist)
    obj.setupUi()
    #print obk


    '''list_scanjet=imageprocessing.validate_scanjet_support()
    #print (list_scanjet)
    if(list_scanjet[2] == 'False'):
        scanjet_error="Scanjet features are not supported and disabled for %s %s. Please upgrade to latest distro version"% (list_scanjet[0],list_scanjet[1])
        ui.failureMessage(scanjet_error)
        ui.DisableAllScanjet()    '''    
    #obk[0].show()
    #sys.exit(obk[1].exec_())

