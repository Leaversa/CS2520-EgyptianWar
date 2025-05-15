import asyncio
from concurrent.futures import Future
import json
import threading
import random
import pygame
from asyncio import Queue
from typing import cast, Callable

import websockets
from websockets import ClientConnection

from game_common import (
    RANKS,
    SUITS,
    ClientMessage,
    GameState,
    GameStatus,
    Player,
)

# Initialize Pygame
pygame.display.init()
pygame.font.init()

# Constants
WIDTH, HEIGHT = 1200, 1200
FPS = 60
SPF = 1 / FPS
CARD_SIZE = (100, 140)
BUTTON_SIZE = (120, 50)

# Colors
GREEN = (34, 139, 34)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
RED = (255, 0, 0)
DISABLE = (100, 200, 100)

# Custom event for server messages
SERVERMSG = pygame.event.custom_type()

# Initialize screen
screen_size = min(
    pygame.display.Info().current_w, pygame.display.Info().current_h
)
screen = pygame.display.set_mode(
    (screen_size * 0.8, screen_size * 0.8), pygame.RESIZABLE
)
pygame.display.set_caption("Egyptian War")


# Load card images
def load_card_images():
    cards = {}
    for suit in SUITS:
        for rank in RANKS:
            try:
                card = pygame.image.load(f"images/{suit}/{rank}.png")
                cards[f"{rank}_of_{suit}"] = pygame.transform.scale(
                    card, CARD_SIZE
                )
            except Exception:
                # Fallback rectangle if images not found
                card = pygame.Surface(CARD_SIZE)
                card.fill(WHITE)
                pygame.draw.rect(card, BLACK, (0, 0, *CARD_SIZE), 2)
                cards[f"{rank}_of_{suit}"] = card
    return cards


cards = load_card_images()


class Button:
    def __init__(
        self, text, x, y, width, height, color=GRAY, hover_color=(220, 220, 220)
    ):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.hover_color = hover_color
        self.text = text
        self.font = pygame.font.Font(None, 28)
        self.enabled = True

    def draw(self, surface):
        mouse_pos = pygame.mouse.get_pos()
        if not self.enabled:
            pygame.draw.rect(surface, self.color, self.rect)
        else:
            if self.rect.collidepoint(mouse_pos) and self.color != DISABLE:
                pygame.draw.rect(surface, self.hover_color, self.rect)
            else:
                pygame.draw.rect(surface, self.color, self.rect)

        text_surf = self.font.render(self.text, True, BLACK)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)


class CardGame:
    def __init__(self, send: Callable[[ClientMessage], Future[None]]):
        self.send = send

        self.self_hand = 0
        self.opponent_hand = 0
        self.turn: Player = "self"

        self.pile = []
        self.game_state: GameState = "start"

        # Slap feedback
        self.last_slap_result = None
        self.slap_message_time = 0

        # Battle state
        self.battle_active = False
        self.battle_face_card = None
        self.battle_remaining = 0

        # Create UI buttons
        self.play_button = Button("Play Card", 50, 500, *BUTTON_SIZE)
        self.slap_button = Button("SLAP!", 200, 500, *BUTTON_SIZE)
        self.new_game_button = Button("New Game", 350, 500, *BUTTON_SIZE)

        # Pile rotation
        self.pile_rotation_angles = []

    def update_pile_rotations(self):
        num_cards_to_show = min(5, len(self.pile))
        # Assign random fixed angles only if the number of cards changed
        if len(self.pile_rotation_angles) != num_cards_to_show:
            self.pile_rotation_angles = [
                random.uniform(-10, 10) for _ in range(num_cards_to_show)
            ]

    def handle_events(self, event: pygame.event.Event):
        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and self.game_state == "playing"
        ):
            if (
                self.play_button.rect.collidepoint(event.pos)
                and self.turn == "self"
            ):
                # Only send pile message if it's our turn
                self.send("pile")
                # Disable the play button until we get the next state update
                self.play_button.enabled = False
            elif self.slap_button.rect.collidepoint(event.pos):
                self.send("slap")
        elif event.type == pygame.MOUSEBUTTONDOWN and self.game_state in [
            "start",
            "game_over",
        ]:
            if self.new_game_button.rect.collidepoint(event.pos):
                self.send("restart")
        elif event.type == SERVERMSG:
            type = event.dict["kind"]
            match type:
                case "state":
                    status = cast(GameStatus, event.dict)
                    self.turn = status["turn"]
                    self.self_hand = status["self_hand"]
                    self.opponent_hand = status["op_hand"]
                    self.pile = status["pile"]
                    self.game_state = (
                        "playing"
                        if self.self_hand and self.opponent_hand
                        else "game_over"
                    )
                    # Re-enable the play button when we get a state update
                    self.play_button.enabled = True
                case "slap_result":
                    self.last_slap_result = event.dict["result"]
                    self.slap_message_time = pygame.time.get_ticks()
                case "battle_start":
                    self.battle_active = True
                    self.battle_face_card = event.dict["face_card"]
                    self.battle_remaining = event.dict["cards_to_play"]
                case "battle_continue":
                    self.battle_remaining = event.dict["cards_remaining"]
                case "battle_end":
                    self.battle_active = False
                    self.battle_face_card = None
                    self.battle_remaining = 0

    def draw(self, screen: pygame.Surface):
        screen.fill(GREEN)

        self.update_pile_rotations()

        screen_rect = screen.get_rect()
        num_cards_to_show = min(5, len(self.pile))

        for i in range(num_cards_to_show):
            card_key = self.pile[-num_cards_to_show + i]
            card = cards[card_key]
            angle = self.pile_rotation_angles[i]
            rotated_card = pygame.transform.rotate(card, angle)
            x = screen_rect.centerx - rotated_card.get_width() // 2
            y = screen_rect.centery - rotated_card.get_height() // 2 + (i * 5)
            screen.blit(rotated_card, (x, y))

        font = pygame.font.Font(None, 36)

        turn_text = font.render(
            f"Current turn: {'Yours' if self.turn == 'self' else "Opponent's"}",
            True,
            WHITE,
        )
        turn_x = screen_rect.centerx - turn_text.get_width() // 2
        turn_y = 20
        screen.blit(turn_text, (turn_x, turn_y))

        opponent_text = font.render(
            f"Opponent's cards: {self.opponent_hand}", True, WHITE
        )
        opponent_x = screen_rect.right - opponent_text.get_width() - 20
        opponent_y = 20
        screen.blit(opponent_text, (opponent_x, opponent_y))

        player_text = font.render(f"Your cards: {self.self_hand}", True, WHITE)
        player_x = 50
        player_y = 590
        screen.blit(player_text, (player_x, player_y))

        # Draw buttons
        if self.game_state == "playing":
            self.play_button.color = DISABLE if self.turn != "self" else GRAY
            self.play_button.draw(screen)
            self.slap_button.draw(screen)
        else:
            self.new_game_button.draw(screen)

        # Game over message
        if self.game_state == "game_over":
            message = "You won!" if self.self_hand else "You lost!"
            text = font.render(message, True, RED)
            screen.blit(
                text, (WIDTH // 2 - text.get_width() // 2, HEIGHT // 2 - 20)
            )

        # Show slap result message if recent
        if (
            self.last_slap_result
            and pygame.time.get_ticks() - self.slap_message_time < 2000
        ):
            msg = (
                "Good slap!"
                if self.last_slap_result == "correct"
                else "Bad slap!"
            )
            color = (
                (0, 255, 0)
                if self.last_slap_result == "correct"
                else (255, 0, 0)
            )
            slap_text = font.render(msg, True, color)
            screen.blit(
                slap_text, (WIDTH // 2 - slap_text.get_width() // 2, 500)
            )

        # Draw battle indicator if active
        if self.battle_active and self.battle_face_card:
            battle_font = pygame.font.Font(None, 32)
            battle_text = battle_font.render(
                f"BATTLE! Play {self.battle_remaining} cards for {self.battle_face_card}",
                True,
                (255, 215, 0),
            )
            screen.blit(
                battle_text,
                (WIDTH // 2 - battle_text.get_width() // 2, HEIGHT - 100),
            )

            # Add flashing effect during battle
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((255, 215, 0, 30))
            screen.blit(overlay, (0, 0))


def intiailize_asyncio(
    loop: asyncio.AbstractEventLoop, send_queue: Queue[ClientMessage]
):
    """Uses `loop` as the asyncio event loop for asyncio_main."""
    asyncio.set_event_loop(loop)
    loop.run_until_complete(asyncio_main(send_queue))


async def asyncio_main(send_queue: Queue[ClientMessage]):
    """Handles incoming and outgoing server messages"""
    async with websockets.connect("ws://localhost:8765") as socket:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(handle_server_incoming(socket))
            tg.create_task(handle_server_outgoing(socket, send_queue))


async def handle_server_incoming(socket: ClientConnection):
    """Forwards server messages to pygame event queue."""
    while True:
        message = await socket.recv()
        obj = json.loads(message)
        pygame.event.post(pygame.event.Event(SERVERMSG, obj))


async def handle_server_outgoing(
    socket: ClientConnection, send_queue: Queue[ClientMessage]
):
    """Sends messages in `send_queue` to the server."""
    while True:
        await socket.send(await send_queue.get())


def main():
    send_queue: Queue[ClientMessage] = Queue()

    # Run initialize_asyncio() in a separate thread
    loop = asyncio.new_event_loop()
    thread = threading.Thread(
        target=intiailize_asyncio, args=(loop, send_queue)
    )
    thread.start()

    game = CardGame(
        lambda msg: asyncio.run_coroutine_threadsafe(send_queue.put(msg), loop)
    )

    clock = pygame.time.Clock()
    while True:
        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    raise KeyboardInterrupt
                game.handle_events(event)

            game.draw(screen)
            pygame.display.flip()
            clock.tick(FPS)
        except KeyboardInterrupt:
            pygame.quit()
            loop.call_soon_threadsafe(loop.stop)


if __name__ == "__main__":
    main()
