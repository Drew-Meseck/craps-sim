"""
Dice roll sequence recording and replay system.

Enables deterministic replay of dice rolls for fair strategy comparison.
"""
import random
from abc import ABC, abstractmethod
from typing import Optional


class DiceProvider(ABC):
    """Abstract interface for dice generation."""

    @abstractmethod
    def roll(self) -> tuple[int, int]:
        """
        Roll two dice.

        Returns:
            tuple[int, int]: (die1, die2) where each is 1-6
        """
        pass


class RandomDiceProvider(DiceProvider):
    """Standard random dice provider using Python's random module."""

    def roll(self) -> tuple[int, int]:
        """Roll two dice randomly."""
        return (random.randint(1, 6), random.randint(1, 6))


class SequenceDiceProvider(DiceProvider):
    """
    Replays dice rolls from a pre-recorded sequence.

    Raises IndexError when sequence is exhausted.
    """

    def __init__(self, sequence: list[tuple[int, int]]):
        """
        Initialize with a dice roll sequence.

        Args:
            sequence: List of (die1, die2) tuples to replay
        """
        self.sequence = sequence
        self.index = 0

    def roll(self) -> tuple[int, int]:
        """
        Return the next roll from the sequence.

        Returns:
            tuple[int, int]: Next (die1, die2) from sequence

        Raises:
            IndexError: If sequence is exhausted
        """
        if self.index >= len(self.sequence):
            raise IndexError(f"Dice sequence exhausted after {self.index} rolls")

        roll = self.sequence[self.index]
        self.index += 1
        return roll

    def reset(self):
        """Reset to beginning of sequence."""
        self.index = 0

    @property
    def remaining(self) -> int:
        """Get number of rolls remaining in sequence."""
        return len(self.sequence) - self.index


class DiceRollSequence:
    """
    Records or generates sequences of dice rolls.

    Can be used to:
    - Record rolls from live gameplay
    - Generate seeded random sequences for reproducibility
    - Replay sequences across multiple strategies for fair comparison
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize a dice roll sequence.

        Args:
            seed: Optional random seed for reproducible generation
        """
        self.rolls: list[tuple[int, int]] = []
        self.seed = seed

    def generate(self, num_rolls: int) -> None:
        """
        Generate a sequence of dice rolls.

        If seed was provided at initialization, uses it for reproducibility.
        Otherwise generates with current random state.

        Args:
            num_rolls: Number of dice rolls to generate
        """
        if self.seed is not None:
            random.seed(self.seed)

        self.rolls = [
            (random.randint(1, 6), random.randint(1, 6))
            for _ in range(num_rolls)
        ]

    def record_roll(self, die1: int, die2: int) -> None:
        """
        Add a roll to the sequence.

        Args:
            die1: Value of first die (1-6)
            die2: Value of second die (1-6)
        """
        self.rolls.append((die1, die2))

    def get_provider(self) -> SequenceDiceProvider:
        """
        Get a provider that replays this sequence.

        Returns a fresh provider starting at the beginning of the sequence.
        Multiple calls return independent providers (each with own index).

        Returns:
            SequenceDiceProvider: Provider configured to replay this sequence
        """
        return SequenceDiceProvider(self.rolls.copy())

    def clear(self) -> None:
        """Clear all recorded rolls."""
        self.rolls.clear()

    def __len__(self) -> int:
        """Get number of rolls in sequence."""
        return len(self.rolls)

    def __repr__(self) -> str:
        return f"DiceRollSequence(rolls={len(self.rolls)}, seed={self.seed})"
