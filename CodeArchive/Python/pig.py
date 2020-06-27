
import androidhelper
import os


droid = androidhelper.Android()

def translate(text):
    return ' '.join('{}{}{}'.format(word, word[0], 'say')[1:] for word in text.split())


banner = '''
Driftwood's pig latin 
translater.
'''
os.system('clear')
print(banner)
while 1:
    word = input('Enter some words: ')
    if word == 'quit':
        break
    if word == 'clear':
        os.system('clear')
        word = ''
    translated = translate(word)
    print(translated)
    droid.ttsSpeak(translate(word))