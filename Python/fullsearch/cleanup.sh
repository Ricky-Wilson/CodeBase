


black *.py
isort -m 3 -tc

pylint3 | less
python3 -m mccabe *.py | less

python3 -m cProfile -o program.prof *.py

tuna programe.prof
