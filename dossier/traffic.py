from constants import *
import time
import random
from class_vehicle import *
from coordinator import *
import signal
import os

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
            "priority": -1  # Les véhicules prioritaires passent en priorité
        }

        section_queues[entry].put(vehicle)
        os.kill(light_pid, signal.SIGUSR1)  # Envoie un signal pour notifier la présence d'un véhicule priority
        print(f"[Trafic Prioritaire] Nouveau véhicule d'urgence de {vehicle['entry']} veut aller vers {vehicle['exit']}")