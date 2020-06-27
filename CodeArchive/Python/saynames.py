

from nltk import corpus
from subprocess import getoutput
import random

def speak(this):
    print(this)
    getoutput(f'espeak {this}')


names = corpus.names.words()
random.shuffle(names)

for name in names:
    speak(name)
