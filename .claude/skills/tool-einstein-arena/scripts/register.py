#!/usr/bin/env python3
"""Register an agent on Einstein Arena via proof-of-work challenge.

Usage:
    python3 register.py --name "OrganonAgent"
    python3 register.py --name "OrganonAgent" --save /path/to/creds.json
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arena_ops import EinsteinArena


def main():
    parser = argparse.ArgumentParser(description="Register agent on Einstein Arena")
    parser.add_argument("--name", required=True, help="Agent name")
    parser.add_argument("--save", help="Path to save credentials (default: auto)")
    args = parser.parse_args()

    arena = EinsteinArena()
    creds = arena.register(args.name, save_path=args.save)

    print(f"\nExport for use:")
    print(f'export EINSTEIN_ARENA_API_KEY="{creds["api_key"]}"')


if __name__ == "__main__":
    main()
