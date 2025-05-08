import asyncio
from concurrent.futures import Future
import json
import threading
import time
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
GREEN = (0, 128, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
RED = (255, 0, 0)

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

    def draw(self, surface):
        mouse_pos = pygame.mouse.get_pos()
        if self.rect.collidepoint(mouse_pos):
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

        # Create UI buttons
        self.play_button = Button("Play Card", 50, 500, *BUTTON_SIZE)
        self.slap_button = Button("SLAP!", 200, 500, *BUTTON_SIZE)
        self.new_game_button = Button("New Game", 350, 500, *BUTTON_SIZE)

    def handle_events(self, event: pygame.event.Event):
        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and self.game_state == "playing"
        ):
            if self.play_button.rect.collidepoint(event.pos):
                self.send("pile")
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

    def draw(self, screen: pygame.Surface):
        screen.fill(GREEN)

        # Draw pile with rotation
        if self.pile:
            # Show last 5 cards in the pile with rotation
            num_cards_to_show = min(5, len(self.pile))
            for i in range(num_cards_to_show):
                card = cards[self.pile[-num_cards_to_show + i]]

                # Calculate rotation angle (in degrees)
                rotation_angle = i * 5  # 5 degrees per card

                # Create a rotated surface
                rotated_card = pygame.transform.rotate(card, rotation_angle)

                # Calculate position with offset for rotation
                x = WIDTH // 2 - rotated_card.get_width() // 2
                y = (
                    HEIGHT // 2 - rotated_card.get_height() // 2 + (i * 5)
                )  # Slight vertical offset

                screen.blit(rotated_card, (x, y))

        # Draw player's hand count
        font = pygame.font.Font(None, 36)
        player_text = font.render(f"Your cards: {self.self_hand}", True, WHITE)
        opponent_text = font.render(
            f"Opponent's cards: {self.opponent_hand}", True, WHITE
        )
        screen.blit(player_text, (50, 320))
        screen.blit(opponent_text, (50, 20))

        # Draw buttons
        if self.game_state == "playing":
            self.play_button.draw(screen)
            self.slap_button.draw(screen)
        else:
            self.new_game_button.draw(screen)

        # Game over message
        if self.game_state == "game_over":
            if self.self_hand:
                message = "You won!"
            else:
                message = "You lost!"
            text = font.render(message, True, RED)
            screen.blit(
                text, (WIDTH // 2 - text.get_width() // 2, HEIGHT // 2 - 20)
            )


def intiailize_asyncio(
    loop: asyncio.AbstractEventLoop,
    send_queue: Queue[ClientMessage]):
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
    thread = threading.Thread(target=intiailize_asyncio, args=(loop, send_queue))
    thread.start()

    game = CardGame(lambda msg: asyncio.run_coroutine_threadsafe(send_queue.put(msg), loop))

    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
            game.handle_events(event)
        
        game.draw(screen)
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
