#!/usr/bin/env python3
# Create a public download link for any of my Github Actions artifacts.
# Optionally download the zip file.
# Written & released by Keir Fraser <keir.xen@gmail.com>

import re, sys
import requests

# Latest artifact webpage:
# https://nightly.link/keirf/FlashFloppy/workflows/ci/master

# Github Actions artifact link and corrsponding public link:
# https://github.com/keirf/FlashFloppy/suites/1623687905/artifacts/29859161
# https://nightly.link/keirf/FlashFloppy/actions/artifacts/29859161

def print_usage():
    print('artifact.py [-d] <github_artifact_url>')
    sys.exit(0)

if not(2 <= len(sys.argv) <= 3):
    print_usage()
if len(sys.argv) == 3:
    if sys.argv[1] != '-d':
        print_usage()
    download = True
    url = sys.argv[2]
else:
    download = False
    url = sys.argv[1]

url = re.sub(r'github.com', 'nightly.link', url)
url = re.sub(r'suites/\d+', 'actions', url)
url += '.zip'
print(url)

if download:
    res = requests.get(url)
    content_disposition = res.headers['Content-Disposition']
    zipname = re.search(r'filename=([^ ]+.zip);', content_disposition).group(1)
    print('Downloading to: ' + zipname)
    with open(zipname, 'wb') as f:
        f.write(res.content)
