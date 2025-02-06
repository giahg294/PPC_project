from constants import *
import multiprocessing as mp
import json
import time


# Files d'attente pour les quatre sections de l'intersection
section_queues = {
    N: mp.Queue(),
    S: mp.Queue(),
    W: mp.Queue(),
    E: mp.Queue()
}
# Processus de coordination du trafic
def coordinator(traffic_light, display_socket):
    """Coordonner la circulation des véhicules et envoyer les données au serveur d'affichage"""
    while True:
        ns, we = traffic_light.get_state()
        # Obtenir les files d'attente pour toutes les directions
        for direction, queue in section_queues.items():
            if not queue.empty():
                vehicle = queue.get()
                if vehicle['priority'] == -1:
                    display_socket.sendall((json.dumps(vehicle) + "\n").encode())
                    print(f"[Coordinator] Vehicule d'urgence depuis {vehicle['entry']} vers {vehicle['exit']} a TRAVERSE l'intersection.")
                    continue  # 优先车辆通过后不再检查其他条件，直接继续循环
                if (vehicle['entry'] in [N, S] and ns == LIGHT_GREEN) or (vehicle['entry'] in [E, W] and we == LIGHT_GREEN):
                    # Si les feux sont verts, le véhicule peut passer
                    display_socket.sendall((json.dumps(vehicle) + "\n").encode())  # Send each vehicle as a separate JSON object with a newline
                    print(f"[Coordinator] Vehicule depuis {vehicle['entry']} vers {vehicle['exit']} a TRAVERSE l'intersection.")
                else:
                    # Si les feux sont rouges, le véhicule doit attendre
                    queue.put(vehicle)  # Remettre le véhicule dans la file d'attente
                    display_socket.sendall((json.dumps(vehicle) + "\n").encode())  # Send each vehicle as a separate JSON object with a newline
                    print(f"[Coordinator] Vehicule depuis {vehicle['entry']} en ATTENTE pour aller vers {vehicle['exit']}")
        time.sleep(1)