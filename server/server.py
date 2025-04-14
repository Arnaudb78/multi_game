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
players = {}  # {client_id: (socket, position, pseudo, soldier_type)}
client_sockets = {}  # {socket: client_id}

# Dictionnaire des tirs actifs
shots = {}  # {shot_id: {'position': (x, y), 'direction': (dx, dy), 'speed': s, 'player_id': pid}}


class ClientThread(threading.Thread):
    def __init__(self, client_socket, client_address):
        threading.Thread.__init__(self)
        self.client_socket = client_socket
        self.client_address = client_address
        self.client_id = str(uuid.uuid4())
        players[self.client_id] = (client_socket, (400, 300), "", "falcon")  # Position initiale avec pseudo et type
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
            for player_id, (_, pos, pseudo, soldier_type) in players.items():
                if player_id != self.client_id:  # Ne pas envoyer sa propre position
                    if not self.send_data((player_id, pos, pseudo, soldier_type)):
                        return
            
            last_update = 0
            while True:
                data = self.client_socket.recv(BUFFER_SIZE)
                if not data:
                    break

                # Mettre à jour la position du joueur ou gérer les tirs
                try:
                    data = pickle.loads(data)
                    if isinstance(data, dict) and 'shot' in data:
                        # Gérer un nouveau tir
                        shot_id = str(uuid.uuid4())
                        shot_data = data['shot']
                        # Ajouter l'ID du joueur qui a tiré
                        shot_data['player_id'] = self.client_id
                        shots[shot_id] = shot_data
                        
                        # Envoyer immédiatement le tir à tous les clients
                        for client_socket in client_sockets.keys():
                            try:
                                client_socket.send(pickle.dumps(('shot', shot_id, shot_data)))
                            except socket.error:
                                continue
                        
                        # Mettre à jour la position du joueur après le tir
                        if isinstance(data, dict) and 'position' in data:
                            position = data['position']
                            pseudo = data.get('pseudo', "")
                            soldier_type = data.get('soldier_type', "falcon")
                            players[self.client_id] = (self.client_socket, position, pseudo, soldier_type)
                    else:
                        # Mettre à jour la position du joueur
                        if isinstance(data, dict) and 'position' in data:
                            position = data['position']
                            pseudo = data.get('pseudo', "")
                            soldier_type = data.get('soldier_type', "falcon")
                            players[self.client_id] = (self.client_socket, position, pseudo, soldier_type)
                        else:
                            position = data
                            players[self.client_id] = (self.client_socket, position, "", "falcon")
                except Exception as e:
                    logger.error(f"Error processing player data: {e}")
                    continue

                # Envoyer les positions de tous les joueurs à tous les clients
                for client_socket in client_sockets.keys():
                    try:
                        # Envoyer toutes les positions à ce client
                        for player_id, (_, pos, pseudo, soldier_type) in players.items():
                            if not self.send_data((player_id, pos, pseudo, soldier_type)):
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
                for client_socket in client_sockets.keys():
                    try:
                        pickle.dumps(disconnect_message)
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
