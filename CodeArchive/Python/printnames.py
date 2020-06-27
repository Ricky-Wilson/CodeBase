

from nltk import corpus
from subprocess import getoutput
import random
import sys
from time import sleep

def speak(this):
    print(this)
    getoutput(f'espeak {this}')


names = corpus.names.words()
random.shuffle(names)

for name in names:
   for char in name:
       sys.stdout.write(char)
       sys.stdout.flush()
       sleep(0.2)
   print('\n')
   sleep(0.7)
