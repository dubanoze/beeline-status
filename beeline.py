#!/usr/bin/python3

##
# Beeline Status
# Script to get balance and data allowance from my.beeline.ru
# Use the same credentials from my.beeline.ru
#
# Author: Grigoriy Kraynov (github@gkraynov.com)
# (c) 2015, MIT License

import os
import sys
import getpass
import pickle
import locale
import datetime

from http.client import HTTPSConnection
from urllib.parse import urlencode


class BeelineCabinet:
    def __init__(self, session_file=None):
        self.host = 'my.beeline.ru'
        self.cookies = {}
        self.state = None
        self.session_file = session_file

    def auth(self, login, password):
        # Invalidate authentication
        self.cookies = None
        index = None

        # Read session file and verify authentication
        if self.session_file and os.path.exists(self.session_file):
            fd = open(self.session_file, 'rb')
            self.cookies = pickle.load(fd)
            fd.close()

            # Try to load the cabinet
            try:
                index = self.request('GET /c/pre/index.xhtml', redirects=0)
            except:
                self.cookies = None

        # Not authenticated
        if not self.cookies:
            self.cookies = {}
            self.request('GET /')
            params = {
                'selectMobileLk': '1',
                'javax.faces.ViewState': 'stateless',
                'loginFormB2C:loginForm': 'loginFormB2C:loginForm',
                'loginFormB2C:loginForm:loginButton': '',
                'loginFormB2C:loginForm:login': login,
                'loginFormB2C:loginForm:password': password
            }
            index = self.request('POST /login.xhtml', params)

        # Get view state
        if index:
            index = index.split('id="j_id1:javax.faces.ViewState:0"')[1].split('/>')[0]
            self.state = index.split('value="')[1].split('"')[0]
        else:
            raise PermissionError('Authentication failed')

        if self.state == 'stateless':
            raise PermissionError('Authentication failed')

        # Write session to file
        if self.session_file:
            try:
                fd = open(self.session_file, 'wb')
                os.chmod(self.session_file, 0o600)
                pickle.dump(self.cookies, fd)
                fd.close()
            except:
                pass

    def get_balance(self):
        params = {
            'javax.faces.partial.render': 'j_idt1245:homeBalance',

            'javax.faces.source': 'j_idt1245:j_idt1247:j_idt1248',
            'j_idt1245:j_idt1247:j_idt1248': 'j_idt1245:j_idt1247:j_idt1248',
            'j_idt1245:j_idt1247': 'j_idt1245:j_idt1247',

            'javax.faces.partial.execute': '@all',
            'javax.faces.partial.ajax': 'true',
            'javax.faces.ViewState': self.state
        }
        frame = self.request('POST /c/pre/index.xhtml', params)

        val = frame.split('j_idt1467:j_idt1469')[1].split('</div>')[0]
        val = val.split('<span class="rur">')[0].split('span class="price')[1]
        val = val.split('">')[1].strip().replace(',', '.')

        balance = float(val)
        return balance

    def get_data_plan(self):
        params = {
            'javax.faces.partial.render': 'bonusesForm',

            'javax.faces.source': 'j_idt2656:j_idt2658',
            'j_idt2656:j_idt2658': 'j_idt2656:j_idt2658',
            'j_idt2656': 'j_idt2656',

            'javax.faces.partial.execute': '@all',
            'javax.faces.partial.ajax': 'true',
            'javax.faces.ViewState': self.state
        }
        frame = self.request('POST /c/pre/index.xhtml', params)

        vals = frame.split('<div class="val">')[1].split('</div>')[0].strip()
        vals = vals.replace('\xa0', ' ').replace(',', '.').split(' ')
        vals = list(filter(lambda x: len(x) and x[0].isdigit(), vals))

        data_allowance = float(vals[0])
        data_package = float(vals[1])

        return data_allowance, data_package

    def request(self, request, params=None, redirects=5):
        http_method = request.split(' ', 1)[0]
        http_location = request.split(' ', 1)[1]

        http_cookie = ''
        for name in self.cookies:
            http_cookie += '; ' + name + '=' + self.cookies[name]
        http_cookie = http_cookie[2:]

        http_headers = {'Host': self.host, 'Cookie': http_cookie}
        if http_method == 'POST':
            http_headers['Content-type'] = 'application/x-www-form-urlencoded'
            http_headers['Accept'] = 'text/plain'
            http_data = urlencode(params).encode('ascii')
        else:
            http_data = None

        # WARNING!
        # Certificate verification depends on your Python version and/or your system
        conn = HTTPSConnection(self.host)

        conn.request(http_method, http_location, http_data, http_headers)
        http_response = conn.getresponse()
        http_response_headers = http_response.getheaders()
        http_response_data = http_response.read().decode('utf-8')

        conn.close()

        self.set_cookies(http_response_headers)

        if http_response.status == 302 and (redirects > 0):
            location = list(filter(lambda x: x[0] == 'Location', http_response_headers))
            location = location[0][1].split(self.host, 1)[1]
            return self.request('GET {0}'.format(location), {}, redirects - 1)
        else:
            assert http_response.status == 200
            return http_response_data

    def set_cookies(self, response_headers):
        for record in response_headers:
            if record[0] == 'Set-Cookie':
                cookie = record[1].split('; ')[0].split('=', 1)
                if cookie[1] != '':
                    self.cookies[cookie[0]] = cookie[1]


def main(login=None, password=None, no_session=True, no_print=False):
    # Get arguments
    if login is None:
        if len(sys.argv) == 2:
            login = sys.argv[1]
            password = getpass.getpass()
        elif len(sys.argv) == 3:
            login = sys.argv[1]
            password = sys.argv[2]
        else:
            print('Usage: beeline.py login [password]')
            print('Password will be ignored if session file is valid')
            return

    # Get current date
    if not no_print:
        loc = locale.getlocale()
        locale.setlocale(locale.LC_ALL, 'C')
        date = datetime.datetime.utcnow().strftime("%d %b %Y %H:%M:%S UTC")
        locale.setlocale(locale.LC_ALL, loc)
        print('Date: {0}'.format(date))

    # Sign in to the cabinet
    if no_session:
        session_filename = None
    else:
        session_filename = '{0}.session'.format(login)

    bee = BeelineCabinet(session_filename)
    try:
        bee.auth(login, password)
    except PermissionError:
        print('Authentication failed')

    # Get balance and data allowance
    balance = None
    data_plan = None
    try:
        balance = bee.get_balance()
        data_plan = bee.get_data_plan()
    except:
        pass

    # Print results
    if not no_print:
        if balance:
            print('Account: +7{0}'.format(login))
            print('Balance: {0} RUB'.format(balance))

            if data_plan:
                print('Data plan: {0} GB (out of {1} GB)'.format(data_plan[0], data_plan[1]))
        else:
            print('Balance: Unknown')

    return {'balance': balance,
            'data_plan': data_plan}


if __name__ == '__main__':
    # Alternatively you can pass params to main() and get values directly
    # Set no_session=False to save cookies to file (may cause update delays)
    main()
