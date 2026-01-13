"""
Strategy simulation runner for executing and comparing strategies.

Runs multiple strategies on the same dice sequence for fair comparison.
"""
from dataclasses import dataclass, field
from typing import Optional

from .strategy import Strategy, StrategyBetInterface
from .game import CrapsGame, TableRules, GamePhase
from .bets import BetManager, BetStatus
from .bankroll import BankrollTracker
from .dice_sequence import DiceRollSequence


@dataclass
class SimulationConfig:
    """Configuration for a strategy simulation run."""
    strategies: list[Strategy]
    num_rolls: Optional[int] = None
    num_shooters: Optional[int] = None
    starting_bankroll: float = 1000.0
    table_minimum: float = 5.0
    table_rules: TableRules = field(default_factory=TableRules)
    dice_sequence: Optional[DiceRollSequence] = None
    seed: Optional[int] = None


@dataclass
class StrategyResult:
    """Results for a single strategy run."""
    strategy_name: str
    starting_bankroll: float
    final_equity: float
    net_change: float
    roi_percent: float
    rolls: list[int]
    equity_series: list[float]
    bankroll_tracker: BankrollTracker
    # Detailed statistics
    total_rolls: int = 0
    total_shooters: int = 0
    points_hit: int = 0
    seven_outs: int = 0
    longest_roll: int = 0
    roll_distribution: dict[int, int] = field(default_factory=dict)
    went_bankrupt: bool = False


class StrategyRunner:
    """
    Runs multiple strategies on the same dice sequence.

    Executes strategies in isolation (each gets own game/bet_manager/tracker)
    for fair comparison on identical rolls.
    """

    def __init__(self, config: SimulationConfig):
        """
        Initialize the strategy runner.

        Args:
            config: Simulation configuration
        """
        self.config = config
        self.results: list[StrategyResult] = []
        self.dice_sequence: DiceRollSequence = None

    def run(self) -> list[StrategyResult]:
        """
        Execute the simulation and return results.

        Returns:
            list[StrategyResult]: Results for each strategy
        """
        # Prepare dice sequence
        self._prepare_dice_sequence()

        # Run each strategy
        self.results = []
        for strategy in self.config.strategies:
            result = self._run_single_strategy(strategy)
            self.results.append(result)

        return self.results

    def _prepare_dice_sequence(self) -> None:
        """Generate or use provided dice sequence."""
        if self.config.dice_sequence:
            self.dice_sequence = self.config.dice_sequence
        else:
            # Generate new sequence
            self.dice_sequence = DiceRollSequence(seed=self.config.seed)
            estimated_rolls = self._estimate_rolls_needed()
            self.dice_sequence.generate(estimated_rolls)

    def _estimate_rolls_needed(self) -> int:
        """Estimate number of rolls needed for simulation."""
        if self.config.num_rolls:
            return self.config.num_rolls
        if self.config.num_shooters:
            # Average ~8-10 rolls per shooter, add buffer
            return self.config.num_shooters * 15
        return 1000  # Default

    def _run_single_strategy(self, strategy: Strategy) -> StrategyResult:
        """
        Run one strategy through the simulation.

        Args:
            strategy: The strategy to run

        Returns:
            StrategyResult: Results for this strategy
        """
        # Create isolated game environment
        game = CrapsGame(
            rules=self.config.table_rules,
            dice_provider=self.dice_sequence.get_provider()
        )
        bet_manager = BetManager(self.config.table_rules)
        tracker = BankrollTracker(self.config.starting_bankroll)
        tracker.start_session(self.config.starting_bankroll)

        # Connect strategy to betting interface
        bet_interface = StrategyBetInterface(bet_manager, tracker)
        strategy._set_bet_interface(bet_interface)

        # Track when shooter changes for termination condition
        shooter_count = 1

        # Statistics tracking
        stats = {
            'points_hit': 0,
            'seven_outs': 0,
            'roll_distribution': {i: 0 for i in range(2, 13)},  # 2-12
            'current_shooter_rolls': 0,
            'longest_roll': 0,
            'bankrupt': False,
        }

        # Setup game callbacks
        def on_roll(roll):
            # Track roll distribution
            stats['roll_distribution'][roll.total] += 1
            stats['current_shooter_rolls'] += 1

            # Resolve bets and process payouts
            bankroll_before = tracker.current_bankroll
            bets_before = bet_manager.get_total_at_risk()

            results = bet_manager.resolve_all(roll, game.phase, game.point)

            # Process payouts
            for bet, result in results:
                if result.status == BetStatus.WON:
                    payout = result.payout + bet.amount
                    tracker.current_bankroll += payout
                    tracker.current_bets -= bet.amount
                elif result.status == BetStatus.PUSH:
                    tracker.current_bankroll += bet.amount
                    tracker.current_bets -= bet.amount
                elif result.status == BetStatus.LOST:
                    tracker.current_bets -= bet.amount

            # Record roll in tracker
            bets_after = bet_manager.get_total_at_risk()
            tracker.record_roll(
                roll.die1, roll.die2,
                bankroll_before, tracker.current_bankroll,
                bets_before, bets_after
            )

            # Let strategy react after roll
            strategy.on_roll_complete(roll, game.phase, game.point)

        def on_point_established(point):
            strategy.on_point_made(point)

        def on_seven_out():
            nonlocal shooter_count
            # Track seven outs (only during point phase)
            stats['seven_outs'] += 1

            # Update longest roll if current shooter had more
            if stats['current_shooter_rolls'] > stats['longest_roll']:
                stats['longest_roll'] = stats['current_shooter_rolls']
            stats['current_shooter_rolls'] = 0

            strategy.on_seven_out()
            tracker.end_shooter(seven_out=True)
            shooter_count += 1

        def on_point_won():
            # Track points made
            stats['points_hit'] += 1

            # Update longest roll if current shooter had more
            if stats['current_shooter_rolls'] > stats['longest_roll']:
                stats['longest_roll'] = stats['current_shooter_rolls']
            stats['current_shooter_rolls'] = 0

            tracker.end_shooter(seven_out=False)

        game.on_roll(on_roll)
        game.on_point_established(on_point_established)
        game.on_seven_out(on_seven_out)
        game.on_point_won(on_point_won)

        # Main simulation loop
        roll_count = 0
        max_rolls = self.config.num_rolls or 100000
        max_shooters = self.config.num_shooters or 100000

        try:
            while roll_count < max_rolls and shooter_count <= max_shooters:
                # Check for bankruptcy - if no bankroll and no bets on table, stop
                if tracker.current_bankroll <= 0 and bet_manager.get_total_at_risk() == 0:
                    stats['bankrupt'] = True
                    break

                # Only let strategy place bets if they have bankroll
                if tracker.current_bankroll > 0:
                    # Let strategy place bets before roll
                    if game.is_come_out:
                        strategy.on_come_out_roll(game.phase, game.point)
                    else:
                        strategy.on_point_roll(game.phase, game.point)

                # Roll dice (will resolve existing bets even if bankrupt)
                game.roll_dice()
                roll_count += 1

        except IndexError:
            # Dice sequence exhausted
            pass

        # Update longest roll one more time for final shooter
        if stats['current_shooter_rolls'] > stats['longest_roll']:
            stats['longest_roll'] = stats['current_shooter_rolls']

        # Build result
        rolls, equity = tracker.get_equity_series()
        final_equity = tracker.current_equity
        net_change = final_equity - self.config.starting_bankroll
        roi = (net_change / self.config.starting_bankroll * 100) if self.config.starting_bankroll > 0 else 0

        return StrategyResult(
            strategy_name=strategy.name,
            starting_bankroll=self.config.starting_bankroll,
            final_equity=final_equity,
            net_change=net_change,
            roi_percent=roi,
            rolls=rolls,
            equity_series=equity,
            bankroll_tracker=tracker,
            total_rolls=roll_count,
            total_shooters=shooter_count,
            points_hit=stats['points_hit'],
            seven_outs=stats['seven_outs'],
            longest_roll=stats['longest_roll'],
            roll_distribution=stats['roll_distribution'],
            went_bankrupt=stats['bankrupt']
        )
