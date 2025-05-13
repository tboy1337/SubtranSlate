#!/usr/bin/env python3
"""
Entry point to run SubtranSlate directly from source code without installation.
This allows users to download the source code and run it directly.
"""

import sys
import os
import argparse

# Ensure parent directory is in the path
# This allows importing the package directly from source
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Import the package version
from src.subtranslate import __version__

def main():
    """Entry point when executed directly."""
    parser = argparse.ArgumentParser(
        description=f"SubtranSlate v{__version__} - A tool for translating subtitle files."
    )
    parser.add_argument('--version', action='store_true',
                      help='Print version and exit')
    parser.add_argument('remainder', nargs=argparse.REMAINDER,
                      help='Arguments to pass to subcommand')
    
    args = parser.parse_args(args=None if sys.argv[1:] else ['--help'])
    
    if args.version:
        print(f"SubtranSlate v{__version__}")
        return 0
    
    # Import CLI main function
    from src.subtranslate.cli import main as cli_main
    return cli_main(args.remainder)

if __name__ == '__main__':
    sys.exit(main()) 