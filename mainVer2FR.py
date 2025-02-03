import multiprocessing as mp
import random
import time
import os
import signal
import socket
import datetime

# Constantes de direction
N = "Nord"
S = "Sud"
W = "Ouest"
E = "Est"
DIRECTIONS = [N, S, W, E]  # Directions possibles des véhicules
VEHICLE_TYPES = ["normal", "prioritaire"]  # Types de véhicules : normal et prioritaire
LIGHT_GREEN = 1  # Feu vert
LIGHT_RED = 0  # Feu rouge
UPDATE_INTERVAL = 5  # Intervalle de changement des feux de circulation (secondes)

# Classe de mémoire partagée pour l'état des feux de circulation
class TrafficLight:
    def __init__(self):
        self.light_state = mp.Array('i', [LIGHT_GREEN, LIGHT_RED])  # NS : vert, WE : rouge

    def set_state(self, ns, we):
        """Définit l'état des feux de circulation"""
        self.light_state[0] = ns  # Direction nord-sud
        self.light_state[1] = we  # Direction est-ouest

    def get_state(self):
        """Récupère l'état des feux de circulation"""
        return self.light_state[0], self.light_state[1]

# Files d'attente pour les quatre sections de l'intersection
section_queues = {
    N: mp.Queue(),
    S: mp.Queue(),
    W: mp.Queue(),
    E: mp.Queue()
}

# Générateur de trafic normal
def normal_traffic_gen():
    """Simule la génération aléatoire de véhicules normaux et les ajoute à la file d'attente correspondante"""
    while True:
        time.sleep(random.randint(1, 3))  # Génération de véhicules à intervalles aléatoires
        entry = random.choice(DIRECTIONS)
        exit = random.choice(DIRECTIONS)

        # S'assurer que l'entrée et la sortie sont différentes
        while entry == exit:
            exit = random.choice(DIRECTIONS)

        vehicle = {
            "type": "normal",
            "entry": entry,
            "exit": exit
        }
        section_queues[entry].put(vehicle)
        print(f"[Trafic Normal] Nouveau véhicule : {vehicle}")

# Générateur de véhicules prioritaires (ex : ambulances, camions de pompiers)
def priority_traffic_gen(light_pid):
    """Simule la génération aléatoire de véhicules prioritaires et notifie le processus du feu de circulation"""
    while True:
        time.sleep(random.randint(5, 10))  # Moins de véhicules prioritaires
        entry = random.choice(DIRECTIONS)
        exit = random.choice(DIRECTIONS)

        # S'assurer que l'entrée et la sortie sont différentes
        while entry == exit:
            exit = random.choice(DIRECTIONS)

        vehicle = {
            "type": "prioritaire",
            "entry": entry,
            "exit": exit
        }

        section_queues[entry].put(vehicle)
        os.kill(light_pid, signal.SIGUSR1)  # Envoie un signal pour notifier la présence d'un véhicule prioritaire
        print(f"[Trafic Prioritaire] Véhicule prioritaire détecté : {vehicle}")

# Contrôleur des feux de circulation
def light_controller(traffic_light):
    """Contrôle le changement des feux de circulation et gère les signaux des véhicules prioritaires"""
    def emergency_signal_handler(signum, frame):
        """Gère le signal des véhicules prioritaires et active le mode d'urgence"""
        print("[Feu de circulation] Mode d'urgence activé !")
        traffic_light.set_state(LIGHT_RED, LIGHT_RED)  # Tous les feux passent au rouge
        time.sleep(3)  # Permet au véhicule prioritaire de passer
        traffic_light.set_state(LIGHT_GREEN, LIGHT_RED)  # Reprise du cycle normal
    
    signal.signal(signal.SIGUSR1, emergency_signal_handler)  # Enregistrement du gestionnaire de signal
    
    while True:
        traffic_light.set_state(LIGHT_GREEN, LIGHT_RED)  # Nord-Sud vert, Est-Ouest rouge
        time.sleep(UPDATE_INTERVAL)
        traffic_light.set_state(LIGHT_RED, LIGHT_GREEN)  # Nord-Sud rouge, Est-Ouest vert
        time.sleep(UPDATE_INTERVAL)

# Processus de coordination du trafic
def coordinator(traffic_light, display_socket):
    """Coordonne le passage des véhicules et envoie les données au serveur d'affichage"""
    while True:
        ns, we = traffic_light.get_state()
        for direction, queue in section_queues.items():
            if not queue.empty():
                vehicle = queue.get()
                print(f"[Coordinateur] Véhicule traité depuis {direction} : {vehicle}")
                display_socket.sendall(str(vehicle).encode())  # Envoi des informations du véhicule au serveur d'affichage
        time.sleep(1)

# Serveur d'affichage (reçoit et affiche les informations des véhicules)
def display_server():
    """Fournit une connexion réseau pour afficher l'état du trafic"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("localhost", 6666))  # Liaison au port local
    server.listen(1)
    print("[Affichage] En attente de connexion...")
    conn, addr = server.accept()  # Attente de connexion
    print("[Affichage] Connecté !")
    while True:
        data = conn.recv(1024)
        if not data:
            break
        print(f"[Affichage] {data.decode()}")

# Fonction principale
def main():
    traffic_light = TrafficLight()  # Objet feu de circulation

    # Démarrer le processus du serveur d'affichage
    display_process = mp.Process(target=display_server)
    display_process.start()
    
    time.sleep(1)  # Attente du démarrage du serveur

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
    
    # Attente de la fin des processus
    light_process.join()
    coordinator_process.join()
    normal_traffic_process.join()
    priority_traffic_process.join()
    display_process.join()

if __name__ == "__main__":
    main()
