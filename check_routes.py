#!/usr/bin/env python3

import sys
sys.path.append('/app/backend')

from server import app

print("Available routes:")
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        print(f"{route.methods} {route.path}")
    elif hasattr(route, 'path'):
        print(f"MOUNT {route.path}")