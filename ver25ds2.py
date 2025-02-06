#deepseek 深度思考

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
        self.lock.acquire()  # 🔄 替换 with self.lock:
        try:
            self.light_states[DIR_INDEX[N]] = ns_green
            self.light_states[DIR_INDEX[S]] = ns_green
            self.light_states[DIR_INDEX[E]] = we_green
            self.light_states[DIR_INDEX[W]] = we_green
            self.emergency_mode.value = False
            self.emergency_direction.value = -1
            print(f"红绿灯变化 - {N}和{S}方向{'绿' if ns_green else '红'}灯，{E}和{W}方向{'绿' if we_green else '红'}灯")
        finally:
            self.lock.release()  # 🔄 释放锁

    def enter_emergency_mode(self, direction):
        self.lock.acquire()  # 🔄 替换 with self.lock:
        try:
            dir_index = DIR_INDEX[direction]
            for i in range(4):
                self.light_states[i] = LIGHT_RED
            self.light_states[dir_index] = LIGHT_GREEN
            self.emergency_mode.value = True
            self.emergency_direction.value = dir_index
            self.emergency_count.value += 1
            print(f"\n!!! 🚑 紧急变灯中---")
            self.print_light_states()
        finally:
            self.lock.release()  # 🔄 释放锁

    def exit_emergency_mode(self):
        print("哈哈哈哈哈哈哈哈哈你进入exit emergency mode啦")
        self.lock.acquire()  # 🔄 替换 with self.lock:
        try:
            print("哈哈哈哈哈哈哈哈哈你进入self lock")
            print(self.emergency_count.value)
            if self.emergency_count.value > 0:
                return
            self.emergency_mode.value = False
            self.set_normal_state(LIGHT_GREEN, LIGHT_RED)
            print("\n!!! 紧急模式解除，恢复正常运行 !!!")
            self.print_light_states()
        finally:
            self.lock.release()  # 🔄 释放锁

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
    # 生成普通车辆，并加入到对应方向的车队中 
    while True:
        time.sleep(random.randint(1, 3))  # 随机等待 1-3 秒
        entry = random.choice(DIRECTIONS)  # 随机选择进入方向
        exit = random.choice([d for d in DIRECTIONS if d != entry])  # 确保出口与入口不同
        
        # 生成新车辆信息
        vehicle = {
            "license_plate": generate_license_plate(),
            "type": "normal",
            "entry": entry,
            "exit": exit,
            "priority": vehicle_priority(entry, exit)
        }
        
        # 加入到对应方向的车队中
        section_queues[entry].append(vehicle)
        
        # 打印车辆信息
        print(f"\n--- 新车 {vehicle['license_plate']} 进入 {entry} 方向 ---")
        print(f"| {'车牌':<8} | {'入口':<3} | {'出口':<3} | {'类型':<5} | {'优先级':<5} |")
        for v in section_queues[entry][-5:]:  # 显示最近5辆车
            print(f"| {v['license_plate']:<10} | {v['entry']:<5} | {v['exit']:<5} | {v['type']:<7} | {v['priority']:<8} |")

def ambulance_gen(section_queues, traffic_light):
    while True:
        time.sleep(random.randint(2, 4))
        entry = random.choice(DIRECTIONS)
        exit = random.choice([d for d in DIRECTIONS if d != entry])

        vehicle = {
            "license_plate": generate_license_plate(),
            "type": "pripri",
            "entry": entry,
            "exit": exit,
            "priority": 0
        }

        traffic_light.lock.acquire()  # 🔄 替换 with traffic_light.lock:
        try:
            section_queues[entry].insert(0, vehicle)
            print("卧槽！！！！！！！！！！！！！！！！！！！你进锁了！！！！！！！")
        finally:
            traffic_light.lock.release()  # 🔄 释放锁

        print(f"\n--- !!! 所有车辆注意！救护车 {vehicle['license_plate']} 进入 {entry} 方向 即将驶向 {exit} 方向，其余车避让！！！ ---")
        traffic_light.enter_emergency_mode(entry)
def coordinator(traffic_light, section_queues):
    def process_direction(direction):
        processed = []
        light_state = traffic_light.get_light_state(direction)
        if light_state != LIGHT_GREEN:
            return processed

        for v in list(section_queues[direction]):
            can_pass = False
            opposite_dir = OPPOSITE_DIR[direction]

            if v['type'] == "pripri":
                print(f'enter 0')
                can_pass = True
                print(f"can_pass after priority 1 check: {can_pass}")
            else:
                if v['priority'] == 1:
                    print(f'enter 1')
                    can_pass = not any(p['priority'] == 0 for p in section_queues[direction])
                    print(f"can_pass after priority 1 check: {can_pass}")
                elif v['priority'] == 2:
                    print(f'enter 2')
                    no_ambu1 = not any(p['priority'] == 0 for p in section_queues[direction])
                    no_ambu1_opposite = not any(p['priority'] == 0 for p in section_queues[opposite_dir])
                    no_straight = not any(p['priority'] == 1 for p in section_queues[direction])
                    no_straight_opposite = not any(p['priority'] == 1 for p in section_queues[opposite_dir])
                    can_pass = no_ambu1 and no_ambu1_opposite and no_straight and no_straight_opposite
                    print(f"can_pass after priority 2 check: {can_pass}")
                elif v['priority'] == 3:
                    print(f'enter 3')
                    no_ambu2 = not any(p['priority'] == 0 for p in section_queues[direction])
                    no_ambu2_opposite = not any(p['priority'] == 0 for p in section_queues[opposite_dir])
                    no_higher_pri = not any(p['priority'] in [1, 2] for p in section_queues[direction])
                    no_higher_pri_opposite = not any(p['priority'] in [1, 2] for p in section_queues[opposite_dir])
                    can_pass = no_ambu2 and no_ambu2_opposite and no_higher_pri and no_higher_pri_opposite
                    print(f"can_pass after priority 3 check: {can_pass}")

            if can_pass:
                print(f'nijincanpass')
                processed.append(v)
                section_queues[direction].remove(v)
                action = ["直行", "右转", "左转"][v['priority']]

                print (v['type'])
                if v['type'] == "pripri":
                    print(f"\n=== ！！！紧急车辆已经通过 [{v['license_plate']}] {v['entry']}→{v['exit']} ({action}) ===")
                    
                    traffic_light.emergency_count.get_lock().acquire()  # 🔄 替换 with traffic_light.emergency_count.get_lock():
                    try:
                        print("呵呵呵呵你进lock.acquire() 了")
                        traffic_light.emergency_count.value -= 1
                        print(f"呵呵呵呵你emergency_count.value-=1了 ， 剩余救护车数量: {traffic_light.emergency_count.value}")

                        if traffic_light.emergency_count.value <= 0:
                            print("哈哈哈哈哈哈哈哈哈哈哈哈你进入if条件了")
                            traffic_light.exit_emergency_mode()
                        traffic_light.print_light_states()
                    finally:
                        traffic_light.emergency_count.get_lock().release()  # 🔄 释放锁

                print(f"\n=== 车辆通过 [{v['license_plate']}] {v['entry']}→{v['exit']} ({action}) ===")
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
    while True:  # 持续运行，模拟交通灯的持续控制
        with traffic_light.lock:  # 获取锁，确保在检查紧急模式时不会被其他进程干扰
            if traffic_light.emergency_mode.value:  # 检查是否处于紧急模式
                time.sleep(0.1)  # 如果是紧急模式，短暂休眠后继续检查，避免频繁占用CPU
                continue  # 跳过后续代码，直接进入下一次循环
        
        # 获取当前南北方向的交通灯状态
        current_ns = traffic_light.light_states[DIR_INDEX[N]]
        
        # 根据当前南北方向的状态，计算新的状态
        # 如果当前是绿灯，则切换为红灯；如果是红灯，则切换为绿灯
        new_ns = LIGHT_RED if current_ns == LIGHT_GREEN else LIGHT_GREEN
        
        # 调用 TrafficLight 类的方法，设置新的交通灯状态
        # 如果南北方向是绿灯，则东西方向是红灯，反之亦然
        traffic_light.set_normal_state(new_ns, LIGHT_RED if new_ns == LIGHT_GREEN else LIGHT_GREEN)
        
        # 按照设定的时间间隔等待，模拟交通灯的切换周期
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
