import pygame
import socket
import threading
import pickle

# Configuration du client
HOST = '127.0.0.1'
PORT = 12345

# Initialisation de Pygame
pygame.init()

# Dimensions de la fenêtre du jeu
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption('Jeu Shooter Multijoueur')

# Couleurs
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)

# Police
font = pygame.font.Font(None, 74)

# Joueur
player_x, player_y = 400, 300
player_speed = 5
player_color = (255, 0, 0)  # Rouge pour le joueur
client_id = None

# Dictionnaire des autres joueurs
other_players = {}  # {client_id: (x, y)}


def draw_menu():
    screen.fill(BLACK)
    
    # Titre
    title = font.render(
        'Jeu Shooter Multijoueur', True, WHITE
    )
    title_rect = title.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/3))
    screen.blit(title, title_rect)
    
    # Bouton Start
    start_button = font.render('Start Game', True, WHITE)
    start_rect = start_button.get_rect(
        center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2)
    )
    pygame.draw.rect(screen, GREEN, start_rect.inflate(20, 20))
    screen.blit(start_button, start_rect)
    
    # Bouton Quit
    quit_button = font.render('Quit', True, WHITE)
    quit_rect = quit_button.get_rect(
        center=(SCREEN_WIDTH/2, 2*SCREEN_HEIGHT/3)
    )
    pygame.draw.rect(screen, RED, quit_rect.inflate(20, 20))
    screen.blit(quit_button, quit_rect)
    
    pygame.display.flip()
    return start_rect, quit_rect


def receive_data(client_socket):
    global other_players, client_id
    while True:
        try:
            data = client_socket.recv(1024)
            if data:
                message = pickle.loads(data)
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
        except Exception as e:
            print(f"Error receiving data: {e}")
            break


def main():
    global player_x, player_y
    
    # Menu principal
    menu_running = True
    while menu_running:
        start_rect, quit_rect = draw_menu()
        
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

    # Connexion au serveur
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((HOST, PORT))

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
        screen.fill((0, 0, 0))

        # Gérer les événements
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Gérer les mouvements
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            player_x -= player_speed
        if keys[pygame.K_RIGHT]:
            player_x += player_speed
        if keys[pygame.K_UP]:
            player_y -= player_speed
        if keys[pygame.K_DOWN]:
            player_y += player_speed

        # Limiter les mouvements aux bords de l'écran
        player_x = max(0, min(player_x, SCREEN_WIDTH - 50))
        player_y = max(0, min(player_y, SCREEN_HEIGHT - 50))

        # Dessiner le joueur
        pygame.draw.rect(screen, player_color, (player_x, player_y, 50, 50))

        # Envoyer la position au serveur
        try:
            data = pickle.dumps((player_x, player_y))
            client_socket.send(data)
        except Exception as e:
            print(f"Error sending position: {e}")
            break

        # Dessiner les autres joueurs
        for other_id, other_player_pos in other_players.items():
            pygame.draw.rect(
                screen,
                (0, 255, 0),
                (other_player_pos[0], other_player_pos[1], 50, 50)
            )

        pygame.display.flip()
        clock.tick(60)

    client_socket.close()
    pygame.quit()


if __name__ == "__main__":
    main()
