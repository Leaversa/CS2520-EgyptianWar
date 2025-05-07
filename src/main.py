import pygame
import random
import sys

# Initialize Pygame
pygame.display.init()
pygame.font.init()

# Constants
WIDTH, HEIGHT = 1200, 1200
FPS = 60
CARD_SIZE = (100, 140)
BUTTON_SIZE = (120, 50)

# Colors
GREEN = (0, 128, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
RED = (255, 0, 0)

# Initialize screen
screen_size = min(pygame.display.Info().current_w, pygame.display.Info().current_h)
screen = pygame.display.set_mode(
    (screen_size * 0.8, screen_size * 0.8), pygame.RESIZABLE
)
pygame.display.set_caption("Egyptian War")
clock = pygame.time.Clock()

# Card values and suits
ranks = [
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
suits = ["hearts", "diamonds", "clubs", "spades"]


# Load card images
def load_card_images():
    cards = {}
    for suit in suits:
        for rank in ranks:
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
    def __init__(self):
        self.deck = []
        self.player_hand = []
        self.opponent_hand = []
        self.pile = []
        self.game_state = "start"  # start, playing, game_over

        # Create and shuffle deck first
        self.create_deck()
        # Then deal cards
        self.deal_initial_cards()

        # Create UI buttons
        self.play_button = Button("Play Card", 50, 500, *BUTTON_SIZE)
        self.slap_button = Button("SLAP!", 200, 500, *BUTTON_SIZE)
        self.new_game_button = Button("New Game", 350, 500, *BUTTON_SIZE)

    def create_deck(self):
        # Create a fresh deck
        self.deck = [f"{rank}_of_{suit}" for suit in suits for rank in ranks]
        # Shuffle the deck
        random.shuffle(self.deck)

    def deal_initial_cards(self):
        # Make sure we have enough cards to deal
        if len(self.deck) < 52:
            self.create_deck()  # Recreate deck if needed

        # Deal 26 cards to each player
        for _ in range(26):
            if self.deck:  # Check if deck has cards
                self.player_hand.append(self.deck.pop())
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
            return True

        # Check for sandwiches (same rank with one card in between)
        if (
            len(self.pile) >= 3
            and self.pile[-1].split("_")[0] == self.pile[-3].split("_")[0]
        ):
            return True

        # Check for top and bottom (same rank on top and bottom of pile)
        if (
            len(self.pile) >= 2
            and self.pile[0].split("_")[0] == self.pile[-1].split("_")[0]
        ):
            return True

        return False

    def handle_events(self, event):
        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and self.game_state == "playing"
        ):
            if (
                self.play_button.rect.collidepoint(event.pos)
                and self.player_hand
            ):
                # Player plays a card
                self.pile.append(self.player_hand.pop(0))
                # Opponent plays a card
                if self.opponent_hand:
                    self.pile.append(self.opponent_hand.pop(0))

            elif self.slap_button.rect.collidepoint(event.pos):
                if self.is_valid_slap():
                    # Player wins the pile
                    self.player_hand.extend(self.pile)
                    self.pile = []
                else:
                    # Player loses a card
                    if self.player_hand:
                        self.pile.append(self.player_hand.pop(0))

        elif event.type == pygame.MOUSEBUTTONDOWN and self.game_state in [
            "start",
            "game_over",
        ]:
            if self.new_game_button.rect.collidepoint(event.pos):
                self.__init__()
                self.game_state = "playing"

    def draw(self):
        screen.fill(GREEN)

        # Draw pile with rotation
        if self.pile:
            # Show last 5 cards in the pile with rotation
            num_cards_to_show = min(5, len(self.pile))
            for i in range(num_cards_to_show):
                card_index = len(self.pile) - num_cards_to_show + i
                card = cards[self.pile[card_index]]

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
        player_text = font.render(
            f"Your cards: {len(self.player_hand)}", True, WHITE
        )
        opponent_text = font.render(
            f"Opponent's cards: {len(self.opponent_hand)}", True, WHITE
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
            if not self.player_hand:
                message = "You lost!"
            else:
                message = "You won!"
            text = font.render(message, True, RED)
            screen.blit(
                text, (WIDTH // 2 - text.get_width() // 2, HEIGHT // 2 - 20)
            )

        # Check for game over
        if len(self.player_hand) == 0 or len(self.opponent_hand) == 0:
            self.game_state = "game_over"


def main():
    game = CardGame()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            game.handle_events(event)

        game.draw()
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
