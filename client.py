import pygame
import socket
import threading
import pickle
import uuid
import logging
from menu import Menu
from map_manager import MapManager
from soldier import Soldier

# Configuration du jeu
DEFAULT_PORT = 12345
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
player_speed = 5
HOST = '0.0.0.0'  # Adresse de connection
PORT = 12345  # Port à utiliser
NETWORK_UPDATE_RATE = 20  # Updates per second

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
other_soldiers = {}  # {client_id: Soldier}  # Cache of soldier objects
player = None

# Camera
camera_x = 0
camera_y = 0
camera_speed = 0.1

# Map
map_manager = MapManager("assets/map/map.tmx")
map_width, map_height = map_manager.get_map_size()

# === SERVER CODE ===
players = {}  # {client_id: (socket, position, pseudo, soldier_type)}
client_sockets = {}


class ClientThread(threading.Thread):
    def __init__(self, client_socket, client_address):
        threading.Thread.__init__(self)
        self.client_socket = client_socket
        self.client_address = client_address
        self.client_id = str(uuid.uuid4())
        players[self.client_id] = (client_socket, (400, 300), "", "Falcon")
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
    global other_players, other_soldiers, client_id
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
                            if msg[1] in other_soldiers:
                                del other_soldiers[msg[1]]
                    else:
                        pid, pos, pseudo, soldier_type = msg
                        if pid != client_id:
                            other_players[pid] = (pos, pseudo, soldier_type)
                            # Create or update soldier object
                            if pid not in other_soldiers:
                                other_soldiers[pid] = Soldier(pos[0], pos[1], soldier_type, pseudo)
                            else:
                                other_soldiers[pid].x = pos[0]
                                other_soldiers[pid].y = pos[1]
                except pickle.UnpicklingError:
                    break
        except socket.error as e:
            print(f"Erreur réception: {e}")
            break


def main():
    global SCREEN_WIDTH, SCREEN_HEIGHT, camera_x, camera_y, player, last_network_update
    player_x, player_y = 400, 300
    last_network_update = 0  # Initialize the network update timer

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
        current_time = pygame.time.get_ticks()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        keys = pygame.key.get_pressed()
        player.update(keys)

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

        # Send position update at fixed rate
        if current_time - last_network_update >= 1000 / NETWORK_UPDATE_RATE:
            try:
                msg = {
                    'position': (player.x, player.y),
                    'pseudo': pseudo,
                    'soldier_type': soldier_type
                }
                sock.send(pickle.dumps(msg))
                last_network_update = current_time
            except socket.error:
                break

        screen.fill((0, 0, 0))
        
        # Draw map
        map_manager.draw(screen, camera_x, camera_y)
        
        # Draw other players
        for pid, soldier in other_soldiers.items():
            soldier.draw(screen, camera_x, camera_y)

        # Draw current player
        player.draw(screen, camera_x, camera_y)

        pygame.display.flip()
        clock.tick(60)

    sock.close()
    pygame.quit()


if __name__ == "__main__":
    main()