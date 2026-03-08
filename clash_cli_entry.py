"""PyInstaller entry point for clash_cli.

Imported by clash_cli.spec as the top-level script; simply delegates
to the normal CLI main() function.
"""
from clash_cli.cli import main

if __name__ == "__main__":
    main()
