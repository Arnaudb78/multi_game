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
                    try:
                        # Format standard: (client_id, position, pseudo, soldier_type)
                        player_data = (player_id, pos, pseudo, soldier_type)
                        self.client_socket.send(pickle.dumps(player_data))
                    except socket.error as e:
                        logger.error(f"Error sending player data: {e}")
                        return
            
            # Envoyer tous les tirs actifs au nouveau client
            for shot_id, shot_data in shots.items():
                try:
                    # Format standard: ('shot', shot_id, shot_data)
                    shot_message = ('shot', shot_id, shot_data)
                    self.client_socket.send(pickle.dumps(shot_message))
                except socket.error as e:
                    logger.error(f"Error sending shot data: {e}")
                    return
            
            last_update = 0
            while True:
                data = self.client_socket.recv(BUFFER_SIZE)
                if not data:
                    break

                # Mettre à jour la position du joueur ou gérer les tirs
                try:
                    parsed_data = pickle.loads(data)
                    
                    # Handle shot data
                    if isinstance(parsed_data, dict) and 'shot' in parsed_data:
                        shot_id = str(uuid.uuid4())
                        shot_data = parsed_data['shot']
                        shot_data['player_id'] = self.client_id
                        shots[shot_id] = shot_data
                        
                        # Broadcast shot to all clients immediately
                        shot_message = ('shot', shot_id, shot_data)
                        for client_socket in client_sockets.keys():
                            try:
                                client_socket.send(pickle.dumps(shot_message))
                            except socket.error as e:
                                logger.error(f"Error sending shot: {e}")
                                continue
                    
                    # Handle position data
                    elif isinstance(parsed_data, dict) and 'position' in parsed_data:
                        position = parsed_data['position']
                        pseudo = parsed_data.get('pseudo', "")
                        soldier_type = parsed_data.get('soldier_type', "falcon")
                        players[self.client_id] = (self.client_socket, position, pseudo, soldier_type)
                        
                        # Broadcast position update to other clients only
                        pos_message = (self.client_id, position, pseudo, soldier_type)
                        for client_socket in client_sockets.keys():
                            if client_socket != self.client_socket:  # Don't send back to originating client
                                try:
                                    client_socket.send(pickle.dumps(pos_message))
                                except socket.error as e:
                                    logger.error(f"Error sending position: {e}")
                                    continue
                    else:
                        logger.warning(f"Unrecognized data format: {type(parsed_data)}")
                                    
                except Exception as e:
                    logger.error(f"Error processing data: {e}")
                    continue

        except socket.error as e:
            logger.error(f"Error in client thread: {e}")
        finally:
            self.client_socket.close()
            if self.client_id in players:
                # Notifier tous les clients de la déconnexion
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

# Fonction pour nettoyer les tirs périodiquement
def cleanup_shots():
    while True:
        try:
            time.sleep(1.0)  # Attendre 1 seconde entre les nettoyages
            
            shots_to_remove = []
            map_width = 2000  # Taille approximative de la carte
            map_height = 2000
            
            # Vérifier chaque tir et marquer ceux qui sont sortis de la carte
            for shot_id, shot_data in shots.items():
                position = shot_data['position']
                # Si le tir est sorti des limites de la carte
                if (position[0] < -100 or position[0] > map_width + 100 or
                    position[1] < -100 or position[1] > map_height + 100):
                    shots_to_remove.append(shot_id)
            
            # Supprimer les tirs marqués
            for shot_id in shots_to_remove:
                if shot_id in shots:
                    del shots[shot_id]
                    
            # Limiter le nombre de tirs actifs pour éviter les fuites de mémoire
            if len(shots) > 1000:
                # Supprimer les 200 plus anciens tirs
                for shot_id in list(shots.keys())[:200]:
                    del shots[shot_id]
                    
        except Exception as e:
            logger.error(f"Error in cleanup thread: {e}")

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    logger.info(f"Serveur démarré sur {HOST}:{PORT}")
    
    # Démarrer le thread de nettoyage des tirs
    cleanup_thread = threading.Thread(target=cleanup_shots, daemon=True)
    cleanup_thread.start()

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
