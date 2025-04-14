import socket
import threading
import logging
import pickle
import uuid
import time
import traceback


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

# Verrou pour protéger l'accès aux données partagées
data_lock = threading.Lock()

class ClientThread(threading.Thread):
    def __init__(self, client_socket, client_address):
        threading.Thread.__init__(self)
        self.client_socket = client_socket
        self.client_address = client_address
        self.client_id = str(uuid.uuid4())
        
        with data_lock:
            players[self.client_id] = (client_socket, (400, 300), "", "falcon")  # Position initiale avec pseudo et type
            client_sockets[client_socket] = self.client_id

    def send_data(self, data):
        try:
            serialized_data = pickle.dumps(data)
            self.client_socket.send(serialized_data)
            return True
        except socket.error as e:
            logger.error(f"Error sending data to client {self.client_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending data to client {self.client_id}: {e}")
            logger.error(traceback.format_exc())
            return False

    def run(self):
        try:
            # Envoyer l'ID du client
            if not self.send_data(('init', self.client_id)):
                logger.error(f"Failed to send init message to client {self.client_id}")
                return
            
            # Pause courte pour permettre au client de traiter son ID
            time.sleep(0.1)
            
            # Envoyer l'état actuel de tous les joueurs au nouveau client
            with data_lock:
                player_list = list(players.items())
            
            for player_id, (_, pos, pseudo, soldier_type) in player_list:
                if player_id != self.client_id:  # Ne pas envoyer sa propre position
                    try:
                        # Format standard: (client_id, position, pseudo, soldier_type)
                        player_data = (player_id, pos, pseudo, soldier_type)
                        if not self.send_data(player_data):
                            logger.warning(f"Failed to send player data for {player_id} to new client {self.client_id}")
                    except Exception as e:
                        logger.error(f"Error sending player data: {e}")
                        logger.error(traceback.format_exc())
                        return
            
            # Pause courte pour permettre au client de traiter les données des joueurs
            time.sleep(0.1)
            
            # Envoyer tous les tirs actifs au nouveau client
            with data_lock:
                shot_list = list(shots.items())
            
            for shot_id, shot_data in shot_list:
                try:
                    # Format standard: ('shot', shot_id, shot_data)
                    shot_message = ('shot', shot_id, shot_data)
                    if not self.send_data(shot_message):
                        logger.warning(f"Failed to send shot {shot_id} to new client {self.client_id}")
                except Exception as e:
                    logger.error(f"Error sending shot data: {e}")
                    logger.error(traceback.format_exc())
                    return
            
            # Boucle principale pour recevoir les données du client
            while True:
                try:
                    data = self.client_socket.recv(BUFFER_SIZE)
                    if not data:
                        logger.info(f"No data received from client {self.client_id}, disconnecting")
                        break
                    
                    # Traiter les données reçues
                    parsed_data = pickle.loads(data)
                    
                    # Handle shot data
                    if isinstance(parsed_data, dict) and 'shot' in parsed_data:
                        shot_id = str(uuid.uuid4())
                        shot_data = parsed_data['shot']
                        shot_data['player_id'] = self.client_id
                        
                        with data_lock:
                            shots[shot_id] = shot_data
                        
                        # Broadcast shot to all clients immediately
                        shot_message = ('shot', shot_id, shot_data)
                        self.broadcast_message(shot_message)
                        logger.info(f"New shot {shot_id} from client {self.client_id}")
                    
                    # Handle position data
                    elif isinstance(parsed_data, dict) and 'position' in parsed_data:
                        position = parsed_data['position']
                        pseudo = parsed_data.get('pseudo', "")
                        soldier_type = parsed_data.get('soldier_type', "falcon")
                        
                        with data_lock:
                            players[self.client_id] = (self.client_socket, position, pseudo, soldier_type)
                        
                        # Broadcast position update to other clients only
                        pos_message = (self.client_id, position, pseudo, soldier_type)
                        self.broadcast_message(pos_message, exclude_self=True)
                    
                    # Other message types
                    else:
                        logger.warning(f"Unrecognized data format from client {self.client_id}: {type(parsed_data)}")
                
                except pickle.UnpicklingError as e:
                    logger.error(f"Error unpickling data from client {self.client_id}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing data from client {self.client_id}: {e}")
                    logger.error(traceback.format_exc())
                    continue
        
        except socket.error as e:
            logger.error(f"Socket error with client {self.client_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error with client {self.client_id}: {e}")
            logger.error(traceback.format_exc())
        finally:
            # Cleanup
            self.client_socket.close()
            self.cleanup_client()
    
    def broadcast_message(self, message, exclude_self=False):
        """Envoie un message à tous les clients connectés, avec option d'exclusion de soi-même"""
        with data_lock:
            socket_list = list(client_sockets.keys())
        
        for client_socket in socket_list:
            if exclude_self and client_socket == self.client_socket:
                continue
            
            try:
                client_socket.send(pickle.dumps(message))
            except socket.error as e:
                logger.error(f"Error broadcasting to a client: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error broadcasting: {e}")
                logger.error(traceback.format_exc())
                continue
    
    def cleanup_client(self):
        """Nettoie les ressources associées à ce client et notifie les autres clients"""
        with data_lock:
            if self.client_id in players:
                del players[self.client_id]
            
            if self.client_socket in client_sockets:
                del client_sockets[self.client_socket]
            
            # Supprimer les tirs du joueur
            shot_ids_to_remove = []
            for shot_id, shot_data in shots.items():
                if shot_data.get('player_id') == self.client_id:
                    shot_ids_to_remove.append(shot_id)
            
            for shot_id in shot_ids_to_remove:
                del shots[shot_id]
        
        # Notifier tous les clients de la déconnexion
        disconnect_message = ('disconnect', self.client_id)
        self.broadcast_message(disconnect_message)
        
        logger.info(f"Client disconnected and cleaned up: {self.client_address}")

# Fonction pour nettoyer les tirs périodiquement
def cleanup_shots():
    while True:
        try:
            time.sleep(1.0)  # Attendre 1 seconde entre les nettoyages
            
            shots_to_remove = []
            map_width = 2000  # Taille approximative de la carte
            map_height = 2000
            
            with data_lock:
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
            logger.error(traceback.format_exc())

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)
        logger.info(f"Serveur démarré sur {HOST}:{PORT}")
        
        # Démarrer le thread de nettoyage des tirs
        cleanup_thread = threading.Thread(target=cleanup_shots, daemon=True)
        cleanup_thread.start()
        
        while True:
            try:
                client_socket, client_address = server_socket.accept()
                logger.info(f"Nouvelle connexion reçue de {client_address}")
                
                client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                
                new_thread = ClientThread(client_socket, client_address)
                new_thread.daemon = True
                new_thread.start()
            except socket.error as e:
                logger.error(f"Error accepting connection: {e}")
            except Exception as e:
                logger.error(f"Unexpected error in main server loop: {e}")
                logger.error(traceback.format_exc())
    
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        logger.error(traceback.format_exc())
    finally:
        server_socket.close()
        logger.info("Server shut down")

if __name__ == "__main__":
    start_server()
