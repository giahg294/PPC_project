# 只修改shared memory
import multiprocessing as mp
import random
import time
import os
import signal
import socket

# 方向常量
N = "North"
S = "South"
W = "West"
E = "East"
DIRECTIONS = [N, S, W, E]
LIGHT_GREEN = 1
LIGHT_RED = 0
UPDATE_INTERVAL = 8
DIR_INDEX = {N: 0, S: 1, E: 2, W: 3}
DIR_INDEX_REVERSE = {v: k for k, v in DIR_INDEX.items()}

# 方向映射表
OPPOSITE_DIR = {
    N: S, S: N,
    E: W, W: E
}

class TrafficLight:
    def __init__(self):
        # 共享内存存储灯态
        self.light_states = mp.Array('i', [LIGHT_GREEN, LIGHT_GREEN, LIGHT_RED, LIGHT_RED])
        self.emergency_mode = mp.Value('b', False)
        self.emergency_direction = mp.Value('i', -1)
        self.emergency_count = mp.Value('i', 0)
        self.lock = mp.Lock()
        self.emergency_dir = mp.Value('i', -1)
        signal.signal(signal.SIGUSR1, self.handle_emergency)

    def handle_emergency(self, signum, frame):
        with self.lock:
            if self.emergency_dir.value != -1:
                self.enter_emergency_mode(DIR_INDEX_REVERSE[self.emergency_dir.value])

    def get_light_state(self, direction):
        with self.lock:
            return self.light_states[DIR_INDEX[direction]]

    def set_normal_state(self, ns_green, we_green):
        with self.lock:
            self.light_states[DIR_INDEX[N]] = ns_green
            self.light_states[DIR_INDEX[S]] = ns_green
            self.light_states[DIR_INDEX[E]] = we_green
            self.light_states[DIR_INDEX[W]] = we_green
            self.emergency_mode.value = False
            self.emergency_direction.value = -1

    def enter_emergency_mode(self, direction):
        with self.lock:
            dir_index = DIR_INDEX[direction]
            for i in range(4):
                self.light_states[i] = LIGHT_RED
            self.light_states[dir_index] = LIGHT_GREEN
            self.emergency_mode.value = True
            self.emergency_direction.value = dir_index
            self.emergency_count.value += 1

    def exit_emergency_mode(self):
        with self.lock:
            self.emergency_mode.value = False
            self.set_normal_state(LIGHT_GREEN, LIGHT_RED)

global_car_id = mp.Value('i', 0)

def generate_license_plate():
    with global_car_id.get_lock():
        global_car_id.value += 1
        return f"CAR-{global_car_id.value:04d}"

def vehicle_priority(entry, exit):
    dir_map = {
        N: {S: 1, W: 2, E: 3},
        S: {N: 1, E: 2, W: 3},
        E: {W: 1, N: 2, S: 3},
        W: {E: 1, S: 2, N: 3}
    }
    return dir_map[entry][exit]

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
        section_queues[entry].put(vehicle)

def ambulance_gen(section_queues, traffic_light):
    while True:
        time.sleep(random.randint(11, 15))
        entry = random.choice(DIRECTIONS)
        exit = random.choice([d for d in DIRECTIONS if d != entry])

        vehicle = {
            "license_plate": generate_license_plate(),
            "type": "priority",
            "entry": entry,
            "exit": exit,
            "priority": vehicle_priority(entry, exit)
        }

        with traffic_light.lock:
            section_queues[entry].put(vehicle)
            traffic_light.emergency_dir.value = DIR_INDEX[entry]
        os.kill(os.getpid(), signal.SIGUSR1)

def coordinator(traffic_light, section_queues):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('localhost', 12345))

    def process_queue(q, direction):
        temp = []
        while not q.empty():
            temp.append(q.get())
        return temp

    def process_direction(direction):
        current_queue = section_queues[direction]
        opposite_dir = OPPOSITE_DIR[direction]
        opposite_queue = section_queues[opposite_dir]

        vehicles = process_queue(current_queue, direction)
        opposite_vehicles = process_queue(opposite_queue, opposite_dir)

        passed = []
        for v in vehicles:
            can_pass = False
            if v["type"] == "priority":
                can_pass = True
            else:
                if v["priority"] == 1:
                    can_pass = True
                elif v["priority"] == 2:
                    can_pass = not any(p["priority"] == 1 for p in vehicles + opposite_vehicles)
                elif v["priority"] == 3:
                    can_pass = not any(p["priority"] in [1,2] for p in vehicles + opposite_vehicles)

            if can_pass:
                action = ["直行", "右转", "左转"][v["priority"]-1]
                msg = f"{v['license_plate']}|{v['entry']}→{v['exit']}|{action}"
                sock.send(msg.encode())
                passed.append(v)
                if v["type"] == "priority":
                    with traffic_light.emergency_count.get_lock():
                        traffic_light.emergency_count.value -= 1
                        if traffic_light.emergency_count.value <= 0:
                            traffic_light.exit_emergency_mode()
            else:
                current_queue.put(v)

        for p in opposite_vehicles:
            opposite_queue.put(p)

        return passed

    while True:
        if traffic_light.emergency_mode.value:
            emergency_dir = DIR_INDEX_REVERSE.get(traffic_light.emergency_direction.value)
            if emergency_dir:
                process_direction(emergency_dir)
        else:
            for direction in DIRECTIONS:
                process_direction(direction)
        time.sleep(1)

def light_controller(traffic_light):
    while True:
        with traffic_light.lock:
            if traffic_light.emergency_mode.value:
                time.sleep(0.1)
                continue

        current_ns = traffic_light.light_states[DIR_INDEX[N]]
        new_ns = LIGHT_RED if current_ns == LIGHT_GREEN else LIGHT_GREEN
        traffic_light.set_normal_state(new_ns, LIGHT_RED if new_ns == LIGHT_GREEN else LIGHT_GREEN)
        time.sleep(UPDATE_INTERVAL)

def display_process():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('localhost', 12345))
    server.listen(1)
    conn, _ = server.accept()
    while True:
        data = conn.recv(1024)
        if data:
            print(f"[DISPLAY] {data.decode()}")

def main():
    section_queues = {d: mp.Queue() for d in DIRECTIONS}
    traffic_light = TrafficLight()

    processes = [
        mp.Process(target=display_process),
        mp.Process(target=light_controller, args=(traffic_light,)),
        mp.Process(target=normal_traffic_gen, args=(section_queues,)),
        mp.Process(target=coordinator, args=(traffic_light, section_queues)),
        mp.Process(target=ambulance_gen, args=(section_queues, traffic_light))
    ]

    for p in processes:
        p.start()
    for p in processes:
        p.join()

if __name__ == "__main__":
    main()