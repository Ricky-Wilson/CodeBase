'''apport package hook for mysql-8.0

(c) 2009 Canonical Ltd.
Author: Mathias Gug <mathias.gug@canonical.com>
'''

from __future__ import print_function, unicode_literals
import os, os.path

from apport.hookutils import *

def _add_my_conf_files(report, filename):
    key = 'MySQLConf' + path_to_key(filename)
    report[key] = ""
    for line in read_file(filename).split('\n'):
        try:
            if 'password' in line.split('=')[0]:
                line = "%s = @@APPORTREPLACED@@" % (line.split('=')[0])
            report[key] += line + '\n'
        except IndexError:
            continue

'''
Mitigation for upstream bug that can lead to statements containing passwords being written to error log
We strip out any lines containing terms listed on http://dev.mysql.com/doc/refman/8.0/en/password-logging.html
(LP: #1574458)
'''
def strip_protected(line):
    protected_terms = ['grant', 'alter user', 'create user', 'set password', 'create server', 'alter server']
    for term in protected_terms:
        if term in line:
            return '--- Line containing protected term %s stripped from log by apport hook. Ref. Launchpad bug #1574458' % term
    return line

def add_info(report):
    attach_conffiles(report, 'mysql-server-8.0', conffiles=None)
    key = 'Logs' + path_to_key('/var/log/daemon.log')
    report[key] = ""
    for line in read_file('/var/log/daemon.log').split('\n'):
        try:
            if 'mysqld' in line.split()[4]:
                report[key] += line + '\n'
        except IndexError:
            continue
    if os.path.exists('/var/log/mysql/error.log'):
        key = 'Logs' + path_to_key('/var/log/mysql/error.log')
        report[key] = ""
        for line in read_file('/var/log/mysql/error.log').split('\n'):
            line = strip_protected(line)
            report[key] += line + '\n'
    attach_mac_events(report, '/usr/sbin/mysqld')
    attach_file(report,'/etc/apparmor.d/usr.sbin.mysqld')
    _add_my_conf_files(report, '/etc/mysql/my.cnf')
    _add_my_conf_files(report, '/etc/mysql/mysql.cnf')
    for d in ['/etc/mysql/conf.d', '/etc/mysql/mysql.conf.d']:
        for f in os.listdir(d):
            _add_my_conf_files(report, os.path.join(d, f))
    try:
        report['MySQLVarLibDirListing'] = str(os.listdir('/var/lib/mysql'))
    except OSError:
        report['MySQLVarLibDirListing'] = str(False)

if __name__ == '__main__':
    report = {}
    add_info(report)
    for key in report:
        print('%s: %s' % (key, report[key].split('\n', 1)[0]))
