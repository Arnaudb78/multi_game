import pygame
import socket
import threading
import pickle
from menu import Menu
from map_manager import MapManager

# Configuration du client
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 12345

# Initialisation de Pygame
pygame.init()

# Dimensions de la fenêtre du jeu (plus petite pour voir une portion du map)
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption('Jeu Shooter Multijoueur')

# Couleurs
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
GRAY = (128, 128, 128)
BLUE = (0, 0, 255)

# Police
font = pygame.font.Font(None, 74)
small_font = pygame.font.Font(None, 36)

# Joueur
player_x, player_y = 400, 300
player_speed = 5
player_color = (255, 0, 0)  # Rouge pour le joueur
client_id = None

# Camera
camera_x = 0
camera_y = 0
camera_speed = 0.1  # Vitesse de la caméra (plus petit = plus fluide)

# Dictionnaire des autres joueurs
other_players = {}  # {client_id: (x, y)}

# Map
map_manager = MapManager("assets/map/map.tmx")
map_width, map_height = map_manager.get_map_size()


def draw_text_input(text, x, y, width, height, active):
    # Draw input box
    color = BLUE if active else GRAY
    pygame.draw.rect(screen, color, (x, y, width, height), 2)
    
    # Draw text
    text_surface = small_font.render(text, True, WHITE)
    screen.blit(text_surface, (x + 5, y + 5))
    
    # Draw cursor if active
    if active and cursor_visible:
        cursor_x = x + 5 + text_surface.get_width()
        pygame.draw.line(screen, WHITE, (cursor_x, y + 5), 
                        (cursor_x, y + height - 5), 2)
    
    return pygame.Rect(x, y, width, height)


def draw_menu():
    screen.fill(BLACK)
    
    # Titre
    title = font.render(
        'Jeu Shooter Multijoueur', True, WHITE
    )
    title_rect = title.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/4))
    screen.blit(title, title_rect)
    
    # Input fields
    input_height = 40
    input_width = 200
    spacing = 20
    
    # Host input
    host_label = small_font.render('Host IP:', True, WHITE)
    host_label_rect = host_label.get_rect(
        center=(SCREEN_WIDTH/2 - input_width/2 - 50, SCREEN_HEIGHT/2 - 60)
    )
    screen.blit(host_label, host_label_rect)
    
    host_rect = draw_text_input(
        host_input,
        SCREEN_WIDTH/2 - input_width/2,
        SCREEN_HEIGHT/2 - 60,
        input_width,
        input_height,
        active_input == 'host'
    )
    
    # Port input
    port_label = small_font.render('Port:', True, WHITE)
    port_label_rect = port_label.get_rect(
        center=(SCREEN_WIDTH/2 - input_width/2 - 50, SCREEN_HEIGHT/2)
    )
    screen.blit(port_label, port_label_rect)
    
    port_rect = draw_text_input(
        port_input,
        SCREEN_WIDTH/2 - input_width/2,
        SCREEN_HEIGHT/2,
        input_width,
        input_height,
        active_input == 'port'
    )
    
    # Bouton Start
    start_button = font.render('Start Game', True, WHITE)
    start_rect = start_button.get_rect(
        center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2 + 80)
    )
    pygame.draw.rect(screen, GREEN, start_rect.inflate(20, 20))
    screen.blit(start_button, start_rect)
    
    # Bouton Quit
    quit_button = font.render('Quit', True, WHITE)
    quit_rect = quit_button.get_rect(
        center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2 + 160)
    )
    pygame.draw.rect(screen, RED, quit_rect.inflate(20, 20))
    screen.blit(quit_button, quit_rect)
    
    pygame.display.flip()
    return start_rect, quit_rect, host_rect, port_rect


def receive_data(client_socket):
    global other_players, client_id
    buffer = b""
    while True:
        try:
            data = client_socket.recv(1024)
            if not data:
                break
                
            buffer += data
            while len(buffer) > 0:
                try:
                    # Try to unpickle the data
                    message = pickle.loads(buffer)
                    buffer = b""  # Clear buffer after successful unpickling
                    
                    if message[0] == 'init':
                        # Message d'initialisation avec l'ID du client
                        client_id = message[1]
                        print(f"Connected with ID: {client_id}")
                    elif message[0] == 'disconnect':
                        # Message de déconnexion d'un joueur
                        disconnected_id = message[1]
                        if disconnected_id in other_players:
                            del other_players[disconnected_id]
                    else:
                        # Message de position d'un joueur
                        other_id, position = message
                        if other_id != client_id:  # Ne pas mettre à jour sa propre position
                            other_players[other_id] = position
                except pickle.UnpicklingError:
                    # If we can't unpickle, we need more data
                    break
                    
        except Exception as e:
            print(f"Error receiving data: {e}")
            break


def main():
    global player_x, player_y, camera_x, camera_y
    
    # Menu principal
    menu = Menu(screen, DEFAULT_HOST, str(DEFAULT_PORT))
    menu_running = True
    
    while menu_running:
        start_rect, quit_rect, host_rect, port_rect = menu.draw()
        menu.update()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = event.pos
                if start_rect.collidepoint(mouse_pos):
                    menu_running = False
                elif quit_rect.collidepoint(mouse_pos):
                    pygame.quit()
                    return
                else:
                    menu.handle_event(event)
            elif event.type == pygame.KEYDOWN:
                menu.handle_event(event)

    # Connexion au serveur
    try:
        host, port = menu.get_connection_info()
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((host, port))
    except Exception as e:
        print(f"Connection error: {e}")
        pygame.quit()
        return

    # Lancer le thread de réception
    receive_thread = threading.Thread(
        target=receive_data,
        args=(client_socket,),
        daemon=True
    )
    receive_thread.start()

    clock = pygame.time.Clock()

    running = True
    while running:
        # Process events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Update game state every frame
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            player_x -= player_speed
        if keys[pygame.K_RIGHT]:
            player_x += player_speed
        if keys[pygame.K_UP]:
            player_y -= player_speed
        if keys[pygame.K_DOWN]:
            player_y += player_speed

        # Clamp player position to map boundaries
        player_x = max(0, min(player_x, map_width - 50))
        player_y = max(0, min(player_y, map_height - 50))

        # Update camera to follow player smoothly
        target_camera_x = player_x - SCREEN_WIDTH // 2
        target_camera_y = player_y - SCREEN_HEIGHT // 2

        # Clamp camera to map boundaries
        target_camera_x = max(0, min(target_camera_x, map_width - SCREEN_WIDTH))
        target_camera_y = max(0, min(target_camera_y, map_height - SCREEN_HEIGHT))

        # Smooth camera movement
        camera_x += (target_camera_x - camera_x) * camera_speed
        camera_y += (target_camera_y - camera_y) * camera_speed

        # Send position update every frame
        try:
            data = pickle.dumps((player_x, player_y))
            client_socket.send(data)
        except Exception as e:
            print(f"Error sending position: {e}")
            break

        # Draw everything
        screen.fill(BLACK)
        
        # Draw map
        map_manager.draw(screen, camera_x, camera_y)
        
        # Draw other players first
        for other_id, other_player_pos in other_players.items():
            pygame.draw.rect(
                screen,
                (0, 255, 0),
                (other_player_pos[0] - camera_x, other_player_pos[1] - camera_y, 50, 50)
            )
        
        # Draw current player on top
        pygame.draw.rect(screen, player_color, (player_x - camera_x, player_y - camera_y, 50, 50))
        
        pygame.display.flip()
        clock.tick(60)

    client_socket.close()
    pygame.quit()


if __name__ == "__main__":
    main()
