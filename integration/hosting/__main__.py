"""`python -m integration.hosting start|status` (see the package docstring)."""
import sys

from integration.hosting import main

sys.exit(main(sys.argv[1:]))
