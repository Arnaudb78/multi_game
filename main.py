import subprocess
import time
import sys


def start_server():
    """ Démarre le serveur dans un sous-processus """
    print("Démarrage du serveur...")
    server = subprocess.Popen([sys.executable, 'server.py'])
    time.sleep(1)  # Attendre un peu que le serveur soit bien lancé
    return server


def start_client():
    """ Démarre un client dans un sous-processus """
    print("Démarrage d'un client...")
    subprocess.Popen([sys.executable, 'client.py'])


if __name__ == "__main__":
    # Démarre le serveur
    server = start_server()

    # Démarre quelques clients (ici on démarre 2 clients pour l'exemple)
    start_client()
    start_client()

    # Laisser le serveur tourner
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Arrêt du serveur et des clients.")
        server.terminate()
