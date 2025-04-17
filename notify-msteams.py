#!/usr/bin/env python3
#
# Michael Cone
#

import argparse
import json
import os
import requests
from datetime import datetime
from jinja2 import Environment, PackageLoader, select_autoescape
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

NAGIOS_URL = "http://nagios.my.lan/cgi-bin/nagios3"
#XI url is just going to be 'http://nagios.my.lan' with no trailing slash

now = datetime.now()
current_time = now.strftime("%H:%M:%S")

env = Environment(
    loader=PackageLoader("notify-msteams"),
    autoescape=select_autoescape()
)

nag_template = {
    'HOST' : 'host.json.jinja',
    'SERVICE' : 'service.json.jinja',
	'XI_HOST' : 'xi_host.json.jinja',
    'XI_SERVICE' : 'xi_service.json.jinja',
    # 'HOST' : 'host_simple.json.jinja',
    # 'SERVICE' : 'service_simple.json.jinja',
}

# XI does some URLEncoding on part of the powerautomate URLs - Fix it!
def fix_xi_power_automate_url(broken_url):
    parsed = urlparse(broken_url)
    
    # Try to recover the query string manually by inserting missing ampersands
    # Look for common param keys to split on
    raw_query = parsed.query
    for key in ['&sp=', '&sv=', '&sig=']:
        raw_query = raw_query.replace(key.replace('&', ''), key)
    
    # Now parse into key-value pairs
    query_params = dict(parse_qsl(raw_query))

    # Reconstruct the fixed URL
    fixed_query = urlencode(query_params, doseq=True)
    fixed_url = urlunparse(parsed._replace(query=fixed_query))

    return fixed_url

def _get_nagios_macros(debug):
    """Read all ENV vars then save and rename the Nagios Macros in a dictionary."""
    MACROS=dict()
    for k, v in sorted(os.environ.items()):
        if k.startswith('NAGIOS_'):
            if debug: #output all env vars read by the script
                print('env var: {} = {}'.format(k, v))
            k = k.replace('NAGIOS_', '')
            MACROS[k] = v
    # Inject Nagios location for template base url.
    MACROS.update({'nagios_url': NAGIOS_URL})
    return MACROS

def send_to_teams(url, message_json, debug):
    """ posts the json message to the ms teams webhook url """
    headers = {'Content-Type': 'application/json'}
    r = requests.post(url, data=message_json, headers=headers)
    if debug: #show status codes
        print('Status code: {}'.format(r.status_code))
    if r.status_code == requests.codes.ok or r.status_code == requests.codes.accepted:
        if debug:
            print('success')
        return True
    else:
        if debug:
            print('failure: {}'.format(r.reason))
        return False

def main():
    """receive nagios environment data and send notifications via MS-Teams"""

    parser = argparse.ArgumentParser()
    parser.add_argument('msgtype', action='store', help='message subject')
    parser.add_argument('--debug', action='store_true', help='print json message, etc. for debugging')
    parsedArgs = parser.parse_args()

    message_type = parsedArgs.msgtype
    debug = parsedArgs.debug
    macros = _get_nagios_macros(debug)
    url = macros.get('_CONTACTWEBHOOKURL')
    if "azure" in url and "XI" in message_type:
        if debug:
            print('Azure URL detected, fixing it')
        url = fix_xi_power_automate_url(url)
    if debug:
        print(url)
    # verify url defined
    if url is None:
        # error no url
        print('ERROR: no ms-teams webhook url was found')
        exit(2)

    # get the Jinja template for "HOST" or "SERVICE" or "XI_HOST" or "XI_SERVICE"
    t = env.get_template(nag_template.get(message_type))
    message_json = t.render(**macros)
    if debug:
        print(message_json + '\n\n--> ' + current_time )
    send_to_teams(url, message_json, debug)


if __name__=='__main__':
    main()
