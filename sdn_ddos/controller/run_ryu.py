"""Launch Ryu 4.34 with the small Eventlet compatibility shim it requires.

Ryu 4.34 imports ``eventlet.wsgi.ALREADY_HANDLED``.  Eventlet 0.36 removed
that sentinel while retaining the surrounding WSGI API.  Defining the sentinel
before Ryu imports it keeps the legacy controller usable without modifying any
installed third-party package.
"""

from __future__ import annotations

import eventlet.wsgi


if not hasattr(eventlet.wsgi, "ALREADY_HANDLED"):
    eventlet.wsgi.ALREADY_HANDLED = object()

from ryu.cmd.manager import main


if __name__ == "__main__":
    main()
