import socket
import threading
import logging
import pickle
import uuid
import time


# Configuration du serveur
HOST = '0.0.0.0'  # Adresse de connection
PORT = 12345        # Port à utiliser
BUFFER_SIZE = 8192  # Increased buffer size
UPDATE_RATE = 30    # Updates per second

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Dictionnaire des joueurs avec leurs positions
players = {}  # {client_id: (socket, position, pseudo, soldier_type, health, bullets)}
client_sockets = {}  # {socket: client_id}


class ClientThread(threading.Thread):
    def __init__(self, client_socket, client_address):
        threading.Thread.__init__(self)
        self.client_socket = client_socket
        self.client_address = client_address
        self.client_id = str(uuid.uuid4())
        # Position initiale, pseudo, type, health, bullets
        players[self.client_id] = (client_socket, (400, 300), "", "falcon", 100, []) 
        client_sockets[client_socket] = self.client_id

    def send_data(self, data):
        try:
            self.client_socket.send(pickle.dumps(data))
        except socket.error as e:
            logger.error(f"Error sending data to client: {e}")
            return False
        return True

    def run(self):
        try:
            # Envoyer l'ID du client
            if not self.send_data(('init', self.client_id)):
                return
            
            # Envoyer l'état actuel de tous les joueurs au nouveau client
            for player_id, (_, player_pos, pseudo, soldier_type, health, bullets) in players.items():
                if player_id != self.client_id:  # Ne pas envoyer sa propre position
                    if not self.send_data((player_id, player_pos, pseudo, soldier_type, health, bullets)):
                        return
            
            last_update = 0
            while True:
                data = self.client_socket.recv(BUFFER_SIZE)
                if not data:
                    break

                # Mettre à jour les données du joueur
                try:
                    player_data = pickle.loads(data)
                    if isinstance(player_data, dict):
                        position = player_data.get('position', (400, 300))
                        pseudo = player_data.get('pseudo', "")
                        soldier_type = player_data.get('soldier_type', "falcon")
                        health = player_data.get('health', 100)
                        bullets = player_data.get('bullets', [])
                        is_dead = player_data.get('is_dead', False)
                        
                        # Only process bullets if player is alive
                        if not is_dead and bullets:
                            bullets_to_remove = []
                            for bullet_idx, bullet in enumerate(bullets):
                                try:
                                    if len(bullet) < 3:
                                        continue  # Skip invalid bullets
                                        
                                    bullet_x, bullet_y, direction = bullet[:3]
                                    for target_id, (_, target_pos, _, _, target_health, _) in players.items():
                                        if target_id != self.client_id:  # Don't damage self
                                            target_x, target_y = target_pos
                                            # Simple distance-based collision
                                            distance = ((bullet_x - target_x) ** 2 + (bullet_y - target_y) ** 2) ** 0.5
                                            if distance < 30:  # Slightly larger collision radius for better hit detection
                                                # Only damage players with health > 0
                                                if target_health > 0:
                                                    # Update target health (-10 damage)
                                                    new_health = max(0, target_health - 10)
                                                    socket_obj, pos, p, st, _, b = players[target_id]
                                                    players[target_id] = (socket_obj, pos, p, st, new_health, b)
                                                    
                                                    # Add kill count/score if the player was killed by this bullet
                                                    if target_health > 0 and new_health <= 0:
                                                        logger.info(f"Player {pseudo} killed {p}")
                                                
                                                # Mark bullet for removal
                                                bullets_to_remove.append(bullet_idx)
                                                break
                                except Exception as e:
                                    logger.error(f"Error processing bullet: {e}")
                                    continue
                                    
                            # Remove bullets that hit targets (in reverse order to avoid index issues)
                            for idx in sorted(bullets_to_remove, reverse=True):
                                if idx < len(bullets):
                                    bullets.pop(idx)
                        
                        # Store updated player data
                        players[self.client_id] = (self.client_socket, position, pseudo, soldier_type, health, bullets)
                except Exception as e:
                    logger.error(f"Error processing player data: {e}")
                    continue

                # Rate limit updates
                current_time = time.time()
                if current_time - last_update >= 1.0 / UPDATE_RATE:
                    last_update = current_time
                    # Envoyer les données de tous les joueurs à tous les clients
                    for client_id, (client_socket, _, _, _, _, _) in players.items():
                        try:
                            # Envoyer toutes les données à ce client
                            for player_id, (_, player_pos, pseudo, soldier_type, health, bullets) in players.items():
                                try:
                                    # Only send data chunks of reasonable size to prevent buffer issues
                                    # Limit bullets if needed
                                    if len(bullets) > 10:
                                        bullets = bullets[:10]
                                        
                                    msg = (player_id, player_pos, pseudo, soldier_type, health, bullets)
                                    client_socket.send(pickle.dumps(msg, protocol=4))  # Use protocol 4 for better compatibility
                                except socket.error as e:
                                    logger.error(f"Error sending data to client {client_id}: {e}")
                                    break
                                except Exception as e:
                                    logger.error(f"Error preparing data for client {client_id}: {e}")
                                    break
                        except socket.error as e:
                            logger.error(f"Error sending data to client: {e}")
                            break

        except socket.error as e:
            logger.error(f"Error in client thread: {e}")
        finally:
            self.client_socket.close()
            if self.client_id in players:
                # Notifier tous les clients de la déconnexion
                disconnect_message = ('disconnect', self.client_id)
                for _, (client_socket, _, _, _, _, _) in players.items():
                    if client_socket != self.client_socket:  # Don't send to disconnected socket
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
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
