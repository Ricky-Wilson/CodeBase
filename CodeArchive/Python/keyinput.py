from __future__ import division
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from future import standard_library

standard_library.install_aliases()
from builtins import *
from past.utils import old_div
import fcntl
import sys
import os
import curses


def main_loop():
    # initializes a new window for capturing key presses
    screen = curses.initscr()
    screen.addstr("foo")
    curses.curs_set(0)
    screen.keypad(1)
    x, y = screen.getmaxyx()
    screen.addstr(int(old_div((x - 1), 2)), int(old_div(y, 2)) - 10, "(hit q to exit)")
    screen.refresh()
    while 1:
        try:
            char = sys.stdin.read(1)
            if char is "q":
                curses.endwin()
                sys.exit(0)
        except:
            curses.endwin()
            sys.exit(0)


if __name__ == "__main__":
    main_loop()
