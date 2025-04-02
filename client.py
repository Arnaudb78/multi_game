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

# Joueur
player_x, player_y = 400, 300
player_speed = 5
player_color = (255, 0, 0)  # Rouge pour le joueur

# Dictionnaire des autres joueurs
other_players = {}  # {client_id: (x, y)}


def receive_data(client_socket):
    global other_players
    while True:
        try:
            data = client_socket.recv(1024)
            if data:
                client_id, position = pickle.loads(data)
                other_players[client_id] = position
        except Exception as e:
            print(f"Error receiving data: {e}")
            break


def main():
    global player_x, player_y

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
        for other_player_pos in other_players.values():
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
