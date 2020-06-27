import os


CSVPATH = '/sdcard/Download'
WORKING_DIR = '/sdcard/Download/blokada'
LOGFILE =  'requests.csv'
ACCEPTED = 'a'
BLOCKED = 'b'

os.chdir(WORKING_DIR)


def parse(csvpath=CSVPATH):
    requests = {}
    with open(LOGFILE) as log:
        for line in log.readlines():
            _, result, host = line.split(',')
            host = host.strip('\n')
            if '.' not in host:
                continue

            if result == BLOCKED:
               requests[host] = 'blocked'
            if result == ACCEPTED:
                requests[host] = 'accepted'
                
        return requests

def hosts():
    for host in parse():
        yield host


def accepted():
    for host in parse():
        if host['result'] == 'accepted':
            yield host
        
        
def blocked():
    results = parse()
    for host in results:
        if results[host] == 'blocked':
            yield host


def accepted():
    results = parse()
    for host in results:
        if results[host] == 'accepted':
            yield host


def all_hosts():
    for host in blocked():
        yield host
    for host in accepted():
        yield host


[print(h) for h in hosts()]