import pygame
import socket
import threading
import pickle
import uuid
import logging
import sys
import os
import time

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from menu import Menu
from game.map_manager import MapManager
from game.soldier import Soldier, SoldierState, SoldierDirection

# Configuration du jeu
DEFAULT_PORT = 12345
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
player_speed = 5
HOST = '0.0.0.0'  # Adresse de connection
PORT = 12345  # Port à utiliser
BUFFER_SIZE = 8192  # Taille du tampon pour la réception des données

WHITE = (255, 255, 255)
RED = (255, 0, 0)

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
other_players = {}  # {client_id: (x, y, pseudo, soldier_type, health, bullets)}
other_soldiers = {}  # Cache for other players' Soldier objects
player = None

# Camera
camera_x = 0
camera_y = 0
camera_speed = 0.1

# Map
map_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'map', 'map.tmx')
map_manager = MapManager(map_path)
map_width, map_height = map_manager.get_map_size()

# === SERVER CODE ===
players = {}  # {client_id: (socket, position, pseudo, soldier_type, health, bullets)}
client_sockets = {}


class ClientThread(threading.Thread):
    def __init__(self, server_address, server_port):
        threading.Thread.__init__(self)
        self.server_address = server_address
        self.server_port = server_port
        self.socket = None
        self.client_id = None
        self.players = {}  # {client_id: (position, pseudo, soldier_type, health, bullets, damage_resistance)}
        self.damage_messages = []  # Liste des messages de dégâts à afficher
        self.running = True

    def receive_data(self):
        while self.running:
            try:
                data = self.socket.recv(BUFFER_SIZE)
                if not data:
                    break

                message = pickle.loads(data)
                
                if isinstance(message, tuple):
                    if message[0] == 'init':
                        self.client_id = message[1]
                        logger.info(f"Connected to server with ID: {self.client_id}")
                    elif message[0] == 'disconnect':
                        player_id = message[1]
                        if player_id in self.players:
                            del self.players[player_id]
                    else:
                        player_id, position, pseudo, soldier_type, health, bullets, damage_resistance = message
                        self.players[player_id] = (position, pseudo, soldier_type, health, bullets, damage_resistance)
                elif isinstance(message, dict) and message.get('type') == 'damage':
                    # Gérer la notification de dégâts
                    damage_amount = message.get('amount', 0)
                    attacker_id = message.get('from')
                    if attacker_id in self.players:
                        attacker_pseudo = self.players[attacker_id][1]
                        self.damage_messages.append({
                            'text': f"-{damage_amount:.1f}",
                            'position': self.players[self.client_id][0],  # Position du joueur touché
                            'time': time.time(),
                            'attacker': attacker_pseudo
                        })
                        
                        # Mettre à jour la santé du joueur local
                        if self.client_id in self.players:
                            pos, pseudo, st, health, bullets, dr = self.players[self.client_id]
                            self.players[self.client_id] = (pos, pseudo, st, max(0, health - damage_amount), bullets, dr)

            except socket.error as e:
                logger.error(f"Socket error in receive_data: {e}")
                break
            except Exception as e:
                logger.error(f"Error in receive_data: {e}")
                continue

    def run(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_address, self.server_port))
            self.receive_data()
        except Exception as e:
            logger.error(f"Error in client thread: {e}")
        finally:
            if self.socket:
                self.socket.close()


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    logger.info(f"Serveur démarré sur {HOST}:{PORT}")

    while True:
        try:
            client_socket, client_address = server_socket.accept()
            logger.info(f"Nouvelle connexion de {client_address}")
            
            # Créer un thread pour gérer ce client
            client_thread = threading.Thread(
                target=handle_client_connection,
                args=(client_socket, client_address),
                daemon=True
            )
            client_thread.start()
        except socket.error as e:
            logger.error(f"Erreur lors de l'acceptation de la connexion: {e}")


def handle_client_connection(client_socket, client_address):
    """Gère la connexion d'un client au serveur hébergé localement"""
    try:
        # Générer un ID unique pour ce client
        client_id = str(uuid.uuid4())
        
        # Envoyer l'ID au client
        client_socket.send(pickle.dumps(('init', client_id)))
        
        # Ajouter le client à la liste des joueurs
        players[client_id] = (client_socket, (400, 300), "", "falcon", 100, [], 0.8)
        client_sockets[client_socket] = client_id
        
        # Envoyer l'état actuel de tous les joueurs au nouveau client
        for player_id, (_, player_pos, pseudo, soldier_type, health, bullets, damage_resistance) in players.items():
            if player_id != client_id:  # Ne pas envoyer sa propre position
                client_socket.send(pickle.dumps((player_id, player_pos, pseudo, soldier_type, health, bullets, damage_resistance)))
        
        # Boucle principale pour ce client
        while True:
            data = client_socket.recv(BUFFER_SIZE)
            if not data:
                break
                
            try:
                player_data = pickle.loads(data)
                if isinstance(player_data, dict):
                    position = player_data.get('position', (400, 300))
                    pseudo = player_data.get('pseudo', "")
                    soldier_type = player_data.get('soldier_type', "falcon")
                    health = player_data.get('health', 100)
                    bullets = player_data.get('bullets', [])
                    is_dead = player_data.get('is_dead', False)
                    damage_resistance = player_data.get('damage_resistance', 0.8)
                    
                    # Traiter les balles si le joueur est vivant
                    if not is_dead and bullets:
                        bullets_to_remove = []
                        for bullet_idx, bullet in enumerate(bullets):
                            try:
                                if len(bullet) < 3:
                                    continue  # Ignorer les balles invalides
                                    
                                # Vérifier les collisions avec les autres joueurs
                                bullet_x, bullet_y, direction = bullet[:3]
                                for target_id, (_, target_pos, _, target_type, target_health, _, target_resistance) in players.items():
                                    if target_id != client_id:  # Ne pas se blesser soi-même
                                        target_x, target_y = target_pos
                                        # Collision basée sur la distance
                                        distance = ((bullet_x - target_x) ** 2 + (bullet_y - target_y) ** 2) ** 0.5
                                        if distance < 30:  # Rayon de collision
                                            # Ne blesser que les joueurs avec de la santé > 0
                                            if target_health > 0:
                                                # Calculer les dégâts avec les multiplicateurs de type et la résistance
                                                base_damage = 10
                                                type_multiplier = calculate_damage(soldier_type, target_type)
                                                actual_damage = base_damage * type_multiplier * target_resistance
                                                
                                                # Mettre à jour la santé de la cible
                                                new_health = max(0, target_health - actual_damage)
                                                socket_obj, pos, p, st, _, b, dr = players[target_id]
                                                players[target_id] = (socket_obj, pos, p, st, new_health, b, dr)
                                                
                                                # Envoyer une notification de dégâts à la cible
                                                try:
                                                    damage_msg = {
                                                        'type': 'damage',
                                                        'amount': actual_damage,
                                                        'from': client_id
                                                    }
                                                    socket_obj.send(pickle.dumps(damage_msg))
                                                except socket.error as e:
                                                    logger.error(f"Erreur lors de l'envoi de la notification de dégâts: {e}")
                                                
                                                # Ajouter un compteur de kills/score si le joueur a été tué par cette balle
                                                if target_health > 0 and new_health <= 0:
                                                    logger.info(f"Le joueur {pseudo} a tué {p}")
                                                
                                                bullets_to_remove.append(bullet_idx)
                                                break  # Sortir de la boucle des cibles après avoir touché quelqu'un
                            except Exception as e:
                                logger.error(f"Erreur lors du traitement de la balle: {e}")
                                continue
                        
                        # Supprimer les balles qui ont touché des cibles (dans l'ordre inverse pour éviter les problèmes d'index)
                        for idx in sorted(bullets_to_remove, reverse=True):
                            if idx < len(bullets):
                                bullets.pop(idx)
                    
                    # Stocker les données mises à jour du joueur
                    players[client_id] = (client_socket, position, pseudo, soldier_type, health, bullets, damage_resistance)
            except Exception as e:
                logger.error(f"Erreur lors du traitement des données du joueur: {e}")
                continue
            
            # Envoyer les données de tous les joueurs à tous les clients
            for pid, (sock, _, _, _, _, _, _) in players.items():
                try:
                    # Envoyer toutes les données à ce client
                    for player_id, (_, player_pos, pseudo, soldier_type, health, bullets, damage_resistance) in players.items():
                        try:
                            # Limiter le nombre de balles si nécessaire pour éviter les problèmes de tampon
                            if len(bullets) > 10:
                                bullets = bullets[:10]
                                
                            msg = (player_id, player_pos, pseudo, soldier_type, health, bullets, damage_resistance)
                            sock.send(pickle.dumps(msg, protocol=4))  # Utiliser le protocole 4 pour une meilleure compatibilité
                        except socket.error as e:
                            logger.error(f"Erreur lors de l'envoi des données au client {player_id}: {e}")
                            break
                        except Exception as e:
                            logger.error(f"Erreur lors de la préparation des données pour le client {player_id}: {e}")
                            break
                except socket.error as e:
                    logger.error(f"Erreur lors de l'envoi des données au client: {e}")
                    break
                    
    except socket.error as e:
        logger.error(f"Erreur dans le thread client: {e}")
    finally:
        client_socket.close()
        if client_id in players:
            # Notifier tous les clients de la déconnexion
            disconnect_message = ('disconnect', client_id)
            for _, (sock, _, _, _, _, _, _) in players.items():
                if sock != client_socket:  # Ne pas envoyer au socket déconnecté
                    try:
                        sock.send(pickle.dumps(disconnect_message))
                    except socket.error:
                        pass
            del players[client_id]
        if client_socket in client_sockets:
            del client_sockets[client_socket]
        logger.info(f"Client déconnecté: {client_address}")


def calculate_damage(attacker_type, target_type):
    # Différents types de soldats ont différents multiplicateurs de dégâts
    damage_multipliers = {
        "falcon": {
            "falcon": 1.0,
            "rogue": 1.2
        },
        "rogue": {
            "falcon": 0.8,
            "rogue": 1.0
        }
    }
    return damage_multipliers.get(attacker_type.lower(), {}).get(target_type.lower(), 1.0)


# === CLIENT CODE ===
def receive_data(sock):
    global other_players, client_id
    buffer = b""
    
    # S'assurer que other_players est initialisé
    if 'other_players' not in globals():
        other_players = {}
    
    while True:
        try:
            data = sock.recv(BUFFER_SIZE)
            if not data:
                break
            buffer += data
            while len(buffer):
                try:
                    msg = pickle.loads(buffer)
                    buffer = b""
                    if isinstance(msg, tuple):
                        if msg[0] == 'init':
                            client_id = msg[1]
                            logger.info(f"ID client reçu: {client_id}")
                        elif msg[0] == 'disconnect':
                            if msg[1] in other_players:
                                del other_players[msg[1]]
                                logger.info(f"Joueur déconnecté: {msg[1]}")
                        else:
                            # Format: (player_id, position, pseudo, soldier_type, health, bullets, damage_resistance)
                            pid, pos, pseudo, soldier_type, health, bullets, damage_resistance = msg
                            if pid != client_id:
                                other_players[pid] = (pos, pseudo, soldier_type, health, bullets, time.time())
                    elif isinstance(msg, dict):
                        if msg.get('type') == 'damage':
                            # Gérer la notification de dégâts
                            damage_amount = msg.get('amount', 0)
                            attacker_id = msg.get('from')
                            
                            # Mettre à jour la santé du joueur local
                            if player:
                                player.take_damage(damage_amount)
                                logger.info(f"Dégâts reçus: {damage_amount}")
                except pickle.UnpicklingError:
                    break
        except socket.error as e:
            logger.error(f"Erreur de réception: {e}")
            break


def main():
    global SCREEN_WIDTH, SCREEN_HEIGHT, camera_x, camera_y, player, other_soldiers, other_players
    player_x, player_y = 400, 300

    # Initialiser other_players s'il n'est pas déjà défini
    if 'other_players' not in globals():
        other_players = {}

    menu = Menu(screen)
    action, ip = menu.show()
    if action is None:
        pygame.quit()
        return

    pseudo, soldier_type = menu.show_profile_selection()
    if pseudo is None:
        pygame.quit()
        return

    # Initialiser la connexion réseau
    sock = None
    client_thread = None
    
    if action == 'host':
        # Démarrer le serveur dans un thread séparé
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()
        logger.info("Serveur démarré en mode hébergement")
        
        # Attendre un peu pour que le serveur démarre
        time.sleep(1)
        
        # Se connecter au serveur local
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(('127.0.0.1', DEFAULT_PORT))
            logger.info("Connecté au serveur local")
        except socket.error as e:
            logger.error(f"Erreur de connexion au serveur local: {e}")
            pygame.quit()
            return
    else:
        # Se connecter au serveur distant
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip, DEFAULT_PORT))
            logger.info(f"Connecté au serveur distant: {ip}")
        except socket.error as e:
            logger.error(f"Erreur de connexion au serveur distant: {e}")
            pygame.quit()
            return

    # Démarrer le thread de réception des données
    client_thread = ClientThread(ip if action == 'join' else '127.0.0.1', DEFAULT_PORT)
    client_thread.start()
    
    # Démarrer le thread de réception des données pour le client local
    # threading.Thread(target=receive_data, args=(sock,), daemon=True).start()
    clock = pygame.time.Clock()
    running = True

    # Create player soldier
    player = Soldier(player_x, player_y, soldier_type, pseudo)

    # Game state
    game_over = False
    respawn_position = (400, 300)  # Default respawn position
    respawn_cooldown = 0
    respawn_delay = 1000  # 1 second delay before respawn

    # Boucle principale du jeu
    last_cleanup = time.time()
    
    while running:
        current_time = time.time()
        
        # Nettoyer les messages de dégâts anciens
        if current_time - last_cleanup > 0.1:  # Nettoyage toutes les 100ms
            other_players = {pid: data for pid, data in other_players.items() if current_time - data[5] < 2.0}
            last_cleanup = current_time

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        keys = pygame.key.get_pressed()
        
        # Handle respawn on R key when dead
        if player.health <= 0:
            game_over = True
            
            # Check for R key press and respawn cooldown
            if keys[pygame.K_r] and current_time - respawn_cooldown > respawn_delay:
                game_over = False
                player.revive(respawn_position[0], respawn_position[1])
                respawn_cooldown = current_time
                
        if not game_over:
            player.update(keys, [other_soldiers.get(pid) for pid in other_soldiers])

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

            # Use the serialize_bullet method to get safe bullet data for network
            try:
                msg = {
                    'position': (player.x, player.y),
                    'pseudo': pseudo,
                    'soldier_type': soldier_type,
                    'health': player.health,
                    'bullets': player.serialize_bullet(),
                    'is_dead': player.is_dead,
                    'damage_resistance': player.damage_resistance
                }
                
                # Envoyer les données via le client_thread si disponible, sinon via le socket direct
                if client_thread and client_thread.socket:
                    client_thread.socket.send(pickle.dumps(msg))
                elif sock:
                    sock.send(pickle.dumps(msg))
                else:
                    logger.error("Aucune connexion disponible pour envoyer les données")
            except socket.error as e:
                logger.error(f"Erreur réseau: {e}")
                break
            except Exception as e:
                logger.error(f"Erreur lors de la préparation des données réseau: {e}")

        screen.fill((0, 0, 0))
        
        # Draw map
        map_manager.draw(screen, camera_x, camera_y)
        
        # Draw other players
        for pid, data in other_players.items():
            # Vérifier si les données sont dans le bon format
            if len(data) >= 5:
                pos, name, soldier_type, health, bullets = data[:5]
                # Le timestamp est à l'index 5, mais nous n'en avons pas besoin ici
                
                if pid not in other_soldiers:
                    # Create new soldier object only if it doesn't exist
                    other_soldiers[pid] = Soldier(pos[0], pos[1], soldier_type, name)
                else:
                    # Update existing soldier's position and health
                    other_soldiers[pid].x = pos[0]
                    other_soldiers[pid].y = pos[1]
                    other_soldiers[pid].health = health
                    
                    # Apply death state if health is 0
                    if health <= 0 and not other_soldiers[pid].is_dead:
                        other_soldiers[pid].is_dead = True
                        other_soldiers[pid].state = SoldierState.DEAD
                        other_soldiers[pid].animation_frame = 0
                    
                    # Clear and update bullets
                    other_soldiers[pid].bullets.clear()
                    for bullet_data in bullets:
                        try:
                            x, y, direction = bullet_data
                            # Convert string direction back to enum if needed
                            if isinstance(direction, str):
                                for dir_enum in SoldierDirection:
                                    if dir_enum.value == direction:
                                        direction = dir_enum
                                        break
                            from game.soldier import Bullet
                            bullet = Bullet(x, y, direction)
                            other_soldiers[pid].bullets.append(bullet)
                        except Exception as e:
                            logger.error(f"Erreur lors de la création d'une balle à partir des données réseau: {e}")
                            continue
                    
                # Draw the soldier and their bullets
                other_soldiers[pid].draw(screen, camera_x, camera_y)

        # Clean up disconnected players
        disconnected_players = set(other_soldiers.keys()) - set(other_players.keys())
        for pid in disconnected_players:
            del other_soldiers[pid]

        # Draw current player
        if not game_over:
            player.draw(screen, camera_x, camera_y)
        else:
            # Show game over and respawn message
            game_over_font = pygame.font.Font(None, 72)
            game_over_text = game_over_font.render("GAME OVER", True, RED)
            respawn_font = pygame.font.Font(None, 36)
            respawn_text = respawn_font.render("Press R to respawn", True, WHITE)
            
            screen.blit(game_over_text, 
                        (SCREEN_WIDTH // 2 - game_over_text.get_width() // 2, 
                         SCREEN_HEIGHT // 2 - 50))
            screen.blit(respawn_text, 
                        (SCREEN_WIDTH // 2 - respawn_text.get_width() // 2, 
                         SCREEN_HEIGHT // 2 + 20))

        # Dessiner les messages de dégâts
        if client_thread and hasattr(client_thread, 'damage_messages'):
            for msg in client_thread.damage_messages:
                # Calculer la position du message (légèrement au-dessus du joueur)
                x, y = msg['position']
                y -= 20  # Décalage vers le haut
                
                # Calculer l'alpha (transparence) en fonction du temps
                age = current_time - msg['time']
                alpha = max(0, min(255, int(255 * (1 - age / 2.0))))
                
                # Créer le texte avec l'attaquant
                text = f"{msg['text']} ({msg['attacker']})"
                font = pygame.font.Font(None, 24)
                text_surface = font.render(text, True, RED)
                text_surface.set_alpha(alpha)
                
                # Dessiner le texte
                screen.blit(text_surface, (x - text_surface.get_width() // 2, y))

        pygame.display.flip()
        clock.tick(60)

    if sock:
        sock.close()
    pygame.quit()


if __name__ == "__main__":
    main()