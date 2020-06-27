from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library

standard_library.install_aliases()
from builtins import input
from builtins import *
import random
import os


def random_number():
    return random.randint(1, 10)


def guess():
    os.system("clear")
    return int(eval(input("Guess a number between 1-10: ")))


def game():
    while True:
        if guess() == random_number():
            print("You got it :)")
            break
        else:
            print("You suck :( ")


game()
