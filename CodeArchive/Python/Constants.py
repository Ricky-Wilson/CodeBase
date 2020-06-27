from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from __future__ import unicode_literals

VERSION="2.0.8"
PACKAGE="blueman"
WEBSITE="https://github.com/blueman-project/blueman"
PREFIX="/usr"
BIN_DIR="/usr/bin"
ICON_PATH = "/usr/share/icons"
PIXMAP_PATH = "/usr/share/pixmaps/blueman"
UI_PATH = "/usr/share/blueman/ui"
OBEX_BROWSE_AVAILABLE = True
DHCP_CONFIG_FILE = "/etc/dhcp/dhcpd.conf"
POLKIT = "no" == "yes"

import os
import gettext
try: import __builtin__ as builtins
except ImportError: import builtins

translation = gettext.translation("blueman", "/usr/share/locale", fallback=True)
try:
    translation.install(unicode=True)
    builtins.ngettext = translation.ungettext
except TypeError:
    translation.install()
    builtins.ngettext = translation.ngettext

if os.path.exists("../apps") and os.path.exists("../data"):
	BIN_DIR = "./"
	ICON_PATH = "../data/icons"
	PIXMAP_PATH = "../data/icons/pixmaps"
	UI_PATH = "../data/ui"
