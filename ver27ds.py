# ver25ds3marcheBienWithoutRules_final.py
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
VEHICLE_TYPES = ["normal", "priority"]
LIGHT_GREEN = 1
LIGHT_RED = 0
UPDATE_INTERVAL = 8
DIR_INDEX = {N: 0, S: 1, E: 2, W: 3}
DIR_INDEX_REVERSE = {v: k for k, v in DIR_INDEX.items()}

# 方向映射表
OPPOSITE_DIR = {N: S, S: N, E: W, W: E}

class Vehicle:
    def __init__(self, plate, v_type, entry, exit, priority):
        self.license_plate = plate
        self.type = v_type
        self.entry = entry
        self.exit = exit
        self.priority = priority

    def __repr__(self):
        return f"{self.license_plate} ({self.type})"

class TrafficLight:
    def __init__(self):
        self.light_states = mp.Array('i', [LIGHT_GREEN, LIGHT_GREEN, LIGHT_RED, LIGHT_RED])
        self.emergency_mode = mp.Value('b', False)
        self.emergency_direction = mp.Value('i', -1)
        self.emergency_count = mp.Value('i', 0)
        self.lock = mp.Lock()
        self.emergency_dir = mp.Value('i', -1)
        signal.signal(signal.SIGUSR1, self.handle_emergency_signal)

    def handle_emergency_signal(self, signum, frame):
        with self.lock:
            if self.emergency_dir.value != -1:
                self.enter_emergency_mode(DIR_INDEX_REVERSE[self.emergency_dir.value])

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
        self.light_states[DIR_INDEX[N]] = ns_green
        self.light_states[DIR_INDEX[S]] = ns_green
        self.light_states[DIR_INDEX[E]] = we_green
        self.light_states[DIR_INDEX[W]] = we_green
        self.emergency_mode.value = False
        self.emergency_direction.value = -1
        print(f"红绿灯变化 - {N}和{S}方向{'绿' if ns_green else '红'}灯，{E}和{W}方向{'绿' if we_green else '红'}灯")

    def enter_emergency_mode(self, direction):
        with self.lock:
            dir_index = DIR_INDEX[direction]
            for i in range(4):
                self.light_states[i] = LIGHT_RED
            self.light_states[dir_index] = LIGHT_GREEN
            self.emergency_mode.value = True
            self.emergency_direction.value = dir_index
            self.emergency_count.value += 1
            self.print_light_states()

    def exit_emergency_mode(self):
        with self.lock:
            self.emergency_mode.value = False
            self.set_normal_state(LIGHT_GREEN, LIGHT_RED)
            print("紧急模式解除，恢复正常运行")

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
        vehicle = Vehicle(
            generate_license_plate(), "normal", entry, exit, 
            vehicle_priority(entry, exit)
        )
        section_queues[entry].put(vehicle)
        print(f"新车 {vehicle.license_plate} 进入 {entry} 方向")

def ambulance_gen(section_queues, traffic_light):
    while True:
        time.sleep(random.randint(11, 15))
        entry = random.choice(DIRECTIONS)
        exit = random.choice([d for d in DIRECTIONS if d != entry])
        vehicle = Vehicle(
            generate_license_plate(), "pripri", entry, exit,
            vehicle_priority(entry, exit)
        )
        with traffic_light.lock:
            section_queues[entry].put(vehicle)
            traffic_light.emergency_dir.value = DIR_INDEX[entry]
        os.kill(os.getpid(), signal.SIGUSR1)
        print(f"救护车 {vehicle.license_plate} 触发紧急模式")





def coordinator(traffic_light, section_queues):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # 新增连接重试逻辑
    connected = False
    while not connected:
        try:
            sock.connect(('localhost', 12345))
            connected = True
        except ConnectionRefusedError:
            print("等待显示进程启动...")
            time.sleep(0.5)

    def process_direction(direction):
        temp_list = []
        while not section_queues[direction].empty():
            temp_list.append(section_queues[direction].get())
        
        processed = []
        for v in temp_list:
            can_pass = False
            opposite_dir = OPPOSITE_DIR[direction]

            # 获取对向车道所有车辆（临时取出）
            opposite_temp = []
            while not section_queues[opposite_dir].empty():
                opposite_temp.append(section_queues[opposite_dir].get())

            if v.type == "pripri":
                can_pass = True
            else:
                if v.priority == 1:
                    can_pass = True
                elif v.priority == 2:
                    no_straight = not any(p.priority == 1 for p in temp_list)
                    no_straight_opposite = not any(p.priority == 1 for p in section_queues[opposite_dir].queue)
                    can_pass = no_straight and no_straight_opposite
                elif v.priority == 3:
                    no_higher = not any(p.priority in [1,2] for p in temp_list)
                    no_higher_opposite = not any(p.priority in [1,2] for p in section_queues[opposite_dir].queue)
                    can_pass = no_higher and no_higher_opposite
            # 将对向车辆放回队列
            for p in opposite_temp:
                section_queues[opposite_dir].put(p)
            if can_pass:
                action = ["直行", "右转", "左转"][v.priority-1]
                msg = f"{v.license_plate} {v.entry}→{v.exit} ({action})"
                sock.send(msg.encode())
                processed.append(v)
                if v.type == "pripri":
                    with traffic_light.emergency_count.get_lock():
                        traffic_light.emergency_count.value -= 1
                        if traffic_light.emergency_count.value <= 0:
                            traffic_light.exit_emergency_mode()
            else:
                section_queues[direction].put(v)
        return processed

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
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # 新增
    server.bind(('localhost', 12345))
    server.listen(1)
    print("[DISPLAY] 服务器已启动，等待连接...")
    conn, _ = server.accept()
    print("[DISPLAY] 已连接协调器")
    # 后续逻辑保持不变
    while True:
        data = conn.recv(1024)
        if data:
            print(f"[DISPLAY] {data.decode()}")


def main():
    section_queues = {d: mp.Queue() for d in DIRECTIONS}
    traffic_light = TrafficLight()

    processes = [
        mp.Process(target=display_process),  # 第一个启动显示进程
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