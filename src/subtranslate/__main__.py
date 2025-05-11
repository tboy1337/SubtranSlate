#!/usr/bin/env python3
"""
Main entry point for SubtranSlate.
"""

import argparse
import sys
import os

# Add parent directory to path so we can import the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from subtranslate import __version__

def main():
    """Entry point for the application."""
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
    
    # Import here to avoid circular imports
    from subtranslate.cli import main as cli_main
    return cli_main(args.remainder)

if __name__ == '__main__':
    sys.exit(main()) 