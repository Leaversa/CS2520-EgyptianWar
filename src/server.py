import asyncio
import json
import random
from asyncio.exceptions import CancelledError
from websockets.asyncio.server import serve, ServerConnection
from websockets.exceptions import ConnectionClosed, ConnectionClosedError
from typing import cast
from game_common import (
    RANKS,
    SUITS,
    Cards,
    GameStatus,
    Player,
    ClientMessage,
)


class GameServer:
    def __init__(self, address: str, port: int):
        self._address = address
        self._port = port
        self._server = serve(self.handle_events, address, port)

        self._connections: list[ServerConnection] = []

        self._game = CardGame()

    async def listen(self):
        """Begins listening for client connections."""
        try:
            async with self._server as server:
                print(f"Serving on http://{self._address}:{self._port}")
                await server.serve_forever()
        # Catches Ctrl+C
        except CancelledError:
            print("Closing server...")

    async def handle_events(self, socket: ServerConnection):
        if self.num_players() == 2:
            return

        self._connections.append(socket)

        player: Player = "self" if self.num_players() == 1 else "opponent"

        if self.num_players() == 2:
            await self.send_all_game_status()

        try:
            async for message in socket:
                action = cast(ClientMessage, message)

                match action:
                    case "restart":
                        self._game.__init__()
                        await self.send_all_game_status()
                    case "pile":
                        # Only process pile message if it's actually the player's turn
                        if player == self._game.turn:
                            self._game.play_card(player)
                            await self.send_all_game_status()
                    case "slap":
                        result = self._game.slap(player)
                        # Broadcast slap_result to all clients
                        for conn in self._connections:
                            await conn.send(
                                json.dumps(
                                    {"kind": "slap_result", "result": result}
                                )
                            )
                        await self.send_all_game_status()

        except ConnectionClosedError:
            pass

        # Close lobby if either player leaves
        for socket in self._connections:
            await socket.close()
        self._connections = []

    def num_players(self) -> int:
        """Gets number of clients connected to the server."""
        return len(self._connections)

    async def send_all_game_status(self):
        """Sends players the game status."""
        if len(self._connections) >= 2:
            await self._connections[0].send(
                json.dumps(self._game.status("self"))
            )
            await self._connections[1].send(
                json.dumps(self._game.status("opponent"))
            )


class CardGame:
    def __init__(self):
        self.deck: Cards = []
        self.self_hand: Cards = []
        self.opponent_hand: Cards = []
        self.pile: Cards = []
        self.turn: Player = "self"
        self.royal_cards_needed: int = -1  # -1 means no royal cards needed

        # Create and shuffle deck first
        self.create_deck()
        # Then deal cards
        self.deal_initial_cards()

    def create_deck(self):
        # Create a fresh deck
        self.deck = [f"{rank}_of_{suit}" for suit in SUITS for rank in RANKS]
        # Shuffle the deck
        random.shuffle(self.deck)

    def deal_initial_cards(self):
        # Make sure we have enough cards to deal
        if len(self.deck) < 52:
            self.create_deck()  # Recreate deck if needed

        # Deal 26 cards to each player
        for _ in range(26):
            if self.deck:  # Check if deck has cards
                self.self_hand.append(self.deck.pop())
            if self.deck:  # Check if deck has cards
                self.opponent_hand.append(self.deck.pop())

    def is_valid_slap(self):
        if len(self.pile) < 2:
            return False

        # Check for doubles (two cards of same rank)
        if (
            len(self.pile) >= 2
            and self.pile[-1].split("_")[0] == self.pile[-2].split("_")[0]
        ):
            print("doubles", self.pile[-1], self.pile[-2])
            return True

        # Check for sandwiches (same rank with one card in between)
        if (
            len(self.pile) >= 3
            and self.pile[-1].split("_")[0] == self.pile[-3].split("_")[0]
        ):
            print("sandwich", self.pile[-1], self.pile[-3])
            return True

        # Check for top and bottom (same rank on top and bottom of pile)
        if (
            len(self.pile) >= 2
            and self.pile[0].split("_")[0] == self.pile[-1].split("_")[0]
        ):
            print("top and bottom", self.pile[0], self.pile[-1])
            return True
        print("no valid slap")
        return False

    def play_card(self, player: Player):
        """
        Moves a card in the players hand to the pile.
        Does nothing if not the player's turn or hand is empty.
        """
        royal_cards = {
            "ace": 4,
            "king": 3,
            "queen": 2,
            "jack": 1,
        }

        if player == self.turn and self.hand(player):
            played_card = self.hand(player).pop(0)
            self.pile.append(played_card)
            print(played_card)

            card_rank = played_card.split("_")[0]

            # Check if the card played is a royal card
            if card_rank in royal_cards:
                # Reset the number of cards needed to the rank of the card played
                self.royal_cards_needed = royal_cards[card_rank]

                print(
                    f"Royal card played: {card_rank}, {self.royal_cards_needed} cards needed"
                )

                # Switch turns when a royal card is played
                self.turn = "opponent" if self.turn == "self" else "self"
            elif self.royal_cards_needed > 0:
                # If the card played is not a royal card, and the number of cards needed is greater than 0,
                # Decrement the number of cards needed
                self.royal_cards_needed -= 1
                # Keep the same player's turn since they haven't played a royal card
                # and they have not met the number of cards needed
            elif self.royal_cards_needed == 0:
                # If no royal card sequence is in progress, give the pile to the other player
                self.royal_cards_needed = -1
                other_player = "opponent" if player == "self" else "self"
                self.hand(other_player).extend(self.pile)
                self.pile = []
                # Switch turns after giving the pile
                self.turn = other_player
            else:
                # If the card played is not a royal card, and no cards needed,
                # Switch turns
                self.turn = "opponent" if player == "self" else "self"

    def slap(self, player: Player):
        """
        If legal, player moves all cards from the pile to their hand.
        If illegal, player moves a card from their hand to the pile.
        """
        hand = self.hand(player)
        if self.is_valid_slap():
            hand.extend(self.pile)
            self.pile = []
            # Interrupt the royal card sequence if it was in progress
            self.royal_cards_needed = -1
            print("slap successful")
            return "correct"
        elif hand:
            self.pile.append(hand.pop(0))
            print("slap incorrect")
            return "incorrect"
        print("slap incorrect")
        return "incorrect"

    def hand(self, player: Player):
        """Gets the hand of `player`"""
        return self.self_hand if player == "self" else self.opponent_hand

    def status(self, player: Player) -> GameStatus:
        """
        Gets the status of the game. `turn`, `self_hand`, and `op_hand` are
        dependent on who `player` is.
        """
        turn = "self" if player == self.turn else "opponent"
        self_hand = self.self_hand if player == "self" else self.opponent_hand
        op_hand = self.opponent_hand if player == "self" else self.self_hand
        return {
            "kind": "state",
            "turn": turn,
            "self_hand": len(self_hand),
            "op_hand": len(op_hand),
            "pile": self.pile,
        }


async def main():
    server = GameServer("localhost", 8765)
    await server.listen()


if __name__ == "__main__":
    asyncio.run(main())
