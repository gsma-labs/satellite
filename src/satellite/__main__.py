"""Entry point for running satellite as a module: ``python -m satellite``.

All multiprocessing and environment guards now live in ``satellite.app.main()``
so they are applied regardless of how the app is launched (console script or
module invocation).
"""

from satellite.app import main

if __name__ == "__main__":
    main()
