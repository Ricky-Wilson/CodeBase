"""
Faraday Penetration Test IDE
Copyright (C) 2016  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information
"""
from faraday.client.persistence.server import models
from faraday.utils.user_input import query_yes_no

__description__ = 'Deletes all services with a non open port'
__prettyname__ = 'Delete All Service Closed'


def main(workspace='', args=None, parser=None):
    parser.add_argument('-y', '--yes', action="store_true")
    parsed_args = parser.parse_args(args)
    if not parsed_args.yes:

        if not query_yes_no("Are you sure you want to delete all closed services in the "
                            "workspace %s" % workspace, default='no'):
            return 1, None

    for service in models.get_services(workspace):
        if service.status != 'open' and service.status != 'opened':
            print('Deleted service: ' + service.name)
            models.delete_service(workspace, service.id)
    return 0, None


# I'm Py3
