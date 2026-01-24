"""
Pre-built craps betting strategies.

This package contains example strategies demonstrating different
betting approaches and risk profiles.
"""
from .pass_odds import PassLineWithOddsStrategy
from .iron_cross import IronCrossStrategy
from .dont_pass import DontPassStrategy
from .place_68 import Place68Strategy
from .regress_and_press import RegressAndPressStrategy

__all__ = [
    'PassLineWithOddsStrategy',
    'IronCrossStrategy',
    'DontPassStrategy',
    'Place68Strategy',
    'RegressAndPressStrategy',
]
