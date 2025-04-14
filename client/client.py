import pygame
import socket
import threading
import pickle
import uuid
import logging
import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from menu import Menu
from game.map_manager import MapManager
from game.soldier import Soldier, SoldierDirection, SoldierState

# Configuration du jeu
DEFAULT_PORT = 12345
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
player_speed = 5
HOST = '0.0.0.0'  # Adresse de connection
PORT = 12345  # Port à utiliser

WHITE = (255, 255, 255)

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
other_players = {}  # {client_id: (x, y, pseudo, soldier_type)}
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

# Variables globales pour les tirs
shots = {}  # {shot_id: {'position': (x, y), 'direction': (dx, dy), 'speed': s, 'player_id': pid}}
bullet_images = {}  # Cache pour les images de balles

# === SERVER CODE ===
players = {}  # {client_id: (socket, position, pseudo, soldier_type)}
client_sockets = {}


class ClientThread(threading.Thread):
    def __init__(self, client_socket, client_address):
        threading.Thread.__init__(self)
        self.client_socket = client_socket
        self.client_address = client_address
        self.client_id = str(uuid.uuid4())
        players[self.client_id] = (client_socket, (400, 300), "", "falcon")
        client_sockets[client_socket] = self.client_id

    def send_data(self, data):
        try:
            self.client_socket.send(pickle.dumps(data))
            return True
        except socket.error as e:
            logger.error(f"Erreur envoi client: {e}")
            return False

    def run(self):
        try:
            if not self.send_data(('init', self.client_id)):
                return

            while True:
                data = self.client_socket.recv(4096)
                if not data:
                    break

                try:
                    parsed = pickle.loads(data)
                    if isinstance(parsed, dict):
                        pos = parsed['position']
                        pseudo = parsed['pseudo']
                        soldier_type = parsed['soldier_type']
                        players[self.client_id] = (
                            self.client_socket, pos, pseudo, soldier_type
                        )
                    else:
                        continue
                except Exception as e:
                    logger.error(f"Erreur parsing: {e}")
                    continue

                for sock in client_sockets:
                    for pid, (_, pos, pseudo, soldier_type) in players.items():
                        try:
                            sock.send(pickle.dumps((pid, pos, pseudo, soldier_type)))
                        except socket.error:
                            continue
        finally:
            self.client_socket.close()
            if self.client_id in players:
                msg = ('disconnect', self.client_id)
                for sock in client_sockets:
                    try:
                        sock.send(pickle.dumps(msg))
                    except socket.error:
                        pass
                del players[self.client_id]
            if self.client_socket in client_sockets:
                del client_sockets[self.client_socket]
            logger.info(f"Client déconnecté: {self.client_address}")


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    logger.info(f"Serveur démarré sur {HOST}:{PORT}")

    while True:
        client_socket, client_address = server_socket.accept()
        logger.info(f"Nouvelle connexion de {client_address}")
        client_thread = ClientThread(client_socket, client_address)
        client_thread.start()


# === CLIENT CODE ===
def receive_data(sock):
    global other_players, client_id, shots
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
                        # Supprimer les tirs du joueur déconnecté
                        shots_to_remove = [shot_id for shot_id, shot_data in shots.items() if shot_data.get('player_id') == msg[1]]
                        for shot_id in shots_to_remove:
                            del shots[shot_id]
                    elif msg[0] == 'shot':
                        # Ajouter le tir à la liste des tirs avec son ID
                        _, shot_id, shot_data = msg
                        if shot_id not in shots:  # Only add if not already present
                            shots[shot_id] = shot_data
                    else:
                        try:
                            pid, pos, pseudo, soldier_type = msg
                            if pid != client_id:
                                other_players[pid] = (pos, pseudo, soldier_type)
                        except (ValueError, TypeError):
                            # Skip invalid player data
                            continue
                except pickle.UnpicklingError:
                    break
        except socket.error as e:
            print(f"Erreur réception: {e}")
            break


def load_bullet_images():
    """Charge les images de balles depuis le dossier assets"""
    global bullet_images
    
    # Chemins des dossiers de balles
    bullet_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'Objects', 'Bullet')
    
    # Charger les images de balles horizontales
    horizontal_images = []
    for i in range(1, 11):
        try:
            image_path = os.path.join(bullet_path, f"Horizontal ({i}).png")
            image = pygame.image.load(image_path).convert_alpha()
            image.set_colorkey((0, 0, 0))
            # Redimensionner l'image
            scale_factor = 0.3
            new_size = (int(image.get_width() * scale_factor), int(image.get_height() * scale_factor))
            image = pygame.transform.scale(image, new_size)
            horizontal_images.append(image)
        except Exception as e:
            print(f"Erreur lors du chargement de l'image de balle horizontale {i}: {e}")
    
    # Charger les images de balles verticales
    vertical_images = []
    for i in range(1, 11):
        try:
            image_path = os.path.join(bullet_path, f"Vertical ({i}).png")
            image = pygame.image.load(image_path).convert_alpha()
            image.set_colorkey((0, 0, 0))
            # Redimensionner l'image
            scale_factor = 0.3
            new_size = (int(image.get_width() * scale_factor), int(image.get_height() * scale_factor))
            image = pygame.transform.scale(image, new_size)
            vertical_images.append(image)
        except Exception as e:
            print(f"Erreur lors du chargement de l'image de balle verticale {i}: {e}")
    
    bullet_images = {
        'horizontal': horizontal_images,
        'vertical': vertical_images
    }


def main():
    global SCREEN_WIDTH, SCREEN_HEIGHT, camera_x, camera_y, player, other_soldiers
    player_x, player_y = 400, 300

    # Charger les images de balles
    load_bullet_images()

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

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        keys = pygame.key.get_pressed()
        player.update(keys)

        # Clamp player position to map boundaries
        player.x = max(0, min(player.x, map_width - 50))
        player.y = max(0, min(player.y, map_height - 50))

        # Send position update to server
        try:
            position_data = {
                'position': (player.x, player.y),
                'pseudo': player.name,
                'soldier_type': player.soldier_type
            }
            sock.send(pickle.dumps(position_data))
        except socket.error as e:
            print(f"Error sending position update: {e}")
            break

        # Update camera to follow player smoothly
        target_camera_x = player.x - SCREEN_WIDTH // 2
        target_camera_y = player.y - SCREEN_HEIGHT // 2

        # Clamp camera to map boundaries
        target_camera_x = max(0, min(target_camera_x, map_width - SCREEN_WIDTH))
        target_camera_y = max(0, min(target_camera_y, map_height - SCREEN_HEIGHT))

        # Smooth camera movement
        camera_x += (target_camera_x - camera_x) * camera_speed
        camera_y += (target_camera_y - camera_y) * camera_speed

        # Gestion des tirs
        if keys[pygame.K_SPACE]:  # Supposons que la barre d'espace est utilisée pour tirer
            # Déterminer la direction du tir en fonction de la direction du joueur
            direction = (1, 0)  # Direction par défaut
            if player.direction == SoldierDirection.LEFT:
                direction = (-1, 0)
            elif player.direction == SoldierDirection.RIGHT:
                direction = (1, 0)
            elif player.direction == SoldierDirection.BACK:
                direction = (0, -1)
            elif player.direction == SoldierDirection.FRONT:
                direction = (0, 1)
                
            shot_data = {
                'shot': {
                    'position': (player.x, player.y),
                    'direction': direction,
                    'speed': 10,
                    'player_id': client_id
                }
            }
            try:
                # Envoyer le tir au serveur
                sock.send(pickle.dumps(shot_data))
                # Changer l'état du joueur pour l'animation de tir
                player.state = SoldierState.SHOOT
            except socket.error:
                break

        # Mettre à jour et dessiner les tirs
        shots_to_remove = []
        for shot_id, shot in shots.items():
            # Mettre à jour la position du tir
            shot['position'] = (
                shot['position'][0] + shot['direction'][0] * shot['speed'],
                shot['position'][1] + shot['direction'][1] * shot['speed']
            )
            
            # Vérifier si le tir est sorti de la carte
            if (shot['position'][0] < -100 or shot['position'][0] > map_width + 100 or
                shot['position'][1] < -100 or shot['position'][1] > map_height + 100):
                shots_to_remove.append(shot_id)
                continue
            
            # Déterminer si le tir est horizontal ou vertical
            is_horizontal = abs(shot['direction'][0]) > abs(shot['direction'][1])
            
            # Dessiner le tir avec l'image appropriée
            if is_horizontal and bullet_images['horizontal']:
                # Animation de la balle horizontale
                animation_frame = (pygame.time.get_ticks() // 50) % len(bullet_images['horizontal'])
                bullet_image = bullet_images['horizontal'][animation_frame]
                
                # Ajuster la position pour centrer l'image
                draw_x = int(shot['position'][0] - camera_x - bullet_image.get_width() // 2)
                draw_y = int(shot['position'][1] - camera_y - bullet_image.get_height() // 2)
                
                # Inverser l'image si le tir va vers la gauche
                if shot['direction'][0] < 0:
                    bullet_image = pygame.transform.flip(bullet_image, True, False)
                
                screen.blit(bullet_image, (draw_x, draw_y))
            elif not is_horizontal and bullet_images['vertical']:
                # Animation de la balle verticale
                animation_frame = (pygame.time.get_ticks() // 50) % len(bullet_images['vertical'])
                bullet_image = bullet_images['vertical'][animation_frame]
                
                # Ajuster la position pour centrer l'image
                draw_x = int(shot['position'][0] - camera_x - bullet_image.get_width() // 2)
                draw_y = int(shot['position'][1] - camera_y - bullet_image.get_height() // 2)
                
                # Inverser l'image si le tir va vers le haut
                if shot['direction'][1] < 0:
                    bullet_image = pygame.transform.flip(bullet_image, False, True)
                
                screen.blit(bullet_image, (draw_x, draw_y))
            else:
                # Fallback si les images ne sont pas disponibles
                pygame.draw.circle(screen, (255, 0, 0), (int(shot['position'][0] - camera_x), int(shot['position'][1] - camera_y)), 5)
            
            # Vérifier les collisions avec le joueur local
            if shot.get('player_id') != client_id:  # Ne pas vérifier les collisions avec ses propres tirs
                player_rect = pygame.Rect(player.x - 25, player.y - 25, 50, 50)  # Hitbox centrée
                shot_rect = pygame.Rect(shot['position'][0] - 5, shot['position'][1] - 5, 10, 10)
                if player_rect.colliderect(shot_rect):
                    print(f"Touché par le tir de {shot.get('player_id')}!")
                    shots_to_remove.append(shot_id)
                    # Réduire la santé du joueur
                    player.take_damage(10)
        
        # Supprimer les tirs qui sont sortis de la carte ou ont touché le joueur
        for shot_id in shots_to_remove:
            del shots[shot_id]

        screen.fill((0, 0, 0))
        
        # Draw map
        map_manager.draw(screen, camera_x, camera_y)
        
        # Draw other players
        for pid, (pos, name, soldier_type) in other_players.items():
            if pid not in other_soldiers:
                # Create new soldier object only if it doesn't exist
                other_soldiers[pid] = Soldier(pos[0], pos[1], soldier_type, name)
            else:
                # Update existing soldier's position
                other_soldiers[pid].x = pos[0]
                other_soldiers[pid].y = pos[1]
            other_soldiers[pid].draw(screen, camera_x, camera_y)

        # Clean up disconnected players
        disconnected_players = set(other_soldiers.keys()) - set(other_players.keys())
        for pid in disconnected_players:
            del other_soldiers[pid]

        # Draw current player
        player.draw(screen, camera_x, camera_y)

        pygame.display.flip()
        clock.tick(60)

    sock.close()
    pygame.quit()


if __name__ == "__main__":
    main()