import pygame
import socket
import threading
import pickle
import uuid
import logging
import sys
import os
import time

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from menu import Menu
from game.map_manager import MapManager
from game.soldier import Soldier, SoldierState, SoldierDirection

# Configuration du jeu
DEFAULT_PORT = 12345
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
player_speed = 5
HOST = '0.0.0.0'  # Adresse de connection
PORT = 12345  # Port à utiliser

WHITE = (255, 255, 255)
RED = (255, 0, 0)

# Initialisation pygame
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption('Jeu Shooter Multijoueur')
font = pygame.font.Font(None, 28)

# Logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Variables globales
client_id = None
other_players = {}  # {client_id: (x, y, pseudo, soldier_type, health, bullets)}
other_soldiers = {}  # Cache for other players' Soldier objects
player = None

# Camera
camera_x = 0
camera_y = 0
camera_speed = 0.1

# Map
map_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'map', 'map.tmx')
map_manager = MapManager(map_path)
map_width, map_height = map_manager.get_map_size()

# === SERVER CODE ===
players = {}  # {client_id: (socket, position, pseudo, soldier_type, health, bullets)}
client_sockets = {}


class ClientThread(threading.Thread):
    def __init__(self, server_address, server_port):
        threading.Thread.__init__(self)
        self.server_address = server_address
        self.server_port = server_port
        self.socket = None
        self.client_id = None
        self.players = {}  # {client_id: (position, pseudo, soldier_type, health, bullets, damage_resistance)}
        self.damage_messages = []  # Liste des messages de dégâts à afficher
        self.running = True

    def receive_data(self):
        while self.running:
            try:
                data = self.socket.recv(4096)
                if not data:
                    break

                message = pickle.loads(data)
                
                if isinstance(message, tuple):
                    if message[0] == 'init':
                        self.client_id = message[1]
                        logger.info(f"Connected to server with ID: {self.client_id}")
                    elif message[0] == 'disconnect':
                        player_id = message[1]
                        if player_id in self.players:
                            del self.players[player_id]
                    else:
                        player_id, position, pseudo, soldier_type, health, bullets, damage_resistance = message
                        self.players[player_id] = (position, pseudo, soldier_type, health, bullets, damage_resistance)
                elif isinstance(message, dict) and message.get('type') == 'damage':
                    # Gérer la notification de dégâts
                    damage_amount = message.get('amount', 0)
                    attacker_id = message.get('from')
                    if attacker_id in self.players:
                        attacker_pseudo = self.players[attacker_id][1]
                        self.damage_messages.append({
                            'text': f"-{damage_amount:.1f}",
                            'position': self.players[self.client_id][0],  # Position du joueur touché
                            'time': time.time(),
                            'attacker': attacker_pseudo
                        })
                        
                        # Mettre à jour la santé du joueur local
                        if self.client_id in self.players:
                            pos, pseudo, st, health, bullets, dr = self.players[self.client_id]
                            self.players[self.client_id] = (pos, pseudo, st, max(0, health - damage_amount), bullets, dr)

            except socket.error as e:
                logger.error(f"Socket error in receive_data: {e}")
                break
            except Exception as e:
                logger.error(f"Error in receive_data: {e}")
                continue

    def run(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_address, self.server_port))
            self.receive_data()
        except Exception as e:
            logger.error(f"Error in client thread: {e}")
        finally:
            if self.socket:
                self.socket.close()


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    logger.info(f"Serveur démarré sur {HOST}:{PORT}")

    while True:
        client_socket, client_address = server_socket.accept()
        logger.info(f"Nouvelle connexion de {client_address}")
        client_thread = ClientThread(client_address[0], PORT)
        client_thread.start()


# === CLIENT CODE ===
def receive_data(sock):
    global other_players, client_id
    buffer = b""
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                break
            buffer += data
            while len(buffer):
                try:
                    msg = pickle.loads(buffer)
                    buffer = b""
                    if msg[0] == 'init':
                        client_id = msg[1]
                    elif msg[0] == 'disconnect':
                        if msg[1] in other_players:
                            del other_players[msg[1]]
                    else:
                        pid, pos, pseudo, soldier_type, health, bullets = msg
                        if pid != client_id:
                            other_players[pid] = (pos, pseudo, soldier_type, health, bullets)
                except pickle.UnpicklingError:
                    break
        except socket.error as e:
            print(f"Erreur réception: {e}")
            break


def main():
    global SCREEN_WIDTH, SCREEN_HEIGHT, camera_x, camera_y, player, other_soldiers
    player_x, player_y = 400, 300

    menu = Menu(screen)
    action, ip = menu.show()
    if action is None:
        pygame.quit()
        return

    pseudo, soldier_type = menu.show_profile_selection()
    if pseudo is None:
        pygame.quit()
        return

    if action == 'host':
        threading.Thread(target=start_server, daemon=True).start()
        host = '127.0.0.1'
    else:
        host = ip

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, DEFAULT_PORT))
    except socket.error as e:
        print(f"Erreur de connexion: {e}")
        pygame.quit()
        return

    threading.Thread(target=receive_data, args=(sock,), daemon=True).start()
    clock = pygame.time.Clock()
    running = True

    # Create player soldier
    player = Soldier(player_x, player_y, soldier_type, pseudo)

    # Game state
    game_over = False
    respawn_position = (400, 300)  # Default respawn position
    respawn_cooldown = 0
    respawn_delay = 1000  # 1 second delay before respawn

    # Boucle principale du jeu
    last_cleanup = time.time()
    
    while running:
        current_time = time.time()
        
        # Nettoyer les messages de dégâts anciens
        if current_time - last_cleanup > 0.1:  # Nettoyage toutes les 100ms
            other_players = {pid: data for pid, data in other_players.items() if current_time - data[5] < 2.0}
            last_cleanup = current_time

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        keys = pygame.key.get_pressed()
        
        # Handle respawn on R key when dead
        if player.health <= 0:
            game_over = True
            
            # Check for R key press and respawn cooldown
            if keys[pygame.K_r] and current_time - respawn_cooldown > respawn_delay:
                game_over = False
                player.revive(respawn_position[0], respawn_position[1])
                respawn_cooldown = current_time
                
        if not game_over:
            player.update(keys, [other_soldiers.get(pid) for pid in other_soldiers])

            # Clamp player position to map boundaries
            player.x = max(0, min(player.x, map_width - 50))
            player.y = max(0, min(player.y, map_height - 50))

            # Update camera to follow player smoothly
            target_camera_x = player.x - SCREEN_WIDTH // 2
            target_camera_y = player.y - SCREEN_HEIGHT // 2

            # Clamp camera to map boundaries
            target_camera_x = max(0, min(target_camera_x, map_width - SCREEN_WIDTH))
            target_camera_y = max(0, min(target_camera_y, map_height - SCREEN_HEIGHT))

            # Smooth camera movement
            camera_x += (target_camera_x - camera_x) * camera_speed
            camera_y += (target_camera_y - camera_y) * camera_speed

            # Use the serialize_bullet method to get safe bullet data for network
            try:
                msg = {
                    'position': (player.x, player.y),
                    'pseudo': pseudo,
                    'soldier_type': soldier_type,
                    'health': player.health,
                    'bullets': player.serialize_bullet(),
                    'is_dead': player.is_dead
                }
                sock.send(pickle.dumps(msg))
            except socket.error as e:
                print(f"Network error: {e}")
                break
            except Exception as e:
                print(f"Error preparing network data: {e}")

        screen.fill((0, 0, 0))
        
        # Draw map
        map_manager.draw(screen, camera_x, camera_y)
        
        # Draw other players
        for pid, (pos, name, soldier_type, health, bullets) in other_players.items():
            if pid not in other_soldiers:
                # Create new soldier object only if it doesn't exist
                other_soldiers[pid] = Soldier(pos[0], pos[1], soldier_type, name)
            else:
                # Update existing soldier's position and health
                other_soldiers[pid].x = pos[0]
                other_soldiers[pid].y = pos[1]
                other_soldiers[pid].health = health
                
                # Apply death state if health is 0
                if health <= 0 and not other_soldiers[pid].is_dead:
                    other_soldiers[pid].is_dead = True
                    other_soldiers[pid].state = SoldierState.DEAD
                    other_soldiers[pid].animation_frame = 0
                
                # Clear and update bullets
                other_soldiers[pid].bullets.clear()
                for bullet_data in bullets:
                    try:
                        x, y, direction = bullet_data
                        # Convert string direction back to enum if needed
                        if isinstance(direction, str):
                            for dir_enum in SoldierDirection:
                                if dir_enum.value == direction:
                                    direction = dir_enum
                                    break
                        from game.soldier import Bullet
                        bullet = Bullet(x, y, direction)
                        other_soldiers[pid].bullets.append(bullet)
                    except Exception as e:
                        print(f"Error creating bullet from network data: {e}")
                        continue
                
            # Draw the soldier and their bullets
            other_soldiers[pid].draw(screen, camera_x, camera_y)

        # Clean up disconnected players
        disconnected_players = set(other_soldiers.keys()) - set(other_players.keys())
        for pid in disconnected_players:
            del other_soldiers[pid]

        # Draw current player
        if not game_over:
            player.draw(screen, camera_x, camera_y)
        else:
            # Show game over and respawn message
            game_over_font = pygame.font.Font(None, 72)
            game_over_text = game_over_font.render("GAME OVER", True, RED)
            respawn_font = pygame.font.Font(None, 36)
            respawn_text = respawn_font.render("Press R to respawn", True, WHITE)
            
            screen.blit(game_over_text, 
                        (SCREEN_WIDTH // 2 - game_over_text.get_width() // 2, 
                         SCREEN_HEIGHT // 2 - 50))
            screen.blit(respawn_text, 
                        (SCREEN_WIDTH // 2 - respawn_text.get_width() // 2, 
                         SCREEN_HEIGHT // 2 + 20))

        # Dessiner les messages de dégâts
        for msg in other_players.values():
            # Calculer la position du message (légèrement au-dessus du joueur)
            x, y = msg[0]
            y -= 20  # Décalage vers le haut
            
            # Calculer l'alpha (transparence) en fonction du temps
            age = current_time - msg[5]
            alpha = max(0, min(255, int(255 * (1 - age / 2.0))))
            
            # Créer le texte avec l'attaquant
            text = f"{msg[1]} {msg[2]} {msg[3]:.1f}"
            font = pygame.font.Font(None, 24)
            text_surface = font.render(text, True, RED)
            text_surface.set_alpha(alpha)
            
            # Dessiner le texte
            screen.blit(text_surface, (x - text_surface.get_width() // 2, y))

        pygame.display.flip()
        clock.tick(60)

    sock.close()
    pygame.quit()


if __name__ == "__main__":
    main()