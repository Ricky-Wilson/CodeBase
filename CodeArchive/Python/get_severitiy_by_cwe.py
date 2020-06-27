#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Faraday Penetration Test IDE
Copyright (C) 2016  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information
"""
from __future__ import absolute_import
from __future__ import print_function

import json

import requests

from faraday.client.persistence.server import models

__description__ = 'Get Vulns filtered by Severity and change Severity based in CWE'
__prettyname__ = 'Get Severity By CWE'

SEVERITY_OPTIONS = ('unclassified', 'info', 'low', 'med', 'high', 'critical', 'all')


def getCweData(couch_url):
    # Get elements from cwe DB in couchdb
    headers = {'Content-Type': 'application/json'}

    payload = {
        'map':
            'function(doc) { if(doc.severity && doc.name){'
            'emit(doc.name, doc.severity); }}'
    }

    r = requests.post(
        couch_url + '/cwe/_temp_view',
        headers=headers,
        data=json.dumps(payload)
    )

    response_code = r.status_code

    if response_code == 200:

        data = r.json()['rows']
        dict = {}

        for item in data:

            value = item['value']
            if value == 'informational':
                value = 'info'

            dict.update({item['key']: value})

        if dict == {}:
            return None
        else:
            print('Get CWE data: OK\n')
            return dict

    elif response_code == 401:
        print('Autorization required, make sure to add user:pwd to Couch URI')
    else:
        print('Error couchDB: ' + str(response_code) + str(r.text))


def checkSeverity(vuln, cwe_dict, severity_choose, workspace, couch_url):
    severity_dict = {
        'unclassified': 0,
        'info': 1,
        'low': 2,
        'med': 3,
        'high': 4,
        'critical': 5,
        'all': 100
    }

    if vuln._name in cwe_dict and severity_dict[vuln.severity] <= severity_dict[severity_choose]:

        print('Change: ' + vuln._name + ' to ' + cwe_dict[vuln._name])

        # Get object Vuln
        response = requests.get(
            models.server.SERVER_URL + '/' + workspace + '/' + str(vuln._id)
        )
        vulnWeb = response.json()

        # Change severity
        vulnWeb['severity'] = cwe_dict[vuln._name]

        # Put changes...
        headers = {'Content-Type': 'application/json'}
        update = requests.put(
            couch_url + '/' + workspace + '/' + vuln._id,
            headers=headers,
            data=json.dumps(vulnWeb)
        )

        if update.status_code == 200 or update.status_code == 201:
            print('Change OK\n')
        else:
            print('Error in update Vulnerability, status code: ' + str(update.status_code))
            print(update.text)


def main(workspace='', args=None, parser=None):
    parser.add_argument('severity', nargs='?', help='Filter by Severity (<=)', default="info", choices=SEVERITY_OPTIONS)
    parser.add_argument('--couchdb', nargs='?', help='CouchDB URL', default="http://faraday:faraday@localhost:5984")

    parsed_args = parser.parse_args(args)

    cwe = getCweData(parsed_args.couchdb)

    if cwe is None:
        print('CWE DB not downloaded....EXIT')
        return 2, None

    for host in models.get_hosts(workspace):
        for v in host.getVulns():
            checkSeverity(v, cwe, parsed_args.severity, workspace, parsed_args.couchdb)

        for i in host.getAllInterfaces():
            for s in i.getAllServices():
                for v in s.getVulns():
                    checkSeverity(v, cwe, parsed_args.severity, workspace, parsed_args.couchdb)

    return 0, None


# I'm Py3
