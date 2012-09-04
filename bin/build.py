#!/usr/bin/env python
"""
build.py - Combine (and minify) javascript files in js directory.
"""

import re
import os
import sys
import stat
import hmac
import hashlib
import urllib
import urllib2
from base64 import b64encode
from datetime import datetime
from fnmatch import fnmatch
import json

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(ROOT_PATH, 'app')
sys.path.insert(0, APP_PATH)

import settings
import includes

# See http://code.google.com/closure/compiler/docs/gettingstarted_api.html
CLOSURE_API = 'http://closure-compiler.appspot.com/compile'



def update_manifest(explicit=False):
    """
    Update the manifest file AUTOGENERATED secion.  We do this on
    each application upload in case any files have changed that
    require a new manifest file be written.
    """
    if not os.path.exists(MANIFEST_FILENAME):
        return

    manifest_file = open(MANIFEST_FILENAME, 'r')
    parts = manifest_file.read().partition('\n' + AUTOGEN_LINE)
    manifest_file.close()
    if parts[1] == '':
        if explicit:
            print "%s has no AUTOGENERATE section" % MANIFEST_FILENAME
        return

    commands = [line for line in parts[2].split('\n') if line.startswith('#!')]
    excludes = []
    for command in commands:
        match = re.match(r'#!\s*EXCLUDE:\s*(.*)\s*$', command)
        if options.verbose:
            print "Excluding paths beginning with '%s'" % match.group(1)
        if match:
            excludes.extend(re.split(r",\s*", match.group(1)))

    cached_files = []
    hash_lines = []

    paths = options.local_listing.keys()
    paths.sort()
    size = 0
    for path in paths:
        info = options.local_listing[path]
        if path == MANIFEST_FILENAME or path == META_FILENAME or \
            info['size'] > MAX_FILE_SIZE or \
            is_data_path(path) or \
            prefix_match(excludes, path):
            continue
        cached_files.append(path)
        hash_lines.append("%s=%s" % (path, info['sha1']))
        size += info['size']

    manifest_lines = [parts[0], AUTOGEN_LINE, AUTOGEN_EXPLAIN]
    manifest_lines.extend(commands)
    manifest_lines.extend((
            "# TOTAL FILES: %s (%s bytes)" % (intcomma(len(cached_files)), intcomma(size)),
            "# SIGNATURE: %s" % hashlib.sha1('\n'.join(hash_lines)).hexdigest(),
            "CACHE:",
            ))
    manifest_lines.extend(cached_files)

    manifest_file = open(MANIFEST_FILENAME, 'w')
    manifest_file.write('\n'.join(manifest_lines) + '\n')
    manifest_file.close()

    # Make sure the listing for the manifest file is up to date
    # so it will be uploaded if changed.
    update_local_listing(MANIFEST_FILENAME)


def offline_command(args):
    """
    Build an app.manifest file to enable your application to be used offline.
    See http://diveintohtml5.org/offline.html for details on using a manifest in your application.
    """

    list_local_files()

    if os.path.exists(MANIFEST_FILENAME) and not options.force:
        print "%s already exists (use -f to overwrite)." % MANIFEST_FILENAME

    if not os.path.exists(MANIFEST_FILENAME) or options.force:
        print "Creating file %s." % MANIFEST_FILENAME
        default_manifest = (
            "CACHE MANIFEST\n"
            "# Cache files for offline access - see http://diveintohtml5.org/offline.html\n"
            "\n"
            "/lib/beta/js/pf-client.min.js\n"
            "/lib/beta/css/client.css\n"
            "/static/images/appbar/green-left.png\n"
            "/static/images/appbar/green-center.png\n"
            "/static/images/appbar/green-right.png\n"
            "/static/images/appbar/down.png\n"
            "/static/images/appbar/logo.png\n"
            "\n"
            "NETWORK:\n"
            "*\n\n"
            )
        manifest = open(MANIFEST_FILENAME, 'w')
        manifest.write(default_manifest + AUTOGEN_LINE)
        manifest.close()
        print default_manifest + AUTOGEN_LINE

    update_manifest(True)


def print_closure_messages(json, prop):
    if prop not in json:
        return

    print "Closure %s:" % prop
    for message in json[prop]:
        print "%d:%d: %s" % (message['lineno'], message['charno'],
                             message.get('error', '') + message.get('warning', ''))


HASH_PREFIX = '/* Source hash: %s */\n'

def closure_compiler(js_code):
    params = [
        ('compilation_level', 'SIMPLE_OPTIMIZATIONS'),
        ('output_info', 'compiled_code'),
        ('output_info', 'errors'),
        ('output_info', 'warnings'),
        ('output_info', 'statistics'),
        ('output_format', 'json'),
    ]

    params.append(('js_code', js_code))
    data = urllib.urlencode(params)
    output = urllib2.urlopen(CLOSURE_API, data).read()
    output = json.loads(output)

    print_closure_messages(output, 'errors')
    # print_closure_messages(output, 'warnings')

    return (HASH_PREFIX % hashlib.sha256(js_code).hexdigest()) + output['compiledCode']


def combine_javascript(base_dir):
    paths = includes.script_paths(base_dir)
    js_dir = os.path.join(APP_PATH, base_dir)

    js_code = ''
    for file_name in paths:
        base_name = os.path.split(file_name)[-1]
        with open(os.path.join(js_dir, file_name)) as js_file:
            js_code += "\n/* %s */\n" % base_name
            js_code += js_file.read()

    print "Combining files into %s/combined.js." % js_dir
    with open(os.path.join(js_dir, 'combined.js'), 'w') as combined_file:
        combined_file.write(js_code)

    print "Combining files into %s/combined-min.js." % js_dir
    with open(os.path.join(js_dir, 'combined-min.js'), 'w') as combined_min_file:
        minified = closure_compiler(js_code)
        combined_min_file.write(minified)


def main():
    combine_javascript('js')
    combine_javascript('rest/js')


if __name__ == '__main__':
    main()
