
import sys, os

# Update the search path and import the real script
sys.path[0] = os.path.join(sys.path[0], "scripts")
import gw

# Execute the real script
gw.main(sys.argv)
