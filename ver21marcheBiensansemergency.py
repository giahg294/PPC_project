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
        if ns == LIGHT_GREEN:
            print("南北方向信号灯变绿。东西方向信号灯变红。    North——South ok .", flush=True)
        else:
            print("东西方向信号灯变绿。南北方向信号灯变红。    East——West ok .", flush=True)

    def get_state(self):
        return self.light_state[0], self.light_state[1]

def vehicle_priority(entry, exit):
    dir_map = {
        N: {S: 0, E: 1, W: 2},
        S: {N: 0, W: 1, E: 2},
        E: {W: 0, S: 1, N: 2},
        W: {E: 0, N: 1, S: 2}
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
    # 定义一个帮助函数，处理给定方向的车辆，基于当前信号灯状态判断是否能通过
    def process_direction(direction, light_state):
        processed = []  # 用于存储已通过路口的车辆
        
        # 遍历当前方向队列中的所有车辆
        for v in section_queues[direction][:]:
            # 判断车辆是否能通过，取决于车辆的优先级和当前信号灯状态
            # 先让直行
            # 两边直行都没车了，右转
            # 两边直行都没车了，两边也没右转了，左转
            if (v['priority'] == 0 and light_state) or \
               (v['priority'] == 1 and light_state and not any(p['priority'] == 0 for p in section_queues[direction]) and not any(p['priority'] == 0 for p in section_queues[OPPOSITE_DIR[direction]])) or \
               (v['priority'] == 2 and light_state and not any(p['priority'] == 0 for p in section_queues[direction]) and not any(p['priority'] == 1 for p in section_queues[direction]) and not any(p['priority'] == 0 for p in section_queues[OPPOSITE_DIR[direction]]) and not any(p['priority'] == 1 for p in section_queues[OPPOSITE_DIR[direction]])):
                
                # 如果满足通过条件，车辆可以通过
                print(f"\n=== [PASS] {v['license_plate']} {v['entry']} -> {v['exit']} ({['Straight','Right','Left'][v['priority']]}) ===")
                print(f"{v['license_plate']} 车已经过路口，从 {v['entry']} 方向驶入 {v['exit']} 方向")
                
                # 将该车辆添加到已处理的列表
                processed.append(v)
                
                # 从当前方向的队列中移除该车辆
                section_queues[direction].remove(v)
        
        # 返回已处理的车辆列表
        return processed

    # 开启一个无限循环，持续检测交通灯状态并处理车辆
    while True:
        # 获取当前交通信号灯的状态（南北方向和东西方向）
        ns, we = traffic_light.get_state()
        
        # 如果南北方向信号灯是绿灯，处理北方向的车辆
        for v in process_direction(N, ns == LIGHT_GREEN):
            time.sleep(0.5)
        
        # 如果南北方向信号灯是绿灯，处理南方向的车辆
        for v in process_direction(S, ns == LIGHT_GREEN):
            time.sleep(0.5)
        
        # 如果东西方向信号灯是绿灯，处理东方向的车辆
        for v in process_direction(E, we == LIGHT_GREEN):
            time.sleep(0.5)
        
        # 如果东西方向信号灯是绿灯，处理西方向的车辆
        for v in process_direction(W, we == LIGHT_GREEN):
            time.sleep(0.5)
        
        # 每次循环结束后暂停1秒钟
        time.sleep(1)

def light_controller(traffic_light):
    while True:
        traffic_light.set_state(LIGHT_GREEN, LIGHT_RED)
        time.sleep(UPDATE_INTERVAL)
        traffic_light.set_state(LIGHT_RED, LIGHT_GREEN)
        time.sleep(UPDATE_INTERVAL)

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
        mp.Process(target=light_controller, args=(traffic_light,)),  # 添加信号灯控制进程
        mp.Process(target=normal_traffic_gen, args=(section_queues,)),
        mp.Process(target=coordinator, args=(traffic_light, section_queues))
    ]

    for p in processes:
        p.start()
    for p in processes:
        p.join()

if __name__ == "__main__":
    main()
