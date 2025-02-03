import multiprocessing as mp
import random
import time
import os
import signal
import socket
import datetime
import ast
import json

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
        time.sleep(random.randint(3, 5))  # Génération de véhicules à intervalles aléatoires
        entry = random.choice(DIRECTIONS)
        exit = random.choice(DIRECTIONS)

        # S'assurer que l'entrée et la sortie sont différentes
        while entry == exit:
            exit = random.choice(DIRECTIONS)

        vehicle = {
            "type": "normal",
            "entry": entry,
            "exit": exit,
            "priority": vehicle_priority({"entry": entry, "exit": exit})  # Définir la priorité
        }
        section_queues[entry].put(vehicle)
        print(f"[Trafic Normal] Nouveau véhicule de {vehicle['entry']} veut aller vers {vehicle['exit']} (priorité : {vehicle['priority']})")

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
            "exit": exit,
            "priority": 0  # Les véhicules prioritaires passent en priorité
        }

        section_queues[entry].put(vehicle)
        os.kill(light_pid, signal.SIGUSR1)  # Envoie un signal pour notifier la présence d'un véhicule priority
        print(f"[Trafic Prioritaire] Nouveau véhicule d'urgence de {vehicle['entry']} veut aller vers {vehicle['exit']}")

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
        # Passer au feu vert pour la direction nord-sud et rouge pour est-ouest
        traffic_light.set_state(LIGHT_GREEN, LIGHT_RED)
        print("[Traffic Light] Changement : Feu vert Nord-Sud, Feu rouge Est-Ouest")
        time.sleep(UPDATE_INTERVAL)
        
        # Passer au feu rouge pour la direction nord-sud et vert pour est-ouest
        traffic_light.set_state(LIGHT_RED, LIGHT_GREEN)
        print("[Traffic Light] Changement : Feu rouge Nord-Sud, Feu vert Est-Ouest")
        time.sleep(UPDATE_INTERVAL)

# Processus de coordination du trafic
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
                    display_socket.sendall((json.dumps(vehicle) + "\n").encode())  # Send each vehicle as a separate JSON object with a newline
                    print(f"[Coordinator] Vehicule de {vehicle['entry']} vers {vehicle['exit']} a traversé l'intersection.")
                else:
                    # Si les feux sont rouges, le véhicule doit attendre
                    queue.put(vehicle)  # Remettre le véhicule dans la file d'attente
                    display_socket.sendall((json.dumps(vehicle) + "\n").encode())  # Send each vehicle as a separate JSON object with a newline
        time.sleep(1)

# Serveur d'affichage (reçoit et affiche les informations des véhicules)
def display_server():
    """Fournit une connexion réseau pour afficher l'état du trafic"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("localhost", 6666))  # Liaison au port local
    server.listen(1)
    print("[Affichage] En attente de connexion...")
    while True:
        client_socket, _ = server.accept()
        buffer = ""
        print("[Affichage] Connecté !")
        print("[-- Nord --] : ")
        print("[-- Sud --] :")
        print("[-- Est --] : ")
        print("[-- Ouest --] : ")

        while True:
            data = client_socket.recv(1024).decode()
            if not data:
                break

            buffer += data  # Append new data to buffer
            while "\n" in buffer:  # Process only complete JSON objects
                json_str, buffer = buffer.split("\n", 1)  # Split at the first newline
                dico = json.loads(json_str)  # Convert JSON string to dictionar
                # dico = ast.literal_eval(data.decode())
                type = dico['type']
                entree = dico['entry']
                sortie = dico['exit']    
                print(f"[-- {entree} --] : vehicule {type} va vers {sortie}")
    client_socket.close()
    
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
