from typing import Literal, TypedDict

RANKS = [
    "A",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "jack",
    "queen",
    "king",
]
SUITS = ["hearts", "diamonds", "clubs", "spades"]

Cards = list[str]

ClientMessage = Literal["pile", "slap", "restart"]
"""
Possible messages the client can send

- pile: Request to add a card to the pile
- slap: Request to slap pile
- restart: Request to restart game
"""

ServerMessageType = Literal["full", "state"]
"""
Possible messages the server can send

- Tell lobby is full
```
{ "kind": "full" }
```

- Tell game state
```
{
    "kind": "state",
    "turn": {player},
    "self_hand": {selfHandCount},
    "op_hand": {opHandCount},
    "pile": [
        "{rank}_of_{suit}",
        "{rank}_of_{suit}",
        ...       
    ],
}
```
"""

Player = Literal["self", "opponent"]

GameState = Literal["start", "playing", "game_over"]

class GameStatus(TypedDict):
    kind: Literal["state"]
    turn: Player
    self_hand: int
    op_hand: int
    pile: Cards

