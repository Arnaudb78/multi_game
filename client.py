import pygame
import socket
import threading
import pickle
import uuid
import logging
from menu import Menu

# Configuration du jeu
DEFAULT_PORT = 12345
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
player_speed = 5

WHITE = (255, 255, 255)

# Initialisation pygame
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption('Jeu Shooter Multijoueur')
font = pygame.font.Font(None, 28)

# Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Variables globales
client_id = None
other_players = {}  # {client_id: (x, y, pseudo, couleur)}

# === SERVER CODE ===
players = {}  # {client_id: (socket, position, pseudo, couleur)}
client_sockets = {}  # {socket: client_id}

class ClientThread(threading.Thread):
    def __init__(self, client_socket, client_address):
        threading.Thread.__init__(self)
        self.client_socket = client_socket
        self.client_address = client_address
        self.client_id = str(uuid.uuid4())
        players[self.client_id] = (client_socket, (400, 300), "", (255, 0, 0))
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
                        color = parsed['color']
                        players[self.client_id] = (self.client_socket, pos, pseudo, color)
                    else:
                        continue
                except Exception as e:
                    logger.error(f"Erreur parsing: {e}")
                    continue

                for sock in client_sockets:
                    for pid, (_, pos, pseudo, color) in players.items():
                        try:
                            sock.send(pickle.dumps((pid, pos, pseudo, color)))
                        except:
                            continue
        finally:
            self.client_socket.close()
            if self.client_id in players:
                msg = ('disconnect', self.client_id)
                for sock in client_sockets:
                    try:
                        sock.send(pickle.dumps(msg))
                    except:
                        pass
                del players[self.client_id]
            if self.client_socket in client_sockets:
                del client_sockets[self.client_socket]
            logger.info(f"Client déconnecté: {self.client_address}")


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', DEFAULT_PORT))
    server_socket.listen(5)
    logger.info(f"Serveur démarré sur le port {DEFAULT_PORT}")
    while True:
        try:
            client_socket, addr = server_socket.accept()
            logger.info(f"Connexion de {addr}")
            thread = ClientThread(client_socket, addr)
            thread.start()
        except:
            break

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
                        pid, pos, pseudo, color = msg
                        if pid != client_id:
                            other_players[pid] = (pos, pseudo, color)
                except pickle.UnpicklingError:
                    break
        except Exception as e:
            print(f"Erreur réception: {e}")
            break

def main():
    global SCREEN_WIDTH, SCREEN_HEIGHT
    player_x, player_y = 400, 300

    menu = Menu(screen)
    action, ip = menu.show()
    if action is None:
        pygame.quit()
        return

    pseudo, color = menu.show_profile_selection()
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
    except Exception as e:
        print(f"Erreur de connexion: {e}")
        pygame.quit()
        return

    threading.Thread(target=receive_data, args=(sock,), daemon=True).start()
    clock = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]: player_x -= player_speed
        if keys[pygame.K_RIGHT]: player_x += player_speed
        if keys[pygame.K_UP]: player_y -= player_speed
        if keys[pygame.K_DOWN]: player_y += player_speed

        player_x = max(0, min(player_x, SCREEN_WIDTH - 50))
        player_y = max(0, min(player_y, SCREEN_HEIGHT - 50))

        try:
            msg = {'position': (player_x, player_y), 'pseudo': pseudo, 'color': color}
            sock.send(pickle.dumps(msg))
        except:
            break

        screen.fill((0, 0, 0))
        for pid, (pos, name, col) in other_players.items():
            pygame.draw.rect(screen, col, (pos[0], pos[1], 50, 50))
            label = font.render(name, True, WHITE)
            screen.blit(label, (pos[0], pos[1] - 20))

        pygame.draw.rect(screen, color, (player_x, player_y, 50, 50))
        label = font.render(pseudo, True, WHITE)
        screen.blit(label, (player_x, player_y - 20))

        pygame.display.flip()
        clock.tick(60)

    sock.close()
    pygame.quit()

if __name__ == "__main__":
    main()