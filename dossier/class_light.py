from constants import *
import multiprocessing as mp
import time
import signal


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