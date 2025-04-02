import socket
import threading
import logging
import pickle
import uuid


# Configuration du serveur
HOST = '0.0.0.0'  # Adresse de connection
PORT = 12345        # Port à utiliser

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Dictionnaire des joueurs avec leurs positions
players = {}  # {client_id: (socket, position)}
client_sockets = {}  # {socket: client_id}


class ClientThread(threading.Thread):
    def __init__(self, client_socket, client_address):
        threading.Thread.__init__(self)
        self.client_socket = client_socket
        self.client_address = client_address
        self.client_id = str(uuid.uuid4())
        players[self.client_id] = (client_socket, (400, 300))  # Position initiale
        client_sockets[client_socket] = self.client_id

    def run(self):
        try:
            # Envoyer l'ID du client
            self.client_socket.send(pickle.dumps(('init', self.client_id)))
            
            while True:
                data = self.client_socket.recv(1024)
                if not data:
                    break

                # Mettre à jour la position du joueur
                try:
                    position = pickle.loads(data)
                    players[self.client_id] = (self.client_socket, position)
                except Exception as e:
                    logger.error(f"Error processing player position: {e}")
                    continue

                # Envoyer les positions de tous les joueurs à tous les clients
                for client_socket in client_sockets.keys():
                    try:
                        # Envoyer toutes les positions à ce client
                        for player_id, (_, player_pos) in players.items():
                            data = pickle.dumps((player_id, player_pos))
                            client_socket.send(data)
                    except socket.error as e:
                        logger.error(f"Error sending data to client: {e}")
                        break

        except socket.error as e:
            logger.error(f"Error in client thread: {e}")
        finally:
            self.client_socket.close()
            if self.client_id in players:
                # Notifier tous les clients de la déconnexion
                disconnect_message = pickle.dumps(('disconnect', self.client_id))
                for client_socket in client_sockets.keys():
                    try:
                        client_socket.send(disconnect_message)
                    except:
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
