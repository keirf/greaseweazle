
# Send a command over telnet to remote host:
#  telnet.py <host> <port> <string>

import sys
import telnetlib

with telnetlib.Telnet(sys.argv[1], sys.argv[2]) as t:
    t.write((sys.argv[3] + '\n').encode('utf-8'))
