"""Typed models for Dota 2 GSI payloads (player view).

Built from real payloads in fixtures/. Only the fields rules need are modelled;
Pydantic ignores everything else (Steam ID, buildings, ...). Every field has a
default because Dota leaves sections out depending on the moment: in the menu
there is no `map`, during hero selection `hero` is just {"id": 0}.

Usage:  state = GameState.model_validate(payload_dict)
"""

from pydantic import BaseModel


class MapState(BaseModel):
    clock_time: int = 0  # game clock in seconds; negative before the horn
    game_time: int = 0  # seconds since the map loaded (never negative)
    game_state: str = ""  # e.g. "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS"
    daytime: bool = True
    paused: bool = False
    radiant_score: int = 0
    dire_score: int = 0


class PlayerState(BaseModel):
    team_name: str | None = None  # "radiant" or "dire"
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    last_hits: int = 0
    denies: int = 0
    gold: int = 0
    gold_reliable: int = 0
    gold_unreliable: int = 0
    gpm: int = 0
    xpm: int = 0


class HeroState(BaseModel):
    id: int = 0  # 0 = no hero picked yet
    name: str | None = None  # internal name, e.g. "npc_dota_hero_nevermore"
    level: int = 0
    xp: int = 0
    alive: bool = True
    respawn_seconds: int = 0
    health: int = 0
    max_health: int = 0
    health_percent: int = 0
    mana: int = 0
    max_mana: int = 0
    mana_percent: int = 0
    buyback_cost: int = 0
    aghanims_scepter: bool = False
    aghanims_shard: bool = False


class Ability(BaseModel):
    name: str
    level: int = 0
    can_cast: bool = False
    passive: bool = False
    cooldown: int = 0
    ultimate: bool = False


class Item(BaseModel):
    name: str  # "empty" for an empty slot
    charges: int | None = None
    cooldown: int | None = None
    can_cast: bool | None = None

    @property
    def is_empty(self) -> bool:
        return self.name == "empty"


class GameState(BaseModel):
    """One GSI payload. `map` is None when you're in the menu, not in a game."""

    map: MapState | None = None
    player: PlayerState = PlayerState()
    hero: HeroState = HeroState()
    # Dota sends these as {"ability0": {...}, "ability1": {...}} and
    # {"slot0": {...}, "stash0": {...}, "teleport0": {...}, ...}.
    abilities: dict[str, Ability] = {}
    items: dict[str, Item] = {}

    @property
    def hero_picked(self) -> bool:
        return self.hero.name is not None

    @property
    def ability_list(self) -> list[Ability]:
        """Abilities in skill-bar order (ability0, ability1, ...)."""
        keys = sorted(self.abilities, key=lambda k: int(k.removeprefix("ability")))
        return [self.abilities[k] for k in keys]

    def _item_names(self, keys: list[str]) -> list[str]:
        """Names of the items in the given slots, skipping missing/empty ones."""
        names = []
        for key in keys:
            item = self.items.get(key)
            if item is not None and not item.is_empty:
                names.append(item.name)
        return names

    @property
    def inventory(self) -> list[str]:
        """Item names in the 6 main slots (slot0-5)."""
        return self._item_names([f"slot{i}" for i in range(6)])

    @property
    def backpack(self) -> list[str]:
        """Item names in the 3 backpack slots (slot6-8)."""
        return self._item_names([f"slot{i}" for i in range(6, 9)])

    @property
    def stash(self) -> list[str]:
        """Item names in the stash (stash0-5)."""
        return self._item_names([f"stash{i}" for i in range(6)])
