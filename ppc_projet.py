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

# Direction opposée (utilisée pour gérer les véhicules tournant à gauche en attente)
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
        print(f"Changement des feux - {N} et {S}sont {'Verts' if ns_green else 'Rouges'}，{E} et {W} sont {'Verts' if we_green else 'Rougs'}")

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
        print("\n!!! 🚑 Mode urgence activé ---")
        self.print_light_states()

    def exit_emergency_mode(self):
        with self.lock:
            self.emergency_mode.value = False
        self.set_normal_state(LIGHT_GREEN, LIGHT_RED)
        print("\n!!! Mode urgence désactivé, retour à la normale !!!")
        self.print_light_states()


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
                    # Ne conserver que les 10 derniers messages
                    if len(log_messages) > 10:
                        log_messages.pop(0)

    def socket_listener():
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(("localhost", DISPLAY_PORT))
        server_socket.listen(5)
        print("Le serveur Display attend la connexion...")
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

        #【Mémoire partagée】État des feux de signalisation
        print("\n 【Mémoire partagée】État des feux de signalisation : ")
        traffic_light.print_light_states()

        # Afficher les queues pour chaque direction
        print("\n【Queues】")
        for direction, queue in section_queues.items():
            queue_str = ", ".join([v['license_plate'] for v in queue])
            print(f"Direction {direction}: {queue_str}")

        # Afficher les nouveaux messages d'une queue
        print("\n【Communication par socket】Dernier message :")
        with log_lock:
            for msg in log_messages:
                print(msg)

        # Alerte si un véhicule d'urgence arrive
        if not msg_queue.empty():
            emergency_msg = msg_queue.get()
            print(f"\n!!! Véhicule d'urgence arrive：{emergency_msg} !!!")
        time.sleep(1)


def send_to_display(message, msg_queue):
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(("localhost", DISPLAY_PORT))
        client_socket.sendall(message.encode())
        client_socket.close()
    except ConnectionRefusedError:
        print("Serveur de Display indisponible, réessai en cours...")

    # Envoyer le message d'arrivée d'un véhicule d'urgence à la queue d'affichage
    msg_queue.put(message)


# === Lights: Processus de gestion des feux de signalisation ===
def light_controller(traffic_light, emergency_event, msg_queue, emergency_flag):
    last_state = None  # Utilisé pour suivre le dernier état du signal lumineux
    while True:
        if emergency_event.is_set():
            # Lorsqu'un événement d'urgence est reçu, passer en mode d'urgence
            print("light_controller détecte un événement d'urgence, basculement en mode d'urgence.")  # Sortie de débogage pour confirmer le déclenchement de l'événement
            emergency_event.clear()  # Réinitialiser le drapeau d'événement pour éviter une réactivation
            send_to_display("Véhicule d'urgence arrivé, changement des feux de signalisation", msg_queue)  # Envoyer le message d'événement d'urgence à l'afficheur
        else:
            # En mode normal:
            # basculer régulièrement l'état des feux de signalisation
            current_ns = traffic_light.light_states[DIR_INDEX[N]]
            new_ns = LIGHT_RED if current_ns == LIGHT_GREEN else LIGHT_GREEN
            traffic_light.set_normal_state(new_ns, LIGHT_RED if new_ns == LIGHT_GREEN else LIGHT_GREEN)
            # Si l'état a changé, envoyer une mise à jour
            if last_state != traffic_light.light_states[:]:
                send_to_display(f"Traffic light updated: {new_ns}  (Rouge==0 et Vert==1)", msg_queue)
                last_state = traffic_light.light_states[:]
                traffic_light.print_light_states()  # Afficher les nouveaux états des feux de signalisation
        time.sleep(UPDATE_INTERVAL)




# === Processus de génération de véhicules normalss  ===
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
        section_queues[entry].append(vehicle)
        print(f"\n--- Nouveau véhicule {vehicle['license_plate']} entrant par la direction {entry} ---")


# priority_traffic_gen
# === Processus de génération de véhicules d'urgence ===
def ambulance_gen(section_queues, traffic_light, emergency_event, msg_queue, emergency_flag):
    while True:
        time.sleep(random.randint(11, 15))
        entry = random.choice(DIRECTIONS)
        exit_dir = random.choice([d for d in DIRECTIONS if d != entry])
        vehicle = {
            "license_plate": generate_ambulance_plate(),
            "type": "priority",  # Véhicule d'urgence 
            "entry": entry,
            "exit": exit_dir,
            "priority": vehicle_priority(entry, exit_dir)
        }
        # Pour assurer la priorité des véhicules d'urgence, 
        # insérer le véhicule en tête de la queue
        section_queues[entry].insert(0, vehicle)
        print(f"\n--- !!! Véhicule d'urgence  {vehicle['license_plate']} entrant par la direction {entry}, destination {exit_dir} ---")

        # Signaler l'événement d'urgence
        emergency_event.set()  # Définir le drapeau d'événement d'urgence
        print("Événement d'urgence déclenché, préparation pour le changement des feux de signalisation")

        traffic_light.enter_emergency_mode(entry)

        if not emergency_flag.value:
            # ?????????????????????????????????????????????????????????
            # ?????????????????????????????????????????????????????????
            # 跟前一个有什么区别啊??????????????????????????????????
            msg_queue.put(f"Véhicule d'urgence {vehicle['license_plate']} arrive, destination {exit_dir}")
            emergency_flag.value = True


# === Processus coordinateur : autoriser le passage des véhicules en fonction de 
# l'état des feux de signalisation et des règles de priorité ===
def coordinator(traffic_light, section_queues, msg_queue):
    def process_direction(direction):
        processed = []
        if traffic_light.get_light_state(direction) != LIGHT_GREEN:
            return processed
        # Trier les véhicules de la même direction par ordre de priorité 
        # (droite > tourner à droite > tourner à gauche)
        vehicles = sorted(list(section_queues[direction]), key=lambda v: v['priority'])
        for v in vehicles:
            can_pass = False
            opp_dir = OPPOSITE_DIR[direction]
            if v['type'] == "priority":
                can_pass = True
            # aller tout droite
            elif v['priority'] == 1:  
                can_pass = True
            # tourner à droite
            elif v['priority'] == 2: 
                can_pass = True  
            # tourner à gauche : attendre les véhicules en face qui vont tout droit
            elif v['priority'] == 3:
                if not any(p['priority'] == 1 for p in list(section_queues[opp_dir])):
                    can_pass = True
            if can_pass:
                processed.append(v)
                # Retirer le véhicule de la queue
                # pour éviter un traitement répétitif
                section_queues[direction].remove(v)
                action = ["va tout droite", "tourne à droite", "tourne à gauche"][v['priority'] - 1]
                # Il faut passer msg_queue à la fonction send_to_display
                send_to_display(f"Véhicule {v['license_plate']} a passé ：{v['entry']} → {v['exit']} ({action})", msg_queue)
        return processed

    while True:
        if traffic_light.emergency_mode.value:
            emergency_dir = DIR_INDEX_REVERSE.get(traffic_light.emergency_direction.value, None)
            if emergency_dir:
                process_direction(emergency_dir)
        else:
            for d in DIRECTIONS:
                process_direction(d)
        time.sleep(1)



# === Gestion de la terminaison du programme ===
def termination_handler(_sig, _frame):
    print("\nLe programme se termine, en cours de nettoyage des ressources...")
    sys.exit(0)


signal.signal(signal.SIGINT, termination_handler)

# Fonction principale
def main():
    manager = mp.Manager()

    # Chaque direction a une queue partagée sous forme de liste
    section_queues = {d: manager.list() for d in DIRECTIONS}
    # Utiliser Event pour simuler la notification d'un mode d'urgence
    emergency_event = mp.Event()

    traffic_light = TrafficLight()
    msg_queue = mp.Queue()  # Queue des messages pour transmettre les alertes d'arrivée des véhicules d'urgence
    # Drapeau d'urgence

    emergency_flag = mp.Value('b', False)  # Pour marquer si l'événement d'urgence a déjà été traité
    # Démarrer le processus d'affichage
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


