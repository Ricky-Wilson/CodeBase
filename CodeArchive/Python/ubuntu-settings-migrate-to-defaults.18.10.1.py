#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Copyright (C) 2018 Canonical
#
# Authors:
#  Marco Trevisan <marco.trevisan@canonical.com>
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUTa
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

from gi.repository import Gio
import os
import sys

OLD_DEFAULTS = {
    "org.gnome.desktop.sound": {
        "theme-name": ["ubuntu"],
    },
    "org.gnome.desktop.interface": {
        "gtk-theme": ["Ambiance", "Radiance"],
        "icon-theme": ["ubuntu-mono-dark"],
        "cursor-theme": ["DMZ-White"],
    }
}

if os.getenv('DESKTOP_SESSION') not in ['ubuntu', 'ubuntu-wayland']:
    sys.exit(0)

any_changed = False

for schema in OLD_DEFAULTS.keys():
    settings = Gio.Settings.new(schema)
    old_settings = OLD_DEFAULTS[schema]

    for key in old_settings.keys():
        user_value = settings.get_user_value(key)

        if user_value and user_value.unpack() in old_settings[key]:
            print('{}.{} is using old ubuntu setting ("{}"), replacing it with '
                'the latest default ("{}")'.format(schema, key,
                    user_value.unpack(),
                    settings.get_default_value(key).unpack()))
            settings.reset(key)
            any_changed = True

if any_changed:
    Gio.Settings.sync()

