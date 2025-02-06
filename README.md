# Simulation de Trafic ： At the crossroads

## Description
Ce programme simule le contrôle du trafic à un carrefour avec feux de signalisation, véhicules normaux et véhicules prioritaires (ambulances). Il utilise des processus parallèles et divers mécanismes de communication interprocessus pour gérer les feux, les véhicules et les priorités.

## Installation et Exécution
### Prérequis :
- Python 3.x
- Modules requis : `multiprocessing`, `socket`, `time`, `random`, `sys`, `os`, `signal`

### Lancer la simulation :
1. Assurez-vous que Python est installé.
2. Exécutez la commande suivante dans le terminal Linux:
   ```sh
   python3 ppc_projet.py
3. La simulation affiche en temps réel l’état des feux et des véhicules.

### Arrêt du programme :
Utilisez CTRL + C pour interrompre la simulation proprement.

### Fonctionnalités principales :

#### • normal_traffic_gen : processus de génération de trafic normal. Pour chaque véhicule généré, il choisit des sections de route source et destination aléatoirement.
#### • ambulance_gen : processus de génération de trafic prioritaire (des ambulances). Pour chaque véhicule généré, il choisit des sections de route source et destination aléatoirement.
#### • coordinator : permet à tous les véhicules (prioritaires ou non) de passer en fonction du code de la route et de l'état des feux de circulation.
#### • light_controller :  processus de gestion des feux de signalisation.
#### • display_server : permet à l'opérateur d'observer la simulation en temps réel.
#### • termination_handler : gestion de la terminaison du programme.


