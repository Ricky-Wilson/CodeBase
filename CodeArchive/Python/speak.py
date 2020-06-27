"""Speak user generated text."""

__author__ = 'Damon Kohler <damonkohler@gmail.com>'
__copyright__ = 'Copyright (c) 2009, Google Inc.'
__license__ = 'Apache License, Version 2.0'

import androidhelper

droid = androidhelper.Android()
message = droid.dialogGetInput('TTS', 'What would you like to say?').result
droid.ttsSpeak(message)
