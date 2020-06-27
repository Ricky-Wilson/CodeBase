from pathlib import Path
import bisect

#size = [1, 1e+3, 1e+6, 1e+9]
size = [1, 2**10, 2**20, 2**30]
unit = ['B', 'K', 'M', 'G']
fpath = input('Enter file name: ') 
fsize = Path(fpath).stat().st_size

def convert(byts):
    if byts != 0:
        index = bisect.bisect(size, byts) -1
        return f'{byts/size[index]:.1f}{unit[index]}'
    else: 
        return '0B'
print(f'{convert(fsize)} {fpath}')