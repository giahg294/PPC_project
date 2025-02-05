import multiprocessing as mp
import random
import time

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
OPPOSITE_DIR = {
    N: S, S: N,
    E: W, W: E
}

class TrafficLight:
    def __init__(self):
        self.light_states = mp.Array('i', [LIGHT_GREEN, LIGHT_GREEN, LIGHT_RED, LIGHT_RED])  # N, S, E, W
        self.emergency_mode = mp.Value('b', False)
        self.emergency_direction = mp.Value('i', -1)  # 方向索引
        self.emergency_count = mp.Value('i', 0)
        self.lock = mp.Lock()

    def set_normal_state(self, ns_green, we_green):
        with self.lock:
            self.light_states[DIR_INDEX[N]] = ns_green
            self.light_states[DIR_INDEX[S]] = ns_green
            self.light_states[DIR_INDEX[E]] = we_green
            self.light_states[DIR_INDEX[W]] = we_green
            self.emergency_mode.value = False
            self.emergency_direction.value = -1
        print(f"Normal state: {N}和{S} {'绿' if ns_green else '红'}灯, {E}和{W} {'绿' if we_green else '红'}灯")

    def enter_emergency_mode(self, direction):
        with self.lock:
            if self.emergency_mode.value:
                return
            dir_index = DIR_INDEX[direction]
            for i in range(4):
                self.light_states[i] = LIGHT_RED
            self.light_states[dir_index] = LIGHT_GREEN
            self.emergency_mode.value = True
            self.emergency_direction.value = dir_index
            self.emergency_count.value += 1
        print(f"\n!!! 紧急模式激活: {direction}方向绿灯，其他方向红灯 !!!")

    def exit_emergency_mode(self):
        with self.lock:
            if self.emergency_count.value > 0:
                return
            self.emergency_mode.value = False
            self.set_normal_state(LIGHT_GREEN, LIGHT_RED)
        print("\n!!! 紧急模式解除，恢复正常运行 !!!")

    def get_light_state(self, direction):
        with self.lock:
            return self.light_states[DIR_INDEX[direction]]

global_car_id = mp.Value('i', 0)

def generate_license_plate():
    with global_car_id.get_lock():
        global_car_id.value += 1
        return f"CAR-{global_car_id.value:04d}"

def vehicle_priority(entry, exit):
    dir_map = {
        N: {S: 0, E: 1, W: 2},
        S: {N: 0, W: 1, E: 2},
        E: {W: 0, S: 1, N: 2},
        W: {E: 0, N: 1, S: 2}
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
        
        section_queues[entry].append(vehicle)
        print(f"\n--- 新车 {vehicle['license_plate']} 进入 {entry} 方向 ---")
        print(f"| {'车牌':<10} | {'入口':<5} | {'出口':<5} | {'类型':<7} | {'优先级':<8} |")
        for v in section_queues[entry][-3:]:  # 显示最近3辆
            print(f"| {v['license_plate']:<10} | {v['entry']:<5} | {v['exit']:<5} | {v['type']:<7} | {v['priority']:<8} |")

def ambulance_gen(section_queues, traffic_light):
    while True:
        time.sleep(random.randint(5, 10))  # 提高救护车生成频率
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
            section_queues[entry].insert(0, vehicle)
        
        traffic_light.enter_emergency_mode(entry)
        print(f"\n--- 救护车 {vehicle['license_plate']} 进入 {entry} 方向 ---")
        print(f"!!! 所有车辆注意！{entry}方向有救护车通过，请让行 !!!")

def coordinator(traffic_light, section_queues):
    def process_direction(direction):
        processed = []
        light_state = traffic_light.get_light_state(direction)
        if light_state != LIGHT_GREEN:
            return processed
        
        for v in list(section_queues[direction]):
            can_pass = False
            opposite_dir = OPPOSITE_DIR[direction]
            
            if v['type'] == "priority":
                can_pass = True
            else:
                if v['priority'] == 0:
                    can_pass = True
                elif v['priority'] == 1:
                    no_straight = not any(p['priority'] == 0 for p in section_queues[direction])
                    no_straight_opposite = not any(p['priority'] == 0 for p in section_queues[opposite_dir])
                    can_pass = no_straight and no_straight_opposite
                elif v['priority'] == 2:
                    no_high_pri = not any(p['priority'] in [0,1] for p in section_queues[direction])
                    no_high_pri_opposite = not any(p['priority'] in [0,1] for p in section_queues[opposite_dir])
                    can_pass = no_high_pri and no_high_pri_opposite
            
            if can_pass:
                processed.append(v)
                section_queues[direction].remove(v)
                action = ["直行", "右转", "左转"][v['priority']]
                print(f"\n=== 车辆通过 [{v['license_plate']}] {v['entry']}→{v['exit']} ({action}) ===")
                
                if v['type'] == "priority":
                    with traffic_light.emergency_count.get_lock():
                        traffic_light.emergency_count.value -= 1
                        if traffic_light.emergency_count.value == 0:
                            traffic_light.exit_emergency_mode()
        return processed

    while True:
        if traffic_light.emergency_mode.value:
            emergency_dir = DIR_INDEX_REVERSE.get(traffic_light.emergency_direction.value, None)
            if emergency_dir:
                for v in process_direction(emergency_dir):
                    time.sleep(0.5)
        else:
            for direction in DIRECTIONS:
                for v in process_direction(direction):
                    time.sleep(0.5)
        time.sleep(1)

def light_controller(traffic_light):
    while True:
        with traffic_light.lock:
            if traffic_light.emergency_mode.value:
                time.sleep(1)
                continue
        
        current_ns = traffic_light.light_states[DIR_INDEX[N]]
        new_ns = LIGHT_RED if current_ns == LIGHT_GREEN else LIGHT_GREEN
        traffic_light.set_normal_state(new_ns, LIGHT_RED if new_ns == LIGHT_GREEN else LIGHT_GREEN)
        print(f"红绿灯切换：{N}和{S} {'绿' if new_ns else '红'}灯, {E}和{W} {'绿' if new_ns == LIGHT_RED else '红'}灯")
        time.sleep(UPDATE_INTERVAL)

def main():
    manager = mp.Manager()
    section_queues = {d: manager.list() for d in DIRECTIONS}

    traffic_light = TrafficLight()

    processes = [
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