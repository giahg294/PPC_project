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
OPPOSITE_DIR = {N: S, S: N, E: W, W: E}

# 共享变量
traffic_light = None

class TrafficLight:
    def __init__(self):
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
            state = "绿" if self.light_states[DIR_INDEX[d]] == LIGHT_GREEN else "红"
            states.append(f"{d}:{state}")
        print(f"当前灯态：{', '.join(states)}")

    def set_normal_state(self, ns_green, we_green):
        with self.lock:
            self.light_states[DIR_INDEX[N]] = ns_green
            self.light_states[DIR_INDEX[S]] = ns_green
            self.light_states[DIR_INDEX[E]] = we_green
            self.light_states[DIR_INDEX[W]] = we_green
            self.emergency_mode.value = False
            self.emergency_direction.value = -1
            print(f"🚦 信号灯切换：{N}/{S} {'绿' if ns_green else '红'}，{E}/{W} {'绿' if we_green else '红'}")

    def enter_emergency_mode(self, direction):
        with self.lock:
            for i in range(4):
                self.light_states[i] = LIGHT_RED
            self.light_states[DIR_INDEX[direction]] = LIGHT_GREEN
            self.emergency_mode.value = True
            self.emergency_direction.value = DIR_INDEX[direction]
            self.emergency_count.value += 1
            print(f"\n🚨 紧急模式：{direction} 方向绿灯，其他方向红灯！")
            self.print_light_states()

    def exit_emergency_mode(self):
        with self.lock:
            if self.emergency_count.value > 0:
                return
            self.emergency_mode.value = False
            self.set_normal_state(LIGHT_GREEN, LIGHT_RED)
            print("\n✅ 紧急模式解除，恢复正常运行！")
            self.print_light_states()

# 车辆编号生成
global_car_id = mp.Value('i', 0)

def generate_license_plate():
    with global_car_id.get_lock():
        global_car_id.value += 1
        return f"CAR-{global_car_id.value:04d}"

# 车辆生成
def normal_traffic_gen(section_queues):
    while True:
        time.sleep(random.randint(1, 3))
        entry, exit = random.sample(DIRECTIONS, 2)
        vehicle = {"license_plate": generate_license_plate(), "type": "normal", "entry": entry, "exit": exit}
        section_queues[entry].put(vehicle)
        print(f"🚗 普通车辆 {vehicle['license_plate']} 进入 {entry} → {exit}")

def ambulance_gen(section_queues):
    while True:
        time.sleep(random.randint(5, 10))
        entry, exit = random.sample(DIRECTIONS, 2)
        vehicle = {"license_plate": generate_license_plate(), "type": "priority", "entry": entry, "exit": exit}
        section_queues[entry].put(vehicle)
        print(f"🚑 紧急车辆 {vehicle['license_plate']} 进入 {entry} → {exit}")
        os.kill(os.getppid(), signal.SIGUSR1)  # 发送信号通知 `light_controller`

# 信号处理
def handle_priority_signal(signum, frame):
    print("🚨 收到紧急信号，信号灯调整！")
    traffic_light.enter_emergency_mode(DIRECTIONS[0])  # 这里可以优化，让实际方向可变

def coordinator(traffic_light, section_queues):
    def process_direction(direction):
        if traffic_light.get_light_state(direction) != LIGHT_GREEN:
            return
        while not section_queues[direction].empty():
            vehicle = section_queues[direction].get()
            if vehicle['type'] == "priority":
                print(f"🚑 紧急车辆通过：{vehicle['license_plate']} {vehicle['entry']} → {vehicle['exit']}")
                with traffic_light.emergency_count.get_lock():
                    traffic_light.emergency_count.value -= 1
                    if traffic_light.emergency_count.value == 0:
                        traffic_light.exit_emergency_mode()
            else:
                print(f"🚗 普通车辆通过：{vehicle['license_plate']} {vehicle['entry']} → {vehicle['exit']}")
    
    while True:
        for direction in DIRECTIONS:
            process_direction(direction)
        time.sleep(1)

def light_controller(traffic_light):
    signal.signal(signal.SIGUSR1, handle_priority_signal)
    while True:
        if not traffic_light.emergency_mode.value:
            current_ns = traffic_light.light_states[DIR_INDEX[N]]
            new_ns = LIGHT_RED if current_ns == LIGHT_GREEN else LIGHT_GREEN
            traffic_light.set_normal_state(new_ns, LIGHT_RED if new_ns == LIGHT_GREEN else LIGHT_GREEN)
        time.sleep(UPDATE_INTERVAL)

def display_process():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("localhost", 9999))
    server_socket.listen(1)
    conn, _ = server_socket.accept()
    while True:
        states = ",".join(str(traffic_light.light_states[i]) for i in range(4))
        conn.sendall(states.encode())
        time.sleep(1)

def main():
    global traffic_light
    manager = mp.Manager()
    section_queues = {d: mp.Queue() for d in DIRECTIONS}
    traffic_light = TrafficLight()

    processes = [
        mp.Process(target=light_controller, args=(traffic_light,)),
        mp.Process(target=normal_traffic_gen, args=(section_queues,)),
        mp.Process(target=coordinator, args=(traffic_light, section_queues)),
        mp.Process(target=ambulance_gen, args=(section_queues,)),
        mp.Process(target=display_process)
    ]

    for p in processes:
        p.start()
    for p in processes:
        p.join()

if __name__ == "__main__":
    main()
