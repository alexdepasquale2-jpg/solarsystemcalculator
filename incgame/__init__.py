"""
Generative incremental game engine.

Every run is generated from a single integer seed: the resources, the actions,
the generators, the upgrade trees, the emergent mechanics, the names, and the
colour theme. Nothing about a run is hand-authored.

Public entry points:

    from incgame import generate_game, GameEngine

    game = generate_game(seed=1234)
    engine = GameEngine(game)
    engine.do_action(game.actions[0].id)
    engine.advance()
"""

from .model import (
    Action,
    Effect,
    GameDef,
    Generator,
    Mechanic,
    PrestigeUpgrade,
    Resource,
    Unlock,
    Upgrade,
    fmt_number,
)
from .generator import generate_game, random_seed
from .engine import GameEngine, GameState
from .save import dump_save, load_save

__version__ = "0.1.0"

__all__ = [
    "Action",
    "Effect",
    "GameDef",
    "GameEngine",
    "GameState",
    "Generator",
    "Mechanic",
    "PrestigeUpgrade",
    "Resource",
    "Unlock",
    "Upgrade",
    "dump_save",
    "fmt_number",
    "generate_game",
    "load_save",
    "random_seed",
    "__version__",
]
