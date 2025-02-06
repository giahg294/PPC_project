import multiprocessing as mp
import random
import time
import os
import signal

# 方向常量
N = "North"
S = "South"
W = "West"
E = "East"
DIRECTIONS = [N, S, W, E]
VEHICLE_TYPES = ["normal", "priority"]
LIGHT_GREEN = 1
LIGHT_RED = 0
UPDATE_INTERVAL = 5

# 方向映射表
OPPOSITE_DIR = {
    N: S, S: N,
    E: W, W: E
}

class TrafficLight:
    def __init__(self):
        self.light_state = mp.Array('i', [LIGHT_GREEN, LIGHT_RED])  # NS, WE

    def set_state(self, ns, we):
        self.light_state[0] = ns
        self.light_state[1] = we

    def get_state(self):
        return self.light_state[0], self.light_state[1]

def vehicle_priority(entry, exit):
    dir_map = {
        N: {S: 0, E: 1, W: 2},
        S: {N: 0, W: 1, E: 2},
        E: {W: 0, N: 1, S: 2},
        W: {E: 0, S: 1, N: 2}
    }
    return dir_map[entry][exit]

global_car_id = mp.Value('i', 0)  # 车牌编号

def generate_license_plate():
    with global_car_id.get_lock():
        global_car_id.value += 1
        return f"CAR-{global_car_id.value:04d}"

def normal_traffic_gen(section_queues):
    while True:
        time.sleep(random.randint(1, 3))
        entry = random.choice(DIRECTIONS)
        exit = random.choice([d for d in DIRECTIONS if d != entry])
        
        vehicle = {
            "license_plate": generate_license_plate(),
            "type": "normal",
            "entry": entry,
            "exit": exit,
            "priority": vehicle_priority(entry, exit)
        }
        
        section_queues[entry].append(vehicle)
        print(f"\n--- !! New Vehicle {vehicle['license_plate']} @ {entry} !! ---")
        print(f"| {'Plate':<10} | {'From':<5} | {'To':<5} | {'Type':<7} | {'Priority':<8} |")
        for v in section_queues[entry]:
            print(f"| {v['license_plate']:<10} | {v['entry']:<5} | {v['exit']:<5} | {v['type']:<7} | {v['priority']:<8} |")

def coordinator(traffic_light, section_queues):
    def process_direction(direction, light_state):
        processed = []
        for v in section_queues[direction][:]:
            if (v['priority'] == 0 and light_state) or \
               (v['priority'] == 1 and light_state and not any(p['priority']==0 for p in section_queues[direction])) or \
               (v['priority'] == 2 and light_state and not any(p['priority']==0 for p in section_queues[OPPOSITE_DIR[direction]])):
                
                print(f"\n=== [PASS] {v['license_plate']} {v['entry']} -> {v['exit']} ({['Straight','Right','Left'][v['priority']]}) ===")
                processed.append(v)
                section_queues[direction].remove(v)
        return processed

    while True:
        ns, we = traffic_light.get_state()
        
        for v in process_direction(N, ns == LIGHT_GREEN):
            time.sleep(0.5)
        for v in process_direction(S, ns == LIGHT_GREEN):
            time.sleep(0.5)
        
        for v in process_direction(E, we == LIGHT_GREEN):
            time.sleep(0.5)
        for v in process_direction(W, we == LIGHT_GREEN):
            time.sleep(0.5)
        
        time.sleep(1)

def main():
    manager = mp.Manager()
    section_queues = {
        N: manager.list(),
        S: manager.list(),
        W: manager.list(),
        E: manager.list()
    }
    
    traffic_light = TrafficLight()
    
    processes = [
        mp.Process(target=normal_traffic_gen, args=(section_queues,)),
        mp.Process(target=coordinator, args=(traffic_light, section_queues))
    ]
    
    for p in processes:
        p.start()
    for p in processes:
        p.join()

if __name__ == "__main__":
    main()
