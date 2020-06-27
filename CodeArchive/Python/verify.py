#!/usr/bin/env python3
#
# verify.py - part of the FDroid server tools
# Copyright (C) 2013, Ciaran Gultnieks, ciaran@ciarang.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import os
import glob
import json
import logging
import requests
from argparse import ArgumentParser
from collections import OrderedDict

from . import _
from . import common
from . import net
from . import update
from .exception import FDroidException

options = None
config = None


class hashabledict(OrderedDict):
    def __key(self):
        return tuple((k, self[k]) for k in sorted(self))

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()

    def __lt__(self, other):
        return self.__key() < other.__key()

    def __qt__(self, other):
        return self.__key() > other.__key()


class Decoder(json.JSONDecoder):
    def __init__(self, **kwargs):
        json.JSONDecoder.__init__(self, **kwargs)
        self.parse_array = self.JSONArray
        # Use the python implemenation of the scanner
        self.scan_once = json.scanner.py_make_scanner(self)

    def JSONArray(self, s_and_end, scan_once, **kwargs):
        values, end = json.decoder.JSONArray(s_and_end, scan_once, **kwargs)
        return set(values), end


class Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return sorted(obj)
        return super().default(obj)


def write_json_report(url, remote_apk, unsigned_apk, compare_result):
    """write out the results of the verify run to JSON

    This builds up reports on the repeated runs of `fdroid verify` on
    a set of apps.  It uses the timestamps on the compared files to
    ensure that there is only one report per file, even when run
    repeatedly.

    """

    jsonfile = unsigned_apk + '.json'
    if os.path.exists(jsonfile):
        with open(jsonfile) as fp:
            data = json.load(fp, object_pairs_hook=OrderedDict)
    else:
        data = OrderedDict()
    output = hashabledict()
    output['url'] = url
    for key, filename in (('local', unsigned_apk), ('remote', remote_apk)):
        d = hashabledict()
        output[key] = d
        d['file'] = filename
        d['sha256'] = update.sha256sum(filename)
        d['timestamp'] = os.stat(filename).st_ctime
        d['packageName'], d['versionCode'], d['versionName'] = common.get_apk_id(filename)
    if compare_result:
        output['verified'] = False
        output['result'] = compare_result
    else:
        output['verified'] = True
    data[str(output['local']['timestamp'])] = output  # str makes better dict keys than float
    with open(jsonfile, 'w') as fp:
        json.dump(data, fp, sort_keys=True)

    if output['verified']:
        jsonfile = 'unsigned/verified.json'
        if os.path.exists(jsonfile):
            with open(jsonfile) as fp:
                data = json.load(fp, cls=Decoder, object_pairs_hook=hashabledict)
        else:
            data = OrderedDict()
            data['packages'] = OrderedDict()
        packageName = output['local']['packageName']
        if packageName not in data['packages']:
            data['packages'][packageName] = set()
        data['packages'][packageName].add(output)
        with open(jsonfile, 'w') as fp:
            json.dump(data, fp, cls=Encoder, sort_keys=True)


def main():

    global options, config

    # Parse command line...
    parser = ArgumentParser(usage="%(prog)s [options] [APPID[:VERCODE] [APPID[:VERCODE] ...]]")
    common.setup_global_opts(parser)
    parser.add_argument("appid", nargs='*', help=_("applicationId with optional versionCode in the form APPID[:VERCODE]"))
    parser.add_argument("--reuse-remote-apk", action="store_true", default=False,
                        help=_("Verify against locally cached copy rather than redownloading."))
    parser.add_argument("--output-json", action="store_true", default=False,
                        help=_("Output JSON report to file named after APK."))
    options = parser.parse_args()

    config = common.read_config(options)

    tmp_dir = 'tmp'
    if not os.path.isdir(tmp_dir):
        logging.info(_("Creating temporary directory"))
        os.makedirs(tmp_dir)

    unsigned_dir = 'unsigned'
    if not os.path.isdir(unsigned_dir):
        logging.error(_("No unsigned directory - nothing to do"))
        sys.exit(0)

    verified = 0
    notverified = 0

    vercodes = common.read_pkg_args(options.appid, True)

    for apkfile in sorted(glob.glob(os.path.join(unsigned_dir, '*.apk'))):

        apkfilename = os.path.basename(apkfile)
        url = 'https://f-droid.org/repo/' + apkfilename
        appid, vercode = common.publishednameinfo(apkfile)

        if vercodes and appid not in vercodes:
            continue
        if vercodes[appid] and vercode not in vercodes[appid]:
            continue

        try:

            logging.info("Processing {apkfilename}".format(apkfilename=apkfilename))

            remote_apk = os.path.join(tmp_dir, apkfilename)
            if not options.reuse_remote_apk or not os.path.exists(remote_apk):
                if os.path.exists(remote_apk):
                    os.remove(remote_apk)
                logging.info("...retrieving " + url)
                try:
                    net.download_file(url, dldir=tmp_dir)
                except requests.exceptions.HTTPError:
                    try:
                        net.download_file(url.replace('/repo', '/archive'), dldir=tmp_dir)
                    except requests.exceptions.HTTPError as e:
                        raise FDroidException(_('Downloading {url} failed. {error}')
                                              .format(url=url, error=e))

            unsigned_apk = os.path.join(unsigned_dir, apkfilename)
            compare_result = common.verify_apks(remote_apk, unsigned_apk, tmp_dir)
            if options.output_json:
                write_json_report(url, remote_apk, unsigned_apk, compare_result)
            if compare_result:
                raise FDroidException(compare_result)

            logging.info("...successfully verified")
            verified += 1

        except FDroidException as e:
            logging.info("...NOT verified - {0}".format(e))
            notverified += 1

    if verified > 0:
        logging.info("{0} successfully verified".format(verified))
    if notverified > 0:
        logging.info("{0} NOT verified".format(notverified))
    sys.exit(notverified)


if __name__ == "__main__":
    main()
