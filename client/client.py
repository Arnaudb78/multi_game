import pygame
import socket
import threading
import pickle
import uuid
import logging
import sys
import os
import time
import traceback
import random

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importer le module serveur pour démarrer le serveur localement si nécessaire
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
try:
    from server import start_server as server_start
except ImportError:
    # Définir une fonction de secours si l'import échoue
    def server_start():
        logger.error("Module serveur introuvable. Le serveur ne peut pas être démarré.")

from menu import Menu
from game.map_manager import MapManager
from game.soldier import Soldier, SoldierDirection, SoldierState

# Configuration du jeu
DEFAULT_PORT = 12345
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
player_speed = 5
HOST = '0.0.0.0'  # Adresse de connection
PORT = 12345  # Port à utiliser

WHITE = (255, 255, 255)
RED = (255, 0, 0)
BLACK = (0, 0, 0)
DARK_RED = (139, 0, 0)

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
other_players = {}  # {client_id: (x, y, pseudo, soldier_type)}
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

# Variables globales pour les tirs
shots = {}  # {shot_id: {'position': (x, y), 'direction': (dx, dy), 'speed': s, 'player_id': pid}}
bullet_images = {}  # Cache pour les images de balles
explosion_images = []  # Cache pour les images d'explosion
active_explosions = []  # Liste des explosions actives (position, frame_actuel, taille)

# Verrou pour les données partagées
data_lock = threading.Lock()

def log_exception(e, message="Exception"):
    """Log une exception avec sa trace complète"""
    logger.error(f"{message}: {e}")
    logger.error(traceback.format_exc())

def load_explosion_images():
    """Charge les images d'explosion depuis le dossier assets"""
    global explosion_images
    
    # Get the path to explosion images
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
    explosion_dir = os.path.join(assets_dir, 'explosion')
    
    # Create directory if it doesn't exist yet
    if not os.path.exists(explosion_dir):
        os.makedirs(explosion_dir)
        logger.info(f"Created explosion directory at {explosion_dir}")
        return
    
    # Look for explosion images
    try:
        images = []
        # Try to load existing explosion images
        for i in range(1, 20):  # Assuming up to 19 frames
            file_path = os.path.join(explosion_dir, f"explosion{i}.png")
            if os.path.exists(file_path):
                img = pygame.image.load(file_path).convert_alpha()
                images.append(img)
                logger.info(f"Loaded explosion image: {file_path}")
            else:
                # Try alternate naming patterns
                file_path = os.path.join(explosion_dir, f"exp{i}.png")
                if os.path.exists(file_path):
                    img = pygame.image.load(file_path).convert_alpha()
                    images.append(img)
                    logger.info(f"Loaded explosion image: {file_path}")
        
        # If no explosion images found, use fallback circle images
        if not images:
            logger.warning("No explosion images found. Using fallback explosions.")
            # Create simple explosion frames (expanding yellow-orange-red circles)
            sizes = [10, 20, 30, 35, 40, 35, 30, 20, 10]
            colors = [
                (255, 255, 0),    # Yellow
                (255, 200, 0),    # Orange-yellow
                (255, 150, 0),    # Orange
                (255, 100, 0),    # Dark orange
                (255, 50, 0),     # Red-orange
                (255, 0, 0),      # Red
                (200, 0, 0),      # Dark red
                (150, 0, 0),      # Even darker red
                (100, 0, 0)       # Very dark red
            ]
            
            for i, (size, color) in enumerate(zip(sizes, colors)):
                surf = pygame.Surface((size*2, size*2), pygame.SRCALPHA)
                pygame.draw.circle(surf, color, (size, size), size)
                # Add some transparent yellow for glow effect
                glow_size = size + 5
                glow_surf = pygame.Surface((glow_size*2, glow_size*2), pygame.SRCALPHA)
                glow_color = (255, 255, 0, 100)  # Semi-transparent yellow
                pygame.draw.circle(glow_surf, glow_color, (glow_size, glow_size), glow_size)
                # Combine surfaces
                final_surf = pygame.Surface((glow_size*2, glow_size*2), pygame.SRCALPHA)
                final_surf.blit(glow_surf, (0, 0))
                final_surf.blit(surf, (5, 5))
                images.append(final_surf)
        
        explosion_images = images
        logger.info(f"Loaded {len(explosion_images)} explosion frames")
    except Exception as e:
        log_exception(e, "Error loading explosion images")

def receive_data(sock):
    global other_players, client_id, shots
    
    while True:
        try:
            # Recevoir les données du serveur
            data = sock.recv(4096)
            if not data:
                logger.info("Connexion fermée par le serveur")
                break
            
            # Désérialiser les données
            try:
                message = pickle.loads(data)
                
                # Message d'initialisation
                if isinstance(message, tuple) and len(message) >= 2 and message[0] == 'init':
                    with data_lock:
                        client_id = message[1]
                    logger.info(f"ID client reçu: {client_id}")
                
                # Message de déconnexion
                elif isinstance(message, tuple) and len(message) >= 2 and message[0] == 'disconnect':
                    player_id = message[1]
                    with data_lock:
                        if player_id in other_players:
                            logger.info(f"Joueur déconnecté: {player_id}")
                            del other_players[player_id]
                        
                        # Supprimer les tirs du joueur déconnecté
                        shots_to_remove = [shot_id for shot_id, shot_data in shots.items() 
                                          if shot_data.get('player_id') == player_id]
                        for shot_id in shots_to_remove:
                            del shots[shot_id]
                
                # Message de tir
                elif isinstance(message, tuple) and len(message) >= 3 and message[0] == 'shot':
                    shot_id = message[1]
                    shot_data = message[2]
                    
                    # Ne pas traiter nos propres tirs à nouveau (ils sont déjà affichés)
                    if shot_data.get('player_id') != client_id or shot_id not in shots:
                        with data_lock:
                            shots[shot_id] = shot_data
                        logger.info(f"Tir reçu: {shot_id} de {shot_data.get('player_id')}")
                
                # Message de mise à jour de santé
                elif isinstance(message, tuple) and len(message) >= 3 and message[0] == 'health_update':
                    player_id = message[1]
                    health = message[2]
                    
                    # Mettre à jour la santé du joueur local si c'est nous
                    if player_id == client_id and player:
                        player.health = health
                        if health <= 0:
                            player.state = SoldierState.DEAD
                        logger.info(f"Santé locale mise à jour: {health}")
                    # Sinon, mettre à jour la santé des autres joueurs
                    elif player_id in other_soldiers:
                        other_soldiers[player_id].health = health
                        if health <= 0:
                            other_soldiers[player_id].state = SoldierState.DEAD
                        logger.info(f"Santé du joueur {player_id} mise à jour: {health}")
                
                # Message de notification de dégâts
                elif isinstance(message, tuple) and len(message) >= 2 and message[0] == 'hit':
                    hit_data = message[1]
                    target_id = hit_data.get('target_id')
                    shooter_id = hit_data.get('shooter_id')
                    damage = hit_data.get('damage', 0)
                    new_health = hit_data.get('new_health', 0)
                    
                    # Si nous sommes la cible, mettre à jour notre santé
                    if target_id == client_id and player:
                        player.health = new_health
                        if new_health <= 0:
                            player.state = SoldierState.DEAD
                        else:
                            # Make sure we continue moving normally if still alive
                            player.state = SoldierState.IDLE
                            
                        logger.info(f"Vous avez été touché par {shooter_id} pour {damage} dégâts. Santé: {new_health}")
                        
                        # Force a position update to ensure sync
                        if sock_global:
                            send_player_position(sock_global, player)
                    
                    # Si un autre joueur est touché, mettre à jour sa santé
                    elif target_id in other_soldiers:
                        other_soldiers[target_id].health = new_health
                        if new_health <= 0:
                            other_soldiers[target_id].state = SoldierState.DEAD
                        else:
                            other_soldiers[target_id].state = SoldierState.IDLE
                            
                        logger.info(f"Joueur {target_id} touché par {shooter_id} pour {damage} dégâts. Santé: {new_health}")
                
                # Message de position (format complet avec vehicle info)
                elif isinstance(message, tuple) and len(message) >= 2:
                    player_id = message[0]
                    
                    # Ne pas traiter notre propre position
                    if player_id != client_id:
                        with data_lock:
                            # New message format with complete data
                            if isinstance(message[1], dict):
                                player_data = message[1]
                                position = player_data.get('position')
                                pseudo = player_data.get('pseudo')
                                soldier_type = player_data.get('soldier_type')
                                health = player_data.get('health', 100)
                                
                                # Store player info
                                other_players[player_id] = (position, pseudo, soldier_type)
                            # Legacy format for backward compatibility
                            else:
                                position = message[1]
                                pseudo = message[2] if len(message) > 2 else ""
                                soldier_type = message[3] if len(message) > 3 else "falcon"
                                health = message[4] if len(message) > 4 else 100
                                
                                # Store player info
                                other_players[player_id] = (position, pseudo, soldier_type)
                            
                            # Update soldier health if it exists
                            if player_id in other_soldiers:
                                other_soldiers[player_id].health = health
                                if health <= 0:
                                    other_soldiers[player_id].state = SoldierState.DEAD
                
                # Format de message inconnu
                else:
                    logger.warning(f"Format de message non reconnu: {type(message)}")
            
            except pickle.UnpicklingError as e:
                logger.error(f"Erreur de désérialisation: {e}")
            except Exception as e:
                log_exception(e, "Erreur lors du traitement du message")
        
        except socket.error as e:
            logger.error(f"Erreur de réception: {e}")
            break
        except Exception as e:
            log_exception(e, "Erreur lors de la réception des données")
            break
    
    logger.info("Thread de réception terminé")

def load_bullet_images():
    """Charge les images de balles depuis le dossier assets"""
    global bullet_images
    
    # Chemins des dossiers de balles
    bullet_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'Objects', 'Bullet')
    
    # Charger les images de balles horizontales
    horizontal_images = []
    for i in range(1, 11):
        try:
            image_path = os.path.join(bullet_path, f"Horizontal ({i}).png")
            image = pygame.image.load(image_path).convert_alpha()
            image.set_colorkey((0, 0, 0))
            
            # Regular bullet size
            scale_factor = 0.3
            new_size = (int(image.get_width() * scale_factor), int(image.get_height() * scale_factor))
            scaled_image = pygame.transform.scale(image, new_size)
            horizontal_images.append(scaled_image)
        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'image de balle horizontale {i}: {e}")
    
    # Charger les images de balles verticales
    vertical_images = []
    for i in range(1, 11):
        try:
            image_path = os.path.join(bullet_path, f"Vertical ({i}).png")
            image = pygame.image.load(image_path).convert_alpha()
            image.set_colorkey((0, 0, 0))
            
            # Regular bullet size
            scale_factor = 0.3
            new_size = (int(image.get_width() * scale_factor), int(image.get_height() * scale_factor))
            scaled_image = pygame.transform.scale(image, new_size)
            vertical_images.append(scaled_image)
        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'image de balle verticale {i}: {e}")
    
    bullet_images = {
        'horizontal': horizontal_images,
        'vertical': vertical_images
    }

def send_player_position(sock, player):
    """Envoie la position du joueur au serveur"""
    try:
        position_data = {
            'position': (player.x, player.y),
            'pseudo': player.name,
            'soldier_type': player.soldier_type,
            'health': player.health
        }
        sock.send(pickle.dumps(position_data))
        return True
    except socket.error as e:
        logger.error(f"Erreur d'envoi de position: {e}")
        return False
    except Exception as e:
        log_exception(e, "Erreur lors de l'envoi de la position")
        return False

def send_health_update(sock, health):
    """Envoie une mise à jour de santé au serveur"""
    try:
        health_data = {
            'health_update': health
        }
        sock.send(pickle.dumps(health_data))
        return True
    except socket.error as e:
        logger.error(f"Erreur d'envoi de mise à jour de santé: {e}")
        return False
    except Exception as e:
        log_exception(e, "Erreur lors de l'envoi de la mise à jour de santé")
        return False

def send_hit_notification(sock, target_id, damage):
    """Envoie une notification de dégâts au serveur"""
    try:
        hit_data = {
            'hit': {
                'target_id': target_id,
                'damage': damage
            }
        }
        sock.send(pickle.dumps(hit_data))
        return True
    except socket.error as e:
        logger.error(f"Erreur d'envoi de notification de dégâts: {e}")
        return False
    except Exception as e:
        log_exception(e, "Erreur lors de l'envoi de la notification de dégâts")
        return False

def send_shot(sock, player, shot_direction):
    """Envoie un tir au serveur"""
    try:
        # Create shot data
        shot_data = {
            'shot': {
                'position': (player.x, player.y),
                'direction': shot_direction,
                'speed': 10,
                'player_id': client_id
            }
        }
        
        # Générer un ID local pour le tir
        shot_id = str(uuid.uuid4())
        
        # Envoyer le tir au serveur
        sock.send(pickle.dumps(shot_data))
        
        # Ajouter le tir localement pour un affichage immédiat
        with data_lock:
            shots[shot_id] = shot_data['shot']
        
        # Changer l'état du joueur
        player.state = SoldierState.SHOOT
        
        logger.info(f"Tir envoyé: {shot_id}")
        return True
    except socket.error as e:
        logger.error(f"Erreur d'envoi de tir: {e}")
        return False
    except Exception as e:
        log_exception(e, "Erreur lors de l'envoi du tir")
        return False

def update_shots():
    """Met à jour la position de tous les tirs et supprime ceux qui sont hors carte"""
    shots_to_remove = []
    
    with data_lock:
        for shot_id, shot in list(shots.items()):
            # Mettre à jour la position du tir
            new_position = (
                shot['position'][0] + shot['direction'][0] * shot['speed'],
                shot['position'][1] + shot['direction'][1] * shot['speed']
            )
            shot['position'] = new_position
            
            # Vérifier si le tir est sorti de la carte
            if (new_position[0] < -100 or new_position[0] > map_width + 100 or
                new_position[1] < -100 or new_position[1] > map_height + 100):
                shots_to_remove.append(shot_id)
        
        # Supprimer les tirs hors carte
        for shot_id in shots_to_remove:
            if shot_id in shots:
                del shots[shot_id]

def draw_shots(screen, camera_x, camera_y):
    """Dessine tous les tirs à l'écran"""
    with data_lock:
        shot_list = list(shots.items())
    
    for shot_id, shot in shot_list:
        # Déterminer si le tir est horizontal ou vertical
        is_horizontal = abs(shot['direction'][0]) > abs(shot['direction'][1])
        
        # Select appropriate image set based on direction
        if is_horizontal:
            image_key = 'horizontal'
        else:
            image_key = 'vertical'
        
        # Dessiner le tir avec l'image appropriée
        if bullet_images.get(image_key):
            # Animation de la balle
            animation_frame = (pygame.time.get_ticks() // 50) % len(bullet_images[image_key])
            bullet_image = bullet_images[image_key][animation_frame]
            
            # Ajuster la position pour centrer l'image
            draw_x = int(shot['position'][0] - camera_x - bullet_image.get_width() // 2)
            draw_y = int(shot['position'][1] - camera_y - bullet_image.get_height() // 2)
            
            # Inverser l'image si nécessaire
            if is_horizontal and shot['direction'][0] < 0:
                bullet_image = pygame.transform.flip(bullet_image, True, False)
            elif not is_horizontal and shot['direction'][1] < 0:
                bullet_image = pygame.transform.flip(bullet_image, False, True)
            
            screen.blit(bullet_image, (draw_x, draw_y))
        else:
            # Fallback si les images ne sont pas disponibles
            color = RED  # Red for normal bullets
            size = 5
            pygame.draw.circle(screen, color, 
                              (int(shot['position'][0] - camera_x), int(shot['position'][1] - camera_y)), 
                              size)

def check_shot_collisions():
    """Vérifie les collisions entre les tirs et les joueurs"""
    if player is None:
        return []
    
    # Si le joueur est mort, on ne vérifie pas les collisions
    if player.health <= 0:
        return []
    
    shots_to_remove = []
    
    with data_lock:
        # Vérifier les collisions avec le joueur local
        player_rect = pygame.Rect(player.x - 25, player.y - 25, 50, 50)
        
        for shot_id, shot in list(shots.items()):
            # Ne pas vérifier les collisions avec nos propres tirs
            if shot.get('player_id') == client_id:
                continue
            
            # Créer une hitbox pour le tir
            shot_rect = pygame.Rect(shot['position'][0] - 5, shot['position'][1] - 5, 10, 10)
            
            # Vérifier la collision avec le joueur local
            if player_rect.colliderect(shot_rect):
                logger.info(f"Touché par le tir de {shot.get('player_id')}!")
                shots_to_remove.append(shot_id)
                
                # Determine damage 
                damage = 10
                player.take_damage(damage)
                
                # Make sure player stays in a movable state
                if player.health > 0:
                    player.state = SoldierState.IDLE
                
                # Envoyer une mise à jour de santé au serveur si nous avons une connexion
                global sock_global
                if sock_global:
                    send_health_update(sock_global, player.health)
                    # Also send position update to ensure sync
                    send_player_position(sock_global, player)
        
        # Vérifier les collisions avec les autres joueurs si on est le tireur
        for shot_id, shot in list(shots.items()):
            if shot.get('player_id') == client_id:
                # Check collision with other players
                for other_id, other_soldier in other_soldiers.items():
                    if other_id == client_id or other_soldier.health <= 0:  # Ne pas se frapper soi-même ou un joueur mort
                        continue
                    
                    other_rect = pygame.Rect(other_soldier.x - 25, other_soldier.y - 25, 50, 50)
                    shot_rect = pygame.Rect(shot['position'][0] - 5, shot['position'][1] - 5, 10, 10)
                    
                    if shot_rect.colliderect(other_rect):
                        logger.info(f"Tir {shot_id} a touché le joueur {other_id}!")
                        shots_to_remove.append(shot_id)
                        
                        # Determine damage
                        damage = 10
                        
                        # Envoyer une notification de dégâts au serveur
                        if sock_global:
                            send_hit_notification(sock_global, other_id, damage)
                        break
    
    # Supprimer les tirs qui ont touché des joueurs
    with data_lock:
        for shot_id in shots_to_remove:
            if shot_id in shots:
                del shots[shot_id]
    
    return shots_to_remove

def draw_death_screen(screen):
    """Affiche l'écran de mort"""
    # Assombrir l'écran avec un semi-transparent overlay
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    overlay.set_alpha(180)  # Semi-transparent
    overlay.fill(BLACK)
    screen.blit(overlay, (0, 0))
    
    # Dessiner le message "Vous êtes mort"
    font_large = pygame.font.Font(None, 72)
    text = font_large.render("VOUS ÊTES MORT", True, DARK_RED)
    text_rect = text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 50))
    screen.blit(text, text_rect)
    
    # Dessiner les instructions pour rejouer
    font_small = pygame.font.Font(None, 32)
    instructions = font_small.render("Appuyez sur R pour réapparaître", True, WHITE)
    instructions_rect = instructions.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 50))
    screen.blit(instructions, instructions_rect)

def respawn_player(player):
    """Réinitialise le joueur après sa mort"""
    player.health = 100
    player.state = SoldierState.IDLE
    # Position aléatoire sur la carte
    player.x = random.randint(100, map_width - 100)
    player.y = random.randint(100, map_height - 100)
    return player

def main():
    global SCREEN_WIDTH, SCREEN_HEIGHT, camera_x, camera_y, player, other_soldiers, sock_global
    
    sock_global = None
    player_x, player_y = 400, 300
    death_timer = 0
    respawn_delay = 3000  # 3 secondes avant de pouvoir réapparaître

    # Charger les images de balles
    load_bullet_images()
    load_explosion_images()

    menu = Menu(screen)
    action, ip = menu.show()
    if action is None:
        pygame.quit()
        return

    pseudo, soldier_type = menu.show_profile_selection()
    if pseudo is None:
        pygame.quit()
        return

    if action == 'host':
        threading.Thread(target=server_start, daemon=True).start()
        host = '127.0.0.1'
        # Attendre que le serveur démarre
        time.sleep(0.5)
    else:
        host = ip

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # Désactiver Nagle pour réduire la latence
        sock.connect((host, DEFAULT_PORT))
        sock_global = sock  # Stocker la socket dans une variable globale pour l'utiliser ailleurs
        logger.info(f"Connecté au serveur {host}:{DEFAULT_PORT}")
    except socket.error as e:
        logger.error(f"Erreur de connexion: {e}")
        pygame.quit()
        return

    # Démarrer le thread de réception
    receive_thread = threading.Thread(target=receive_data, args=(sock,), daemon=True)
    receive_thread.start()

    # Créer le joueur local
    player = Soldier(player_x, player_y, soldier_type, pseudo)

    # Variables pour la boucle principale
    clock = pygame.time.Clock()
    running = True
    last_shot_time = 0
    shot_cooldown = 300  # millisecondes
    last_position_update = 0
    position_update_rate = 50  # millisecondes
    fps_display = True
    
    # Attendre de recevoir l'ID client
    wait_start = time.time()
    while client_id is None:
        if time.time() - wait_start > 5:  # Timeout de 5 secondes
            logger.error("Timeout en attendant l'ID client")
            running = False
            break
        time.sleep(0.1)
    
    # Boucle principale du jeu
    while running:
        # Gestion des événements
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F3:
                    fps_display = not fps_display
                elif event.key == pygame.K_r and player.health <= 0 and pygame.time.get_ticks() - death_timer > respawn_delay:
                    # Réapparaître si mort et touche R pressée
                    player = respawn_player(player)
                    if sock_global:
                        send_health_update(sock_global, player.health)
                        send_player_position(sock, player)
        
        # Gestion du clavier (seulement si le joueur est vivant)
        keys = pygame.key.get_pressed()
        
        # Variables pour déterminer si la position a changé
        player_moved = False
        current_time = pygame.time.get_ticks()
        
        if player.health > 0:
            # Normal player movement
            player_moved = player.update(keys)
            
            # Limiter la position du joueur aux limites de la carte
            player.x = max(0, min(player.x, map_width - 50))
            player.y = max(0, min(player.y, map_height - 50))
            
            # Normal position update when moving
            if player_moved or current_time - last_position_update > position_update_rate:
                last_position_update = current_time
                send_player_position(sock, player)
            
            # Gestion des tirs
            if keys[pygame.K_SPACE] and current_time - last_shot_time > shot_cooldown:
                last_shot_time = current_time
                
                # Déterminer la direction du tir en fonction de la direction du joueur
                direction = (1, 0)  # Direction par défaut
                if player.direction == SoldierDirection.LEFT:
                    direction = (-1, 0)
                elif player.direction == SoldierDirection.RIGHT:
                    direction = (1, 0)
                elif player.direction == SoldierDirection.BACK:
                    direction = (0, -1)
                elif player.direction == SoldierDirection.FRONT:
                    direction = (0, 1)
                
                # Envoyer le tir au serveur
                send_shot(sock, player, direction)
        else:
            # Si le joueur vient de mourir, enregistrer le moment
            if death_timer == 0:
                death_timer = pygame.time.get_ticks()
        
        # Mise à jour de la caméra pour suivre le joueur en douceur
        target_camera_x = player.x - SCREEN_WIDTH // 2
        target_camera_y = player.y - SCREEN_HEIGHT // 2
        
        # Limiter la caméra aux limites de la carte
        target_camera_x = max(0, min(target_camera_x, map_width - SCREEN_WIDTH))
        target_camera_y = max(0, min(target_camera_y, map_height - SCREEN_HEIGHT))
        
        # Mouvement fluide de la caméra
        camera_x += (target_camera_x - camera_x) * camera_speed
        camera_y += (target_camera_y - camera_y) * camera_speed
        
        # Force position update every 2 seconds even if not moving
        force_update_interval = 2000  # ms
        if player and player.health > 0 and current_time - last_position_update > force_update_interval:
            last_position_update = current_time
            if sock_global:
                send_player_position(sock, player)
        
        # Mise à jour des tirs
        update_shots()
        
        # Vérification des collisions (seulement si le joueur est vivant)
        if player.health > 0:
            check_shot_collisions()
        
        # Effacer l'écran
        screen.fill((0, 0, 0))
        
        # Dessiner la carte
        map_manager.draw(screen, camera_x, camera_y)
        
        # Dessiner les autres joueurs (seulement ceux qui sont vivants)
        with data_lock:
            other_player_list = list(other_players.items())
        
        for pid, player_data in other_player_list:
            # Unpack the player data
            if len(player_data) >= 5:  # New format with vehicle info
                pos, name, soldier_type = player_data[0], player_data[1], player_data[2]
            else:  # Legacy format for backward compatibility
                pos, name, soldier_type = player_data

            if pid not in other_soldiers:
                # Créer un nouvel objet Soldier s'il n'existe pas
                other_soldiers[pid] = Soldier(pos[0], pos[1], soldier_type, name)
            else:
                # Mettre à jour la position du soldat existant
                other_soldiers[pid].x = pos[0]
                other_soldiers[pid].y = pos[1]
            
            # Dessiner le soldat s'il est vivant
            if other_soldiers[pid].health > 0 or other_soldiers[pid].state != SoldierState.DEAD:
                other_soldiers[pid].draw(screen, camera_x, camera_y)
        
        # Nettoyer les soldats déconnectés
        with data_lock:
            disconnected_players = set(other_soldiers.keys()) - set(other_players.keys())
        
        for pid in disconnected_players:
            del other_soldiers[pid]
        
        # Dessiner les tirs
        draw_shots(screen, camera_x, camera_y)
        
        # Dessiner le joueur local s'il est vivant
        if (player.health > 0 or player.state != SoldierState.DEAD):
            player.draw(screen, camera_x, camera_y)
        
        # Afficher l'écran de mort si le joueur est mort
        if player.health <= 0:
            draw_death_screen(screen)
        
        # Afficher les FPS si activé
        if fps_display:
            fps_text = font.render(f"FPS: {int(clock.get_fps())}", True, WHITE)
            screen.blit(fps_text, (10, 10))
        
        # Rafraîchir l'écran
        pygame.display.flip()
        
        # Limiter les FPS
        clock.tick(60)
    
    # Fermer la connexion
    sock.close()
    pygame.quit()

if __name__ == "__main__":
    main()