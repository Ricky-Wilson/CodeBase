from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from __future__ import unicode_literals

import dbus.service
import os
import subprocess
import signal
from blueman.plugins.MechanismPlugin import MechanismPlugin


class Rfcomm(MechanismPlugin):
    files = {}

    @dbus.service.method('org.blueman.Mechanism', in_signature="d")
    def open_rfcomm(self, port_id):
        subprocess.Popen(['/usr/lib/blueman/blueman-rfcomm-watcher', '/dev/rfcomm%d' % port_id])

    @dbus.service.method('org.blueman.Mechanism', in_signature="d")
    def close_rfcomm(self, port_id):
        command = 'blueman-rfcomm-watcher /dev/rfcomm%d' % port_id

        out, err = subprocess.Popen(['ps', '-e', 'o', 'pid,args'], stdout=subprocess.PIPE).communicate()
        for line in out.decode('utf-8').splitlines():
            if command in line:
                os.kill(int(line.split(None, 1)[0]), signal.SIGTERM)
