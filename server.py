import socket
import threading
import logging
import pickle


# Configuration du serveur
HOST = '127.0.0.1'  # Adresse localhost
PORT = 12345        # Port à utiliser

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Liste des joueurs avec leurs positions
players = {}  # {client_socket: (x, y)}


class ClientThread(threading.Thread):
    def __init__(self, client_socket, client_address):
        threading.Thread.__init__(self)
        self.client_socket = client_socket
        self.client_address = client_address

    def run(self):
        try:
            while True:
                data = self.client_socket.recv(1024)
                if not data:
                    break

                # Mettre à jour la position du joueur
                try:
                    position = pickle.loads(data)
                    players[self.client_socket] = position
                except Exception as e:
                    logger.error(f"Error processing player position: {e}")
                    continue

                # Envoyer les positions de tous les joueurs à tous les clients
                for player_socket in players:
                    if player_socket != self.client_socket:
                        try:
                            # Envoyer la position de ce joueur au client
                            player_socket.send(pickle.dumps((self.client_socket, position)))
                        except socket.error as e:
                            logger.error(f"Error sending data to client: {e}")
                            break

        except socket.error as e:
            logger.error(f"Error in client thread: {e}")
        finally:
            self.client_socket.close()
            if self.client_socket in players:
                del players[self.client_socket]
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
