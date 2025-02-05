#deepseek
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

def normal_traffic_gen(section_queues):
    while True:
        time.sleep(random.randint(1, 3))
        entry = random.choice(DIRECTIONS)
        exit = random.choice([d for d in DIRECTIONS if d != entry])
        
        vehicle = {
            "type": "normal",
            "entry": entry,
            "exit": exit,
            "priority": vehicle_priority(entry, exit)
        }
        
        section_queues[entry].append(vehicle)
        print(f"\n--- !! New Vehicle @ {entry} !! ---")
        print(f"| {'From':<5} | {'To':<5} | {'Type':<7} | {'Priority':<8} |")
        for v in section_queues[entry]:
            print(f"| {v['entry']:<5} | {v['exit']:<5} | {v['type']:<7} | {v['priority']:<8} |")

def priority_traffic_gen(light_pid, section_queues, emergency_direction):
    while True:
        time.sleep(random.randint(5, 10))
        entry = random.choice(DIRECTIONS)
        exit = random.choice([d for d in DIRECTIONS if d != entry])
        
        vehicle = {
            "type": "priority",
            "entry": entry,
            "exit": exit,
            "priority": 0
        }
        
        section_queues[entry].append(vehicle)
        with emergency_direction.get_lock():
            emergency_direction.value = entry.encode()
        
        print(f"\n--- !! EMERGENCY Vehicle @ {entry} !! ---")
        print(f"| {'From':<5} | {'To':<5} | {'Type':<7} | {'Priority':<8} |")
        for v in section_queues[entry]:
            print(f"| {v['entry']:<5} | {v['exit']:<5} | {v['type']:<7} | {v['priority']:<8} |")
        
        os.kill(light_pid, signal.SIGUSR1)

def light_controller(traffic_light, emergency_direction):
    def handler(signum, frame):
        with emergency_direction.get_lock():
            entry = emergency_direction.value.decode()
        print("\n=== EMERGENCY LIGHT CHANGE ===")
        
        if entry in (N, S):
            traffic_light.set_state(LIGHT_GREEN, LIGHT_RED)
        else:
            traffic_light.set_state(LIGHT_RED, LIGHT_GREEN)
        
        time.sleep(3)
        traffic_light.set_state(LIGHT_GREEN, LIGHT_RED)  # 返回默认状态
    
    signal.signal(signal.SIGUSR1, handler)
    
    while True:
        traffic_light.set_state(LIGHT_GREEN, LIGHT_RED)
        print("\n=== NS GREEN / WE RED ===")
        time.sleep(UPDATE_INTERVAL)
        
        traffic_light.set_state(LIGHT_RED, LIGHT_GREEN)
        print("\n=== WE GREEN / NS RED ===")
        time.sleep(UPDATE_INTERVAL)

def coordinator(traffic_light, section_queues):
    def process_direction(direction, light_state):
        processed = []
        for v in section_ques[direction][:]:
            if (v['priority'] == 0 and light_state) or \
               (v['priority'] == 1 and light_state and not any(p['priority']==0 for p in section_ques[direction])) or \
               (v['priority'] == 2 and light_state and not any(p['priority']==0 for p in section_ques[OPPOSITE_DIR[direction]])):
                
                print(f"\n=== [PASS] {v['entry']}->{v['exit']} ({['Straight','Right','Left'][v['priority']]}) ===")
                processed.append(v)
                section_ques[direction].remove(v)
        return processed

    while True:
        ns, we = traffic_light.get_state()
        
        # Process NS方向
        for v in process_direction(N, ns == LIGHT_GREEN):
            time.sleep(0.5)
        for v in process_direction(S, ns == LIGHT_GREEN):
            time.sleep(0.5)
        
        # Process WE方向
        for v in process_direction(E, we == LIGHT_GREEN):
            time.sleep(0.5)
        for v in process_direction(W, we == LIGHT_GREEN):
            time.sleep(0.5)
        
        time.sleep(1)

def main():
    manager = mp.Manager()
    section_ques = {
        N: manager.list(),
        S: manager.list(),
        W: manager.list(),
        E: manager.list()
    }
    emergency_direction = mp.Array('c', 10)  # 存储方向字符串
    
    traffic_light = TrafficLight()
    
    light_process = mp.Process(target=light_controller, args=(traffic_light, emergency_direction))
    light_process.start()
    
    processes = [
        mp.Process(target=normal_traffic_gen, args=(section_ques,)),
        mp.Process(target=priority_traffic_gen, args=(light_process.pid, section_ques, emergency_direction)),
        mp.Process(target=coordinator, args=(traffic_light, section_ques))
    ]
    
    for p in processes:
        p.start()
    for p in processes:
        p.join()

if __name__ == "__main__":
    main()