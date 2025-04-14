import socket
import threading
import logging
import pickle
import uuid
import time
from soldier import Soldier, SoldierDirection


# Configuration du serveur
HOST = '0.0.0.0'  # Adresse de connection
PORT = 12345        # Port à utiliser
UPDATE_RATE = 20  # Updates per second
POSITION_THRESHOLD = 2.0  # Minimum distance change to trigger update

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Dictionnaire des joueurs avec leurs positions et états
players = {}  # {client_id: (socket, soldier, last_update_time)}
client_sockets = {}  # {socket: client_id}
bullets = []  # List of active bullets: [(x, y, direction, owner_id)]


class ClientThread(threading.Thread):
    def __init__(self, client_socket, client_address):
        threading.Thread.__init__(self)
        self.client_socket = client_socket
        self.client_address = client_address
        self.client_id = str(uuid.uuid4())
        # Create initial soldier
        initial_soldier = Soldier(400, 300, "Falcon", "Player")
        players[self.client_id] = (client_socket, initial_soldier, time.time())
        client_sockets[client_socket] = self.client_id
        self.last_position = (400, 300)

    def send_data(self, data):
        try:
            self.client_socket.send(pickle.dumps(data))
        except socket.error as e:
            logger.error(f"Error sending data to client: {e}")
            return False
        return True

    def update_bullets(self):
        current_time = time.time()
        # Update bullet positions
        for bullet in bullets[:]:
            x, y, direction, owner_id = bullet
            # Update position based on direction
            if direction == "LEFT":
                x -= 10
            elif direction == "RIGHT":
                x += 10
            elif direction == "UP":
                y -= 10
            elif direction == "DOWN":
                y += 10
            
            # Check for collisions with players
            for pid, (_, soldier, _) in players.items():
                if pid != owner_id:  # Don't check collision with shooter
                    dx = x - soldier.x
                    dy = y - soldier.y
                    distance = (dx*dx + dy*dy) ** 0.5
                    if distance < 20:  # Collision radius
                        # Apply damage
                        soldier.take_damage(10)
                        bullets.remove(bullet)
                        break
            
            # Remove bullets that are off screen
            if x < -100 or x > 2000 or y < -100 or y > 2000:
                bullets.remove(bullet)
            else:
                # Update bullet position
                bullets[bullets.index(bullet)] = (x, y, direction, owner_id)

    def run(self):
        try:
            # Send client ID
            if not self.send_data(('init', self.client_id)):
                return
            
            # Send current state of all players to new client
            for player_id, (_, soldier, _) in players.items():
                if player_id != self.client_id:
                    if not self.send_data(('player', player_id, soldier.x, soldier.y, 
                                         soldier.soldier_type, soldier.name, soldier.health)):
                        return
            
            while True:
                data = self.client_socket.recv(4096)
                if not data:
                    break

                try:
                    msg = pickle.loads(data)
                    current_time = time.time()
                    
                    if msg[0] == 'position':
                        position = msg[1]
                        # Check if position has changed significantly
                        dx = position[0] - self.last_position[0]
                        dy = position[1] - self.last_position[1]
                        distance = (dx*dx + dy*dy) ** 0.5
                        
                        if distance >= POSITION_THRESHOLD or current_time - players[self.client_id][2] >= 1.0/UPDATE_RATE:
                            self.last_position = position
                            # Update soldier position
                            players[self.client_id][1].x = position[0]
                            players[self.client_id][1].y = position[1]
                            players[self.client_id] = (players[self.client_id][0], 
                                                     players[self.client_id][1], 
                                                     current_time)
                            
                            # Send updates to all clients
                            for client_socket in client_sockets.keys():
                                try:
                                    # Send all player positions and states
                                    for player_id, (_, soldier, _) in players.items():
                                        if not self.send_data(('player', player_id, soldier.x, soldier.y,
                                                             soldier.soldier_type, soldier.name, soldier.health)):
                                            break
                                    # Send all active bullets
                                    for bullet in bullets:
                                        if not self.send_data(('bullet', *bullet)):
                                            break
                                except socket.error as e:
                                    logger.error(f"Error sending data to client: {e}")
                                    break
                    
                    elif msg[0] == 'shoot':
                        # Add new bullet
                        direction = msg[1]
                        bullets.append((self.last_position[0], self.last_position[1], direction, self.client_id))
                        # Send bullet creation to all clients
                        for client_socket in client_sockets.keys():
                            try:
                                self.send_data(('bullet', self.last_position[0], self.last_position[1], direction, self.client_id))
                            except socket.error:
                                continue
                
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    continue

                # Update bullets
                self.update_bullets()

        except socket.error as e:
            logger.error(f"Error in client thread: {e}")
        finally:
            self.client_socket.close()
            if self.client_id in players:
                # Notify all clients of disconnect
                disconnect_message = ('disconnect', self.client_id)
                for client_socket in client_sockets.keys():
                    try:
                        client_socket.send(pickle.dumps(disconnect_message))
                    except socket.error:
                        pass
                del players[self.client_id]
            if self.client_socket in client_sockets:
                del client_sockets[self.client_socket]
            logger.info(f"Client disconnected: {self.client_address}")


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    logger.info(f"Serveur démarré sur {HOST}:{PORT}")

    while True:
        try:
            client_socket, client_address = server_socket.accept()
            logger.info(f"Connexion reçue de {client_address}")
            new_thread = ClientThread(client_socket, client_address)
            new_thread.start()
        except socket.error as e:
            logger.error(f"Error accepting connection: {e}")


if __name__ == "__main__":
    start_server()
