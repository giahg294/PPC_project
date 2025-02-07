import multiprocessing as mp
import random
import time
import socket
import sys
import os
import signal

# === Constantes ===
N = "North"
S = "South"
W = "West"
E = "East"
DIRECTIONS = [N, S, W, E]
LIGHT_GREEN = 1
LIGHT_RED = 0
UPDATE_INTERVAL = 8  # Intervalle de mise à jour des feux en mode normal (secondes)

# Indexation des directions pour un accès plus facile
DIR_INDEX = {N: 0, S: 1, E: 2, W: 3}
DIR_INDEX_REVERSE = {v: k for k, v in DIR_INDEX.items()}

# Directions opposées (utilisée pour gérer les véhicules tournant à gauche en attente)
OPPOSITE_DIR = {
    N: S, S: N,
    E: W, W: E
}


# === Feux de signalisation (mémoire partagée) ===
class TrafficLight:
    def __init__(self):
        # Un tableau de mémoire partagée pour stocker l'état des feux dans les quatre directions
        # accessible par le processus coordinator
        self.light_states = mp.Array('i', [LIGHT_GREEN, LIGHT_GREEN, LIGHT_RED, LIGHT_RED])
        self.emergency_mode = mp.Value('b', False)
        self.emergency_direction = mp.Value('i', -1)
        self.emergency_count = mp.Value('i', 0)
        self.lock = mp.Lock()

    def get_light_state(self, direction):
        with self.lock:
            return self.light_states[DIR_INDEX[direction]]

    def print_light_states(self):
        states = []
        for d in DIRECTIONS:
            state = "Vert" if self.light_states[DIR_INDEX[d]] == LIGHT_GREEN else "Rouge"
            states.append(f"{d}:{state}")
        print(f"État actuel des feux：{', '.join(states)}")
        

    def set_normal_state(self, ns_green, we_green):
        with self.lock:
            self.light_states[DIR_INDEX[N]] = ns_green
            self.light_states[DIR_INDEX[S]] = ns_green
            self.light_states[DIR_INDEX[E]] = we_green
            self.light_states[DIR_INDEX[W]] = we_green
            self.emergency_mode.value = False
            self.emergency_direction.value = -1
        print(f"Changement des feux - {N} et {S}sont {'Verts' if ns_green else 'Rouges'}，{E} et {W} sont {'Verts' if we_green else 'Rouges'}")
        time.sleep(7)
    def enter_emergency_mode(self, direction):
        with self.lock:
            dir_index = DIR_INDEX[direction]
            # Met tous les feux au rouge sauf la direction d'urgence
            for i in range(4):
                self.light_states[i] = LIGHT_RED
            self.light_states[dir_index] = LIGHT_GREEN
            self.emergency_mode.value = True
            self.emergency_direction.value = dir_index
            self.emergency_count.value += 1
        print("\n!!! 🚑 Entrer Mode Urgence ---")
        time.sleep(7)
        self.print_light_states()
        time.sleep(7)

    def exit_emergency_mode(self):
        with self.lock:
            self.emergency_mode.value = False
        self.set_normal_state(LIGHT_GREEN, LIGHT_RED)
        print("\n!!! Mode urgence désactivé, retour à la normale !!!")
        time.sleep(7)
        self.print_light_states()
        time.sleep(7)



# === Génération des plaques d'immatriculation ===
global_car_id = mp.Value('i', 0) # variables partagées , initialement egale a 0
def generate_license_plate():
    with global_car_id.get_lock():
        global_car_id.value += 1
        return f"CAR-{global_car_id.value:04d}"


global_amb_id = mp.Value('i', 0)
def generate_ambulance_plate():
    with global_amb_id.get_lock():
        global_amb_id.value += 1
        return f"AMB-{global_amb_id.value:04d}"


def vehicle_priority(entry, exit_dir):
    # Définition des priorités : 
    # Ambulance(de type "priority" dans le dictionnaire des voitures) > Tout droit (1) > Droite (2) > Gauche (3)
    priority_map = {
        N: {S: 1, W: 2, E: 3},
        S: {N: 1, E: 2, W: 3},
        E: {W: 1, N: 2, S: 3},
        W: {E: 1, S: 2, N: 3}
    }
    return priority_map[entry][exit_dir]


# === Communication par socket ：display ===
DISPLAY_PORT = 65432


def display_server(traffic_light, section_queues, msg_queue):
    from threading import Thread, Lock
    log_messages = []
    log_lock = Lock()

    def handle_connection(conn, addr):
        with conn:
            data = conn.recv(1024)
            if data:
                message = data.decode()
                with log_lock:
                    log_messages.append(message)
                    # Ne conserver que les 15 derniers messages
                    if len(log_messages) > 15:
                        log_messages.pop(0)

    def socket_listener():
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(("localhost", DISPLAY_PORT))
        server_socket.listen(5)
        print("Le display_server attend la connexion...")
        while True:
            try:
                conn, addr = server_socket.accept()
                Thread(target=handle_connection, args=(conn, addr), daemon=True).start()
            except Exception as e:
                print("Exception de socket_listener :", e)

    # Démarrer le thread d'écoute 
    listener_thread = Thread(target=socket_listener, daemon=True)
    listener_thread.start()

    # Mise à jour périodique de l'affichage de l'interface
    while True:
        # Effacer l'écran
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 50)
        print("Simulation de traffic en temps réel".center(50))
        print("=" * 50)

        # 【Mémoire partagée】État des feux de signalisation
        print("\n【Mémoire partagée】État des feux de signalisation: ")
        traffic_light.print_light_states()

        # Afficher les files d'attente pour chaque direction
        print("\n【File d'attente】")
        for direction, queue in section_queues.items():
            queue_str = ""
            # Récupérer toutes les voitures dans la file d'attente et afficher leurs plaques d'immatriculation
            while not queue.empty():
                vehicle = queue.get_nowait()  # Sans blocage, récupérer la voiture dans la file d'attente
                queue_str += f"{vehicle['license_plate']}, "
            # Afficher les informations des voitures
            print(f"Direction {direction}: {queue_str.rstrip(', ')}")

        # Afficher les nouveaux messages d'une queue
        print("\n【Communication par socket】Dernier message :")
        with log_lock:
            for msg in log_messages:
                print(msg)
        
        time.sleep(3)



# === Processus de génération de véhicules normales ===
def normal_traffic_gen(section_queues):
    while True:
        time.sleep(random.randint(1, 3))
        entry = random.choice(DIRECTIONS)
        exit_dir = random.choice([d for d in DIRECTIONS if d != entry])
        vehicle = {
            "license_plate": generate_license_plate(),
            "type": "normal",
            "entry": entry,
            "exit": exit_dir,
            "priority": vehicle_priority(entry, exit_dir)
        }
        # Débogage : Afficher les informations de la voiture normale.
        print(f"\n--- NORMALE: Voiture normale {vehicle['license_plate']} entrant par la direction {entry} , destination {exit_dir}---")
        time.sleep(7)
        section_queues[entry].put(vehicle)  # Placer la voiture dans la message queue correspondante  à la direction d'entrée
    

# === Processus de génération de véhicules d'urgence ===
def ambulance_gen(section_queues, traffic_light, emergency_event, msg_queue, emergency_flag):
    while True:
        time.sleep(random.randint(35, 40))  # Simuler le temps d'arrivée aléatoire des véhicules d'urgence
        entry = random.choice(DIRECTIONS)  # Choisir aléatoirement la direction d'entrée
        exit_dir = random.choice([d for d in DIRECTIONS if d != entry])  # Choisir aléatoirement une direction de sortie différente

        # Utiliser generate_ambulance_plate() pour générer la plaque d'immatriculation de l'ambulance
        vehicle = {
            "license_plate": generate_ambulance_plate(),  
            "type": "priority",  
            "entry": entry,
            "exit": exit_dir,
            "priority": vehicle_priority(entry, exit_dir)  # La priorité est déterminée par la fonction `vehicle_priority`
        }

        # Debogage: Afficher les informations du véhicule pour confirmer la plaque et le type
        print(f" Véhicule d'urgence arrive - Plaque d'immatriculation: {vehicle['license_plate']} Type: {vehicle['type']} Entrant par: {entry} Direction cible: {exit_dir}")
        
        # Insérer le véhicule d'urgence dans la message queue correspondante à la direction d'entrée
        section_queues[entry].put(vehicle)

        # Signaler un événement d'urgence pour activer le mode prioritaire
        emergency_event.set()  
        print("Événement d'urgence déclenché, préparation pour le changement des feux de signalisation")

        traffic_light.enter_emergency_mode(entry)

        # Envoi un message de l'arrivee d'une voiture urgence
        if not emergency_flag.value:
            msg_queue.put(f"Voiture d'urgence {vehicle['license_plate']} arrive，destination {exit_dir}")
            emergency_flag.value = True


def send_to_display(message, msg_queue, emergency_flag=False):
    
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(("localhost", DISPLAY_PORT))
        client_socket.sendall(message.encode())
        client_socket.close()
    except ConnectionRefusedError:
        print("Display server indisponible，reessai en cours...")

    # Ajouter le message à la file d'attente des messages, déclencher l'événement d'urgence uniquement en mode d'urgence
    if emergency_flag:
        msg_queue.put(f"!!! Voiture d'urgence arrive：{message} !!!")
    else:
        msg_queue.put(message)

    # print(f"Message envoyée a serveur Display: {message}")  # Debogage


# === Processus coordinateur : autoriser le passage des véhicules en fonction de 
# l'état des feux de signalisation et des règles de priorité ===

def coordinator(traffic_light, section_queues, msg_queue):
    def process_direction(direction):
        processed = []

        # Si le feu de signalisation de la direction actuelle est rouge, les véhicules ne peuvent pas passer
        if traffic_light.get_light_state(direction) != LIGHT_GREEN:
            # print(f"Direction {direction} est rouge, les véhicules ne peuvent pas passer")
            return processed

        # Sortir toutes les véhicules de la même direction , Trier par ordre de priorité 
        vehicles = []
        while not section_queues[direction].empty():
            vehicles.append(section_queues[direction].get_nowait())  # Acquerir toutes les véhicules de la même direction

        # (urgence > droite > tourner à droite > tourner à gauche)
        vehicles = sorted(vehicles, key=lambda v: v['priority'])

        for v in vehicles:
            print(f"Traiter la voiture {v['license_plate']}, Type: {v['type']}, Entrant par : {v['entry']}, Direction cible: {v['exit']}")  # Debogage
            time.sleep(7)
            can_pass = False
            opp_dir = OPPOSITE_DIR[direction]  # Obtenir la direction opposee pour le jugement de tourner à gauche

            # Déclencher le message pour les véhicules prioritaires uniquement
            if v['type'] == "priority":
                can_pass = True  
                send_to_display(f"Voiture d'urgence {v['license_plate']} arrive，destination {v['exit']}", msg_queue, emergency_flag=True)
                # print(f"Message envoyé à l'affichage: Voiture d'urgence {v['license_plate']} arrive, destination {v['exit']}")  # Debogage
            
            elif v['priority'] == 1:  # aller tout droit
                can_pass = True
            elif v['priority'] == 2:  # tourner a droite
                can_pass = True
            elif v['priority'] == 3:  # tourner a gauche
                 # Les véhicules tournant à gauche ne peuvent passer que s'il n'y a pas de véhicules en ligne droite en face
                 # Il faut vérifier la file d'attente de la direction opposée pour les véhicules en ligne droite
                 opp_vehicles = []
                 while not section_queues[opp_dir].empty():
                     opp_vehicles.append(section_queues[opp_dir].get_nowait())

                 # Can_pass si y'a pas de voiture allant tout droit dans le sens oppose
                 if not any(p['priority'] == 1 for p in opp_vehicles):
                     can_pass = True

            if can_pass:
                processed.append(v)  # Traitement de cette voiture fini, mettre dans la liste Processed
                remove_from_queue(section_queues[direction], v)
                action = ["va tout droite", "tourne à droite", "tourne à gauche"][v['priority'] - 1]
                # Informer a Display Server que la voiture a passé
                send_to_display(f"Voiture {v['license_plate']} a passé：{v['entry']} → {v['exit']} ({action})", msg_queue)

        return processed
    
    # Surveiller en continu les feux de signalisation et les files d'attente des voies
    while True:
        if traffic_light.emergency_mode.value:
            # Si entrer en mode d'urgence, traiter les véhicules d'urgence en priorité
            emergency_dir = DIR_INDEX_REVERSE.get(traffic_light.emergency_direction.value, None)
            if emergency_dir:
                # print(f"Mode d'urgence, en train de traiter la voiture d'urgence {v['license_plate']}  dans la direction {emergency_dir} ")  # Sortie debogage
                process_direction(emergency_dir)
        else:
            # Sinon, traiter les véhicules dans chaque direction dans l'ordre normal
            for d in DIRECTIONS:
                process_direction(d)

        time.sleep(1)  # Traiter une fois par seconde


# === Lights: Processus de gestion des feux de signalisation ===
def light_controller(traffic_light, emergency_event, msg_queue, emergency_flag):
    last_state = None  # Utilisé pour suivre le dernier état du signal lumineux
    while True:
        if emergency_event.is_set():
            # Lorsqu'un événement d'urgence est reçu, passer en mode d'urgence
            # print("light_controller détecte un événement d'urgence, basculement en mode d'urgence.")  # Sortie de débogage pour confirmer le déclenchement de l'événement
            emergency_event.clear()  # Réinitialiser le drapeau d'événement pour éviter une réactivation
            send_to_display("Véhicule d'urgence arrivé, changement des feux de signalisation", msg_queue)  # Envoyer le message d'événement d'urgence à l'afficheur
        else:
            # En mode normal:
            # basculer régulièrement l'état des feux de signalisation
            current_ns = traffic_light.light_states[DIR_INDEX[N]] # Obtenire l'etat actuel de Nord et Sud
            new_ns = LIGHT_RED if current_ns == LIGHT_GREEN else LIGHT_GREEN
            traffic_light.set_normal_state(new_ns, LIGHT_RED if new_ns == LIGHT_GREEN else LIGHT_GREEN)
            # Si l'état a changé, envoyer une mise à jour
            if last_state != traffic_light.light_states[:]:
                send_to_display(f"Feux mise a jour: {new_ns}  (NS==Rouge si 0 et NS==Vert si 1)", msg_queue)
                last_state = traffic_light.light_states[:] # Renouveler last_state
                traffic_light.print_light_states()  # Afficher les nouveaux états des feux de signalisation
        time.sleep(UPDATE_INTERVAL) # attendre la prochaine changement


# === Gestion de la terminaison du programme ===
def termination_handler(_sig, _frame):
    print("\nLe programme se termine, en cours de nettoyage des ressources...")
    sys.exit(0)

signal.signal(signal.SIGINT, termination_handler)

def remove_from_queue(queue, target):
    """ 从 multiprocessing.Queue 中移除指定的元素 """
    temp_list = []

    # 读取所有元素
    while not queue.empty():
        item = queue.get()
        if item != target:  # 只存储非目标元素
            temp_list.append(item)

    # 重新放回 queue
    for item in temp_list:
        queue.put(item)

# === Fonction main ===
def main():
    manager = mp.Manager()
    section_queues = {d: mp.Queue() for d in DIRECTIONS}  # message queue
    emergency_event = mp.Event()

    traffic_light = TrafficLight()
    msg_queue = mp.Queue()  # pour la notification de l'arrivee d'une voiture d'urgence

    # Drapeau d'une voiture urgence
    emergency_flag = mp.Value('b', False)  # Pour marquer si l'événement d'urgence a déjà été traité

    # Démarrer le processus display 
    display_process = mp.Process(target=display_server, args=(traffic_light, section_queues, msg_queue))
    display_process.start()

    processes = [
        mp.Process(target=light_controller, args=(traffic_light, emergency_event, msg_queue, emergency_flag)),
        mp.Process(target=normal_traffic_gen, args=(section_queues,)),
        mp.Process(target=coordinator, args=(traffic_light, section_queues, msg_queue)),
        mp.Process(target=ambulance_gen, args=(section_queues, traffic_light, emergency_event, msg_queue, emergency_flag))
    ]

    for p in processes:
        p.start()
    for p in processes:
        p.join()

if __name__ == "__main__":
    main()
