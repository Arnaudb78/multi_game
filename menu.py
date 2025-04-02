import pygame
import pyperclip  # ✅ Nécessaire pour accéder au presse-papier

# Init Pygame
pygame.init()

# Couleurs
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
GRAY = (128, 128, 128)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)

# Police
font = pygame.font.Font(None, 74)
small_font = pygame.font.Font(None, 36)

class Menu:
    def __init__(self, screen):
        self.screen = screen
        self.active_input = False
        self.ip_input = ''
        self.cursor_visible = True
        self.cursor_timer = 0
        self.input_rect = None
        self.mode = None  # 'host' ou 'join'

    def draw_input(self, text, x, y, width, height, active):
        color = BLUE if active else GRAY
        pygame.draw.rect(self.screen, color, (x, y, width, height), 2)
        text_surface = small_font.render(text, True, WHITE)
        self.screen.blit(text_surface, (x + 5, y + 5))
        if active and self.cursor_visible:
            cursor_x = x + 5 + text_surface.get_width()
            pygame.draw.line(self.screen, WHITE, (cursor_x, y + 5), (cursor_x, y + height - 5), 2)
        return pygame.Rect(x, y, width, height)

    def show(self):
        running = True
        clock = pygame.time.Clock()

        while running:
            self.screen.fill(BLACK)
            width, height = self.screen.get_size()

            title = font.render('Shooter Multijoueur', True, WHITE)
            title_rect = title.get_rect(center=(width/2, height/4))
            self.screen.blit(title, title_rect)

            host_button = font.render('Héberger une partie', True, WHITE)
            host_rect = host_button.get_rect(center=(width/2, height/2 - 50))
            pygame.draw.rect(self.screen, GREEN, host_rect.inflate(30, 20))
            self.screen.blit(host_button, host_rect)

            join_button = font.render('Rejoindre une partie', True, WHITE)
            join_rect = join_button.get_rect(center=(width/2, height/2 + 50))
            pygame.draw.rect(self.screen, BLUE, join_rect.inflate(30, 20))
            self.screen.blit(join_button, join_rect)

            if self.mode == 'join':
                label = small_font.render("IP :", True, WHITE)
                self.screen.blit(label, (width/2 - 100, height/2 + 120))
                self.input_rect = self.draw_input(self.ip_input, width/2 - 50, height/2 + 115, 200, 40, self.active_input)

                continue_button = small_font.render('Se connecter', True, WHITE)
                continue_rect = continue_button.get_rect(center=(width/2, height/2 + 200))
                pygame.draw.rect(self.screen, GREEN, continue_rect.inflate(20, 10))
                self.screen.blit(continue_button, continue_rect)

            pygame.display.flip()
            self.update_cursor()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None, None
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mouse_pos = event.pos
                    if host_rect.collidepoint(mouse_pos):
                        return 'host', '127.0.0.1'
                    elif join_rect.collidepoint(mouse_pos):
                        self.mode = 'join'
                    elif self.mode == 'join':
                        if self.input_rect and self.input_rect.collidepoint(mouse_pos):
                            self.active_input = True
                        else:
                            self.active_input = False
                        if 'continue_rect' in locals() and continue_rect.collidepoint(mouse_pos):
                            return 'join', self.ip_input.strip()
                elif event.type == pygame.KEYDOWN and self.active_input:
                    if event.key == pygame.K_BACKSPACE:
                        self.ip_input = self.ip_input[:-1]
                    elif event.key == pygame.K_RETURN:
                        return 'join', self.ip_input.strip()
                    elif event.key == pygame.K_v and pygame.key.get_mods() & pygame.KMOD_CTRL:
                        # ✅ Collage depuis le presse-papier
                        try:
                            clipboard = pyperclip.paste()
                            if isinstance(clipboard, str):
                                self.ip_input += clipboard
                        except Exception as e:
                            print("Erreur lors du collage :", e)
                    elif len(self.ip_input) < 30 and event.unicode.isprintable():
                        self.ip_input += event.unicode

            clock.tick(60)

    def update_cursor(self):
        current_time = pygame.time.get_ticks()
        if current_time - self.cursor_timer > 500:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = current_time

    def show_profile_selection(self):
        pseudonyms = ['Paul', 'Arnaud', 'Fatima', 'Manal', 'Loris', 'Elena', 'Thomas', 'Emma', 'Chainez', 'Oceane', 'Marianne', 'Jules', 'Jamal']
        colors = [RED, GREEN, BLUE, YELLOW, MAGENTA]
        selected_name = None
        selected_color = None
        clock = pygame.time.Clock()

        while True:
            v_rect = None
            self.screen.fill(BLACK)
            width, height = self.screen.get_size()
            title = small_font.render('Choisis ton pseudo et ta couleur', True, WHITE)
            self.screen.blit(title, (width/2 - 150, 50))

            for i, name in enumerate(pseudonyms):
                label = small_font.render(name, True, WHITE)
                rect = label.get_rect(topleft=(100, 100 + i * 50))
                pygame.draw.rect(self.screen, GREEN if name == selected_name else GRAY, rect.inflate(20, 10), 2)
                self.screen.blit(label, rect)

            for i, color in enumerate(colors):
                rect = pygame.Rect(400 + i * 60, 120, 40, 40)
                pygame.draw.rect(self.screen, color, rect)
                pygame.draw.rect(self.screen, WHITE, rect, 2 if color != selected_color else 4)

            if selected_name and selected_color:
                validate = small_font.render('Valider', True, WHITE)
                v_rect = validate.get_rect(center=(width/2, height - 60))
                pygame.draw.rect(self.screen, GREEN, v_rect.inflate(20, 10))
                self.screen.blit(validate, v_rect)

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None, None
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos
                    for i, name in enumerate(pseudonyms):
                        rect = pygame.Rect(100, 100 + i * 50, 150, 40)
                        if rect.collidepoint(mx, my):
                            selected_name = name
                    for i, color in enumerate(colors):
                        rect = pygame.Rect(400 + i * 60, 120, 40, 40)
                        if rect.collidepoint(mx, my):
                            selected_color = color
                    if v_rect and v_rect.collidepoint(mx, my):
                        return selected_name, selected_color

            clock.tick(60)
