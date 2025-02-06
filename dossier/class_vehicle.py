import random
from constants import *

class Vehicle:
    def __init__(self, vehicle_type, entry, exit):
        self.vehicle_type = vehicle_type  # "normal" ou "prioritaire"
        self.entry = entry  # Point d'entrée (Nord, Sud, Est, Ouest)
        self.exit = exit  # Point de sortie
        self.priority = self.calculate_priority()  # Calcul de la priorité

    def calculate_priority(self):
        """Définit la priorité en fonction de l'entrée et de la sortie"""
        if self.entry == self.exit:
            raise ValueError("Entrée et sortie ne peuvent pas être identiques.")

        priority_rules = {
            ("Nord", "Sud"): 0, ("Nord", "Ouest"): 1, ("Nord", "Est"): 2,
            ("Sud", "Nord"): 0, ("Sud", "Est"): 1, ("Sud", "Ouest"): 2,
            ("Est", "Ouest"): 0, ("Est", "Nord"): 1, ("Est", "Sud"): 2,
            ("Ouest", "Est"): 0, ("Ouest", "Sud"): 1, ("Ouest", "Nord"): 2,
        }
        return -1 if self.vehicle_type == "prioritaire" else priority_rules.get((self.entry, self.exit), 2)

    @staticmethod
    def generate_random(vehicle_type="normal"):
        """Génère un véhicule avec des entrées et sorties aléatoires"""
        entry, exit = random.sample(DIRECTIONS, 2)  # Sélectionner deux directions différentes
        return Vehicle(vehicle_type, entry, exit)

    def __repr__(self):
        return f"Vehicle(type={self.vehicle_type}, entry={self.entry}, exit={self.exit}, priority={self.priority})"
