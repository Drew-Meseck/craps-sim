"""
Strategy simulation runner for executing and comparing strategies.

Runs multiple strategies on the same dice sequence for fair comparison.
"""
from dataclasses import dataclass, field
from typing import Optional
import statistics
import copy

from .strategy import Strategy, StrategyBetInterface
from .game import CrapsGame, TableRules, GamePhase
from .bets import BetManager, BetStatus
from .bankroll import BankrollTracker, ShooterRecord
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
    # Session mode configuration
    session_mode: bool = False
    shooters_per_session: int = 5
    num_sessions: int = 100


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
    # Enhanced statistics
    weighted_house_edge: float = 0.0
    action_by_bet_type: dict[str, float] = field(default_factory=dict)
    shooter_records: list[ShooterRecord] = field(default_factory=list)


@dataclass
class SessionResult:
    """Results for a single session (N shooters)."""
    session_number: int
    starting_bankroll: float
    ending_bankroll: float
    net_change: float
    roi_percent: float
    num_shooters: int
    num_rolls: int
    points_made: int
    seven_outs: int
    shooter_records: list[ShooterRecord] = field(default_factory=list)


@dataclass
class SessionSimulationResult:
    """Results for session-based simulation of a strategy."""
    strategy_name: str
    sessions: list[SessionResult]

    # Cross-session statistics
    avg_session_net: float
    std_session_net: float
    avg_session_roi: float
    std_session_roi: float
    median_session_net: float

    # Percentile analysis (what players at different luck levels experienced)
    percentile_10: float  # Unlucky players (bottom 10%)
    percentile_25: float  # Below average
    percentile_75: float  # Above average
    percentile_90: float  # Lucky players (top 10%)
    min_session_net: float
    max_session_net: float

    # Overall totals
    total_sessions: int
    winning_sessions: int
    losing_sessions: int
    break_even_sessions: int

    # Action-weighted house edge
    weighted_house_edge: float
    action_by_bet_type: dict[str, float] = field(default_factory=dict)

    # Overall bankroll tracking
    total_net_change: float = 0.0
    total_roi_percent: float = 0.0


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

    def run_sessions(self) -> list[SessionSimulationResult]:
        """
        Execute session-based simulation and return results.

        This is a convenience method that creates a SessionRunner internally.

        Returns:
            list[SessionSimulationResult]: Session results for each strategy
        """
        session_runner = SessionRunner(self.config)
        return session_runner.run()

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

            # Process payouts and track bet results
            for bet, result in results:
                if result.status == BetStatus.WON:
                    payout = result.payout + bet.amount
                    tracker.current_bankroll += payout
                    tracker.current_bets -= bet.amount
                    tracker.record_bet_result(bet.name, True, result.payout)
                elif result.status == BetStatus.PUSH:
                    tracker.current_bankroll += bet.amount
                    tracker.current_bets -= bet.amount
                elif result.status == BetStatus.LOST:
                    tracker.current_bets -= bet.amount
                    tracker.record_bet_result(bet.name, False, bet.amount)

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
            tracker.record_point_established()
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
            tracker.record_point_made()

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
            went_bankrupt=stats['bankrupt'],
            weighted_house_edge=bet_manager.get_weighted_house_edge(),
            action_by_bet_type=bet_manager.get_action_summary(),
            shooter_records=tracker.get_all_shooter_records()
        )


class SessionRunner:
    """
    Runs session-based simulations.

    A session consists of a fixed number of shooters. This simulates
    realistic casino sessions where you play for a certain duration.
    """

    def __init__(self, config: SimulationConfig):
        """
        Initialize the session runner.

        Args:
            config: Simulation configuration with session_mode=True
        """
        self.config = config
        self.results: list[SessionSimulationResult] = []

    def run(self) -> list[SessionSimulationResult]:
        """
        Execute session-based simulation for all strategies.

        Returns:
            list[SessionSimulationResult]: Results for each strategy
        """
        self.results = []

        for strategy in self.config.strategies:
            result = self._run_strategy_sessions(strategy)
            self.results.append(result)

        return self.results

    def _run_strategy_sessions(self, strategy: Strategy) -> SessionSimulationResult:
        """Run all sessions for a single strategy."""
        sessions: list[SessionResult] = []
        total_action: dict[str, float] = {}
        total_house_edge_action: dict[str, float] = {}

        for session_num in range(1, self.config.num_sessions + 1):
            # Create fresh strategy copy for each session
            session_strategy = copy.deepcopy(strategy)
            session_result, session_action, session_edges = self._run_single_session(
                session_strategy, session_num
            )
            sessions.append(session_result)

            # Accumulate action across sessions
            for bet_type, amount in session_action.items():
                total_action[bet_type] = total_action.get(bet_type, 0.0) + amount
                total_house_edge_action[bet_type] = session_edges.get(bet_type, 0.0)

        # Calculate cross-session statistics
        net_changes = [s.net_change for s in sessions]
        rois = [s.roi_percent for s in sessions]

        avg_net = statistics.mean(net_changes) if net_changes else 0.0
        std_net = statistics.stdev(net_changes) if len(net_changes) > 1 else 0.0
        avg_roi = statistics.mean(rois) if rois else 0.0
        std_roi = statistics.stdev(rois) if len(rois) > 1 else 0.0
        median_net = statistics.median(net_changes) if net_changes else 0.0

        # Percentile analysis
        sorted_nets = sorted(net_changes)
        n = len(sorted_nets)
        if n > 0:
            p10 = sorted_nets[int(n * 0.10)] if n > 1 else sorted_nets[0]
            p25 = sorted_nets[int(n * 0.25)] if n > 1 else sorted_nets[0]
            p75 = sorted_nets[int(n * 0.75)] if n > 1 else sorted_nets[-1]
            p90 = sorted_nets[int(n * 0.90)] if n > 1 else sorted_nets[-1]
            min_net = sorted_nets[0]
            max_net = sorted_nets[-1]
        else:
            p10 = p25 = p75 = p90 = min_net = max_net = 0.0

        winning = sum(1 for s in sessions if s.net_change > 0)
        losing = sum(1 for s in sessions if s.net_change < 0)
        break_even = sum(1 for s in sessions if s.net_change == 0)

        # Calculate weighted house edge across all sessions
        total_wagered = sum(total_action.values())
        if total_wagered > 0:
            weighted_edge = sum(
                action * total_house_edge_action.get(bet_type, 0.0)
                for bet_type, action in total_action.items()
            ) / total_wagered
        else:
            weighted_edge = 0.0

        total_net = sum(s.net_change for s in sessions)
        total_roi = (total_net / (self.config.starting_bankroll * len(sessions)) * 100) if sessions else 0.0

        return SessionSimulationResult(
            strategy_name=strategy.name,
            sessions=sessions,
            avg_session_net=avg_net,
            std_session_net=std_net,
            avg_session_roi=avg_roi,
            std_session_roi=std_roi,
            median_session_net=median_net,
            percentile_10=p10,
            percentile_25=p25,
            percentile_75=p75,
            percentile_90=p90,
            min_session_net=min_net,
            max_session_net=max_net,
            total_sessions=len(sessions),
            winning_sessions=winning,
            losing_sessions=losing,
            break_even_sessions=break_even,
            weighted_house_edge=weighted_edge,
            action_by_bet_type=total_action,
            total_net_change=total_net,
            total_roi_percent=total_roi
        )

    def _run_single_session(
        self, strategy: Strategy, session_num: int
    ) -> tuple[SessionResult, dict[str, float], dict[str, float]]:
        """
        Run a single session (N shooters).

        Returns:
            tuple of (SessionResult, action_summary, house_edges)
        """
        # Create isolated game environment
        dice_sequence = DiceRollSequence(
            seed=(self.config.seed or 0) + session_num if self.config.seed else None
        )
        dice_sequence.generate(self.config.shooters_per_session * 15)

        game = CrapsGame(
            rules=self.config.table_rules,
            dice_provider=dice_sequence.get_provider()
        )
        bet_manager = BetManager(self.config.table_rules)
        tracker = BankrollTracker(self.config.starting_bankroll)
        tracker.start_session(self.config.starting_bankroll)

        # Connect strategy
        bet_interface = StrategyBetInterface(bet_manager, tracker)
        strategy._set_bet_interface(bet_interface)

        # Session tracking
        shooter_count = 0
        roll_count = 0
        points_made = 0
        seven_outs = 0

        # Callbacks
        def on_roll(roll):
            nonlocal roll_count
            roll_count += 1

            bankroll_before = tracker.current_bankroll
            bets_before = bet_manager.get_total_at_risk()

            results = bet_manager.resolve_all(roll, game.phase, game.point)

            for bet, result in results:
                if result.status == BetStatus.WON:
                    payout = result.payout + bet.amount
                    tracker.current_bankroll += payout
                    tracker.current_bets -= bet.amount
                    tracker.record_bet_result(bet.name, True, result.payout)
                elif result.status == BetStatus.PUSH:
                    tracker.current_bankroll += bet.amount
                    tracker.current_bets -= bet.amount
                elif result.status == BetStatus.LOST:
                    tracker.current_bets -= bet.amount
                    tracker.record_bet_result(bet.name, False, bet.amount)

            bets_after = bet_manager.get_total_at_risk()
            tracker.record_roll(
                roll.die1, roll.die2,
                bankroll_before, tracker.current_bankroll,
                bets_before, bets_after
            )

            strategy.on_roll_complete(roll, game.phase, game.point)

        def on_point_established(point):
            tracker.record_point_established()
            strategy.on_point_made(point)

        def on_seven_out():
            nonlocal shooter_count, seven_outs
            seven_outs += 1
            shooter_count += 1
            strategy.on_seven_out()
            tracker.end_shooter(seven_out=True)

        def on_point_won():
            nonlocal points_made
            points_made += 1
            tracker.record_point_made()
            tracker.end_shooter(seven_out=False)

        game.on_roll(on_roll)
        game.on_point_established(on_point_established)
        game.on_seven_out(on_seven_out)
        game.on_point_won(on_point_won)

        # Run session until we've had N shooters seven out
        try:
            while shooter_count < self.config.shooters_per_session:
                # Check for bankruptcy
                if tracker.current_bankroll <= 0 and bet_manager.get_total_at_risk() == 0:
                    break

                if tracker.current_bankroll > 0:
                    if game.is_come_out:
                        strategy.on_come_out_roll(game.phase, game.point)
                    else:
                        strategy.on_point_roll(game.phase, game.point)

                game.roll_dice()

        except IndexError:
            pass

        # Build session result
        ending_bankroll = tracker.current_equity
        net_change = ending_bankroll - self.config.starting_bankroll
        roi = (net_change / self.config.starting_bankroll * 100) if self.config.starting_bankroll > 0 else 0

        session_result = SessionResult(
            session_number=session_num,
            starting_bankroll=self.config.starting_bankroll,
            ending_bankroll=ending_bankroll,
            net_change=net_change,
            roi_percent=roi,
            num_shooters=shooter_count,
            num_rolls=roll_count,
            points_made=points_made,
            seven_outs=seven_outs,
            shooter_records=tracker.get_all_shooter_records()
        )

        return session_result, bet_manager.get_action_summary(), bet_manager.bet_house_edges
