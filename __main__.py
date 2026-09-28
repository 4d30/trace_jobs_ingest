#!/usr/bin/env python

import sys 
import traceback

from .conductor import main 

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
