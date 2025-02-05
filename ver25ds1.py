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
        # 使用 multiprocessing.Array 存储四个方向的信号灯状态（N, S, E, W）
        self.light_states = mp.Array('i', [LIGHT_GREEN, LIGHT_GREEN, LIGHT_RED, LIGHT_RED])  
        
        # 标记是否进入紧急模式（救护车模式）
        self.emergency_mode = mp.Value('b', False)
        
        # 记录当前进入紧急模式的方向，默认-1表示没有
        self.emergency_direction = mp.Value('i', -1)  
        
        # 记录当前救护车数量
        self.emergency_count = mp.Value('i', 0)

        # 进程锁，防止多个进程同时修改状态
        self.lock = mp.Lock()

    # 设置正常模式的信号灯状态 
    def set_normal_state(self, ns_green, we_green):
        with self.lock:
            self.light_states[DIR_INDEX[N]] = ns_green
            self.light_states[DIR_INDEX[S]] = ns_green
            self.light_states[DIR_INDEX[E]] = we_green
            self.light_states[DIR_INDEX[W]] = we_green
            # 不处于紧急模式
            self.emergency_mode.value = False
            self.emergency_direction.value = -1
        print(f"红绿灯变化 - {N}和{S}方向{'绿' if ns_green else '红'}灯，{E}和{W}方向{'绿' if we_green else '红'}灯")
     
    # 进入紧急模式，只有救护车🚑来到的方向的信号灯变绿，其余方向变红
    def enter_emergency_mode(self, direction):
       
        with self.lock:
            dir_index = DIR_INDEX[direction]
            
            # 所有方向先变红
            for i in range(4):
                self.light_states[i] = LIGHT_RED
            
            # 只有紧急车辆方向的灯变绿
            self.light_states[dir_index] = LIGHT_GREEN
            
            # 标记进入紧急模式
            self.emergency_mode.value = True
            self.emergency_direction.value = dir_index
            self.emergency_count.value += 1
        
        print(f"\n!!! 🚑 紧急变灯中---")
        self.print_light_states()



    # 退出紧急模式，恢复正常信号灯状态
    def exit_emergency_mode(self):
        print("哈哈哈哈哈哈哈哈哈你进入exit emergency mode啦")
        with self.lock:
            print("哈哈哈哈哈哈哈哈哈你进入self lock")
            if self.emergency_count.value > 0:
                return  # 如果还有救护车，保持紧急状态
            
            self.emergency_mode.value = False
            self.set_normal_state(LIGHT_GREEN, LIGHT_RED)  # 复原正常信号灯模式
        
        print("\n!!! 紧急模式解除，恢复正常运行 !!!")
        self.print_light_states()
   
    # 获取指定方向的信号灯状态 
    def get_light_state(self, direction):
        with self.lock:
            return self.light_states[DIR_INDEX[direction]]
    # 打印当前灯态
    def print_light_states(self):
        states = []
        for d in DIRECTIONS:
            state = "绿" if self.light_states[DIR_INDEX[d]] == LIGHT_GREEN else "红"
            states.append(f"{d}:{state}")
        print(f"当前灯态：{', '.join(states)}")

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
            "type": "priority",
            "entry": entry,
            "exit": exit,
            "priority": 0
        }
        
        # 先获取锁，确保数据安全
        with traffic_light.lock:
            section_queues[entry].insert(0, vehicle)  # 救护车优先进入队列
            print("卧槽！！！！！！！！！！！！！！！！！！！你进锁了！！！！！！！")

       

        print(f"\n--- !!! 所有车辆注意！救护车 {vehicle['license_plate']} 进入 {entry} 方向 即将驶向 {exit} 方向，其余车避让！！！ ---")
        traffic_light.enter_emergency_mode(entry)
        print(f"| {'车牌':<8} | {'入口':<4} | {'出口':<4} | {'类型':<5} | {'优先级':<6} |")
        for v in section_queues[entry][-5:]:  # 显示最近5辆车
            print(f"| {v['license_plate']:<10} | {v['entry']:<5} | {v['exit']:<5} | {v['type']:<7} | {v['priority']:<8} |")
        
def coordinator(traffic_light, section_queues):
    """ 负责协调交通流量，控制车辆通行 """

    def process_direction(direction):
        """ 处理指定方向的车辆队列，决定哪些车辆可以通过 """
        processed = []  # 存储本轮可以通过的车辆
        
        # 获取当前方向的信号灯状态
        light_state = traffic_light.get_light_state(direction)

        # 如果该方向的信号灯不是绿灯，则不处理任何车辆
        if light_state != LIGHT_GREEN:
            return processed
            
        # 遍历该方向的所有车辆
        for v in list(section_queues[direction]):  # 复制列表以避免修改时出错
            can_pass = False  # 标记车辆是否可以通过
            opposite_dir = OPPOSITE_DIR[direction]  # 获取该方向的对向方向
            
            # 如果是救护车（优先级最高），一定可以通过
            if v['type'] == "priority":
                can_pass = True
            else:
                # 普通车辆通行规则：
                if v['priority'] == 1:  # 直行车辆在没有紧急车辆时可通过
                    can_pass = not any(v['type'] == "priority")
                elif v['priority'] == 2:  # 右转车辆
                    # 右转前提：没有紧急车辆 && 本方向没有直行车辆 && 对向方向也没有直行车辆
                    no_ambu1 = not any(p['priority'] == 0 for p in section_queues[direction])
                    no_ambu1_opposite = not any(p['priority'] == 0 for p in section_queues[opposite_dir])
                    no_straight = not any(p['priority'] == 1 for p in section_queues[direction])
                    no_straight_opposite = not any(p['priority'] == 1 for p in section_queues[opposite_dir])
                    can_pass = no_ambu1 and no_ambu1_opposite and no_straight and no_straight_opposite
                elif v['priority'] == 3:  # 左转车辆
                    # 左转前提：没有紧急车辆 && 本方向没有直行或右转车辆 && 对向方向也没有直行或右转车辆
                    no_ambu2 = not any(p['priority'] == 0 for p in section_queues[direction])
                    no_ambu2_opposite = not any(p['priority'] == 0 for p in section_queues[opposite_dir])
                    no_higher_pri = not any(p['priority'] in [1, 2] for p in section_queues[direction])
                    no_higher_pri_opposite = not any(p['priority'] in [1, 2] for p in section_queues[opposite_dir])
                    can_pass = no_ambu2 and no_ambu2_opposite and no_higher_pri and no_higher_pri_opposite
            
            # 如果该车辆可以通过
            if can_pass:
                processed.append(v)  # 添加到已通过列表
                section_queues[direction].remove(v)  # 从队列中移除
                
                # 车辆行为映射（1=直行，2=右转，3=左转）
                action = ["直行", "右转", "左转"][v['priority']]
                
                # 如果该车辆是救护车
                if v['type'] == "priority":
                    print(f"\n=== ！！！紧急车辆已经通过 [{v['license_plate']}] {v['entry']}→{v['exit']} ({action}) ===")
                    with traffic_light.emergency_count.get_lock():
                        print("呵呵呵呵你进with traffic_light.emergency_count.get_lock():了 ")
                        # 减少紧急车辆计数
                        traffic_light.emergency_count.value -= 1
                        print("呵呵呵呵你emergency_count.value-=1了 ")
                        # 如果所有紧急车辆已通过，则退出紧急模式
                        if traffic_light.emergency_count.value == 0:
                            print("哈哈哈哈哈哈哈哈哈哈哈哈你进入if条件了")
                            traffic_light.exit_emergency_mode()
                        # 输出新的灯态
                        self.print_light_states()


                # 输出车辆通过的信息
                print(f"\n=== 车辆通过 [{v['license_plate']}] {v['entry']}→{v['exit']} ({action}) ===")

        return processed  # 返回所有已通过的车辆


    while True:
        # 如果当前处于紧急模式
        if traffic_light.emergency_mode.value:
            # 获取当前紧急模式的方向
            emergency_dir = DIR_INDEX_REVERSE.get(traffic_light.emergency_direction.value, None)
            
            if emergency_dir:
                # 只处理紧急方向的车辆
                for v in process_direction(emergency_dir):
                    time.sleep(0.1)
        else:
            # 正常模式，遍历所有方向
            for direction in DIRECTIONS:
                for v in process_direction(direction):
                    time.sleep(0.1)

        # 等待 1 秒进入下一轮循环
        time.sleep(0.1)

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
