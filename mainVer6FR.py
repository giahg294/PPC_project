import multiprocessing as mp
import random
import time
import os
import signal
import socket
import datetime

# Constantes des directions
N = "North"  # Nord
S = "South"  # Sud
W = "West"   # Ouest
E = "East"   # Est
DIRECTIONS = [N, S, W, E]  # Directions possibles des véhicules
VEHICLE_TYPES = ["normal", "priority"]  # Types de véhicules : normal et prioritaire
LIGHT_GREEN = 1  # Feu vert
LIGHT_RED = 0  # Feu rouge
UPDATE_INTERVAL = 5  # Intervalle de temps pour le changement de feu (secondes)

# Classe de mémoire partagée pour l'état des feux de circulation
class TrafficLight:
    def __init__(self):
        self.light_state = mp.Array('i', [LIGHT_GREEN, LIGHT_RED])  # NS: Feu vert, WE: Feu rouge

    def set_state(self, ns, we):
        """Définir l'état des feux de circulation"""
        self.light_state[0] = ns  # Direction nord-sud
        self.light_state[1] = we  # Direction est-ouest

    def get_state(self):
        """Obtenir l'état des feux de circulation"""
        return self.light_state[0], self.light_state[1]

# Quatre files d'attente pour les sections du carrefour
section_queues = {
    N: mp.Queue(),
    S: mp.Queue(),
    W: mp.Queue(),
    E: mp.Queue()
}

# Règles de priorité des véhicules : aller tout droit > tourner à droite > tourner à gauche
def vehicle_priority(vehicle):
    entry = vehicle['entry']
    exit = vehicle['exit']
    if entry == N:
        if exit == N:
            return 0  # Priorité pour aller tout droit
        elif exit == E:
            return 1  # Priorité pour tourner à droite
        else:
            return 2  # Priorité pour tourner à gauche
    elif entry == S:
        if exit == S:
            return 0
        elif exit == W:
            return 1
        else:
            return 2
    elif entry == E:
        if exit == E:
            return 0
        elif exit == N:
            return 1
        else:
            return 2
    elif entry == W:
        if exit == W:
            return 0
        elif exit == S:
            return 1
        else:
            return 2

# Générateur de véhicules normaux
def normal_traffic_gen():
    """Simuler la génération de véhicules normaux aléatoires et les ajouter dans la file d'attente correspondante"""
    while True:
        time.sleep(random.randint(1, 3))  # Générer des véhicules à intervalles aléatoires
        entry = random.choice(DIRECTIONS)
        exit = random.choice(DIRECTIONS)

        # Assurer que entry et exit soient différents
        while entry == exit:
            exit = random.choice(DIRECTIONS)

        vehicle = {
            "type": "normal",
            "entry": entry,
            "exit": exit,
            "priority": vehicle_priority({"entry": entry, "exit": exit})  # Définir la priorité
        }
        section_queues[entry].put(vehicle)
        print(f"[Normal Traffic] New vehicle: {vehicle}")

# Générateur de véhicules prioritaires (comme ambulances, camions de pompiers)
def priority_traffic_gen(light_pid):
    """Simuler la génération de véhicules prioritaires et notifier le processus de feux de circulation"""
    while True:
        time.sleep(random.randint(5, 10))  # Génération moins fréquente de véhicules prioritaires
        entry = random.choice(DIRECTIONS)
        exit = random.choice(DIRECTIONS)

         # Assurer que entry et exit soient différents
        while entry == exit:
            exit = random.choice(DIRECTIONS)
        vehicle = {
            "type": "priority",
            "entry": entry,
            "exit": exit,
            "priority": 0  # Les véhicules prioritaires passent en priorité
        }
        section_queues[entry].put(vehicle)
        os.kill(light_pid, signal.SIGUSR1)  # Envoyer un signal pour notifier qu'il y a un véhicule prioritaire
        print(f"[Priority Traffic] Emergency vehicle detected: {vehicle}")

# Contrôleur des feux de circulation
def light_controller(traffic_light):
    """Contrôler le changement de l'état des feux et gérer les signaux des véhicules prioritaires"""
    def emergency_signal_handler(signum, frame):
        """Fonction de gestion du signal pour les véhicules prioritaires, déclenche le mode urgence"""
        print("[Traffic Light] Emergency mode activated!")
        traffic_light.set_state(LIGHT_RED, LIGHT_RED)  # Tous les feux deviennent rouges
        time.sleep(3)  # Laisser passer les véhicules prioritaires
        traffic_light.set_state(LIGHT_GREEN, LIGHT_RED)  # Reprendre le cycle normal des feux
    
    signal.signal(signal.SIGUSR1, emergency_signal_handler)  # Enregistrer le gestionnaire de signal
    
    while True:
        # Passer au feu vert pour la direction nord-sud et rouge pour est-ouest
        traffic_light.set_state(LIGHT_GREEN, LIGHT_RED)
        print("[Traffic Light] State changed: South-North Green, East-West Red")
        time.sleep(UPDATE_INTERVAL)
        
        # Passer au feu rouge pour la direction nord-sud et vert pour est-ouest
        traffic_light.set_state(LIGHT_RED, LIGHT_GREEN)
        print("[Traffic Light] State changed: South-North Red, East-West Green")
        time.sleep(UPDATE_INTERVAL)


# Processus de coordination des véhicules
def coordinator(traffic_light, display_socket):
    """Coordonner la circulation des véhicules et envoyer les données au serveur d'affichage"""
    while True:
        ns, we = traffic_light.get_state()
        # Obtenir les files d'attente pour toutes les directions
        for direction, queue in section_queues.items():
            if not queue.empty():
                vehicle = queue.get()
                if (vehicle['entry'] in [N, S] and ns == LIGHT_GREEN) or (vehicle['entry'] in [E, W] and we == LIGHT_GREEN):
                    # Si les feux sont verts, le véhicule peut passer
                    display_socket.sendall(f"Vehicle from {vehicle['entry']} going to {vehicle['exit']} with priority {vehicle['priority']}, Light: Green".encode())
                    print(f"[Coordinator] Vehicle from {vehicle['entry']} going to {vehicle['exit']} has passed through the intersection.")
                else:
                    # Si les feux sont rouges, le véhicule doit attendre
                    queue.put(vehicle)  # Remettre le véhicule dans la file d'attente
                    display_socket.sendall(f"Vehicle from {vehicle['entry']} going to {vehicle['exit']} with priority {vehicle['priority']}, Light: Red (Waiting)".encode())
        time.sleep(1)


# Serveur d'affichage (recevoir et afficher les informations des véhicules)
def display_server():
    """Fournir une connexion réseau pour afficher l'état du trafic"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("localhost", 6666))  # Lier au port local
    server.listen(1)
    print("[Display] Waiting for connection...")
    conn, addr = server.accept()  # Attendre une connexion
    print("[Display] Connected!")
    while True:
        data = conn.recv(1024)
        if not data:
            break
        print(f"[Display] {data.decode()}")

# Fonction principale
def main():
    traffic_light = TrafficLight()  # Objet pour les feux de circulation

    # Démarrer le processus du serveur d'affichage
    display_process = mp.Process(target=display_server)
    display_process.start()
    
    time.sleep(1)  # Attendre que le serveur démarre

    display_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    display_socket.connect(("localhost", 6666))  # Connexion au serveur d'affichage

    # Démarrer les différents processus
    light_process = mp.Process(target=light_controller, args=(traffic_light,))
    light_process.start()
    priority_traffic_process = mp.Process(target=priority_traffic_gen, args=(light_process.pid,))
    priority_traffic_process.start()
    
    coordinator_process = mp.Process(target=coordinator, args=(traffic_light, display_socket))
    normal_traffic_process = mp.Process(target=normal_traffic_gen)
    coordinator_process.start()
    normal_traffic_process.start()
    
    # Attendre la fin des processus
    light_process.join()
    coordinator_process.join()
    normal_traffic_process.join()
    priority_traffic_process.join()
    display_process.join()

if __name__ == "__main__":
    main()
