#!/usr/bin/env python3
"""
Craps Simulator - Main Entry Point

A comprehensive craps simulator with GUI for testing and analyzing craps strategies.
"""

from craps.table_gui import run_table_gui


def main():
    """Launch the craps simulator."""
    print("Starting Craps Simulator...")
    print("=" * 40)
    print("Features:")
    print("  - Visual craps table with purple theme")
    print("  - Draggable chips ($1, $5, $25, $100, $500)")
    print("  - All standard bet types")
    print("  - Correct pay tables")
    print("=" * 40)
    print()
    print("Controls:")
    print("  - Left-click on chip to select denomination")
    print("  - Left-click on table to place chips")
    print("  - Right-click on betting spot to remove chips")
    print("=" * 40)
    run_table_gui()


if __name__ == "__main__":
    main()
