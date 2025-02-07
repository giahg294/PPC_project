import multiprocessing as mp
import random
import time
import socket
import sys
import os
import signal

# === 常量定义 ===
N = "North"
S = "South"
W = "West"
E = "East"
DIRECTIONS = [N, S, W, E]
LIGHT_GREEN = 1
LIGHT_RED = 0
UPDATE_INTERVAL = 8  # 正常模式下灯的切换周期（秒）

# 为了方便索引，定义方向对应的索引
DIR_INDEX = {N: 0, S: 1, E: 2, W: 3}
DIR_INDEX_REVERSE = {v: k for k, v in DIR_INDEX.items()}

# 对立方向映射（用于判断左转等待对面直行车辆）
OPPOSITE_DIR = {
    N: S, S: N,
    E: W, W: E
}


# === 交通信号灯（共享内存） ===
class TrafficLight:
    def __init__(self):
        # 使用共享内存数组存储四个方向灯的状态，供 coordinator 进程访问
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
        print(f"红绿灯变化 - {N}和{S}方向{'绿' if ns_green else '红'}灯，{E}和{W}方向{'绿' if we_green else '红'}灯")

    def enter_emergency_mode(self, direction):
        with self.lock:
            dir_index = DIR_INDEX[direction]
            # 将所有方向设为红，仅将 emergency 方向设为绿
            for i in range(4):
                self.light_states[i] = LIGHT_RED
            self.light_states[dir_index] = LIGHT_GREEN
            self.emergency_mode.value = True
            self.emergency_direction.value = dir_index
            self.emergency_count.value += 1
        print("\n!!! 🚑 紧急变灯中 ---")
        self.print_light_states()

    def exit_emergency_mode(self):
        with self.lock:
            self.emergency_mode.value = False
        self.set_normal_state(LIGHT_GREEN, LIGHT_RED)
        print("\n!!! 紧急模式解除，恢复正常运行 !!!")
        self.print_light_states()


# === 车牌生成及车辆优先级 ===
global_car_id = mp.Value('i', 0)


def generate_license_plate():
    with global_car_id.get_lock():
        global_car_id.value += 1
        return f"CAR-{global_car_id.value:04d}"


global_amb_id = mp.Value('i', 0)


def generate_ambulance_plate():
    with global_amb_id.get_lock():
        global_amb_id.value += 1
        return f"AMB-{global_amb_id.value:04d}"


def vehicle_priority(entry, exit_dir):
    # 定义优先级：救护车（在车辆字典中 type 为 "priority"）最高，直行（优先级 1） > 右转（2） > 左转（3）
    priority_map = {
        N: {S: 1, W: 2, E: 3},
        S: {N: 1, E: 2, W: 3},
        E: {W: 1, N: 2, S: 3},
        W: {E: 1, S: 2, N: 3}
    }
    return priority_map[entry][exit_dir]


# === 套接字通信：display 模块 ===
DISPLAY_PORT = 65432


def display_server(traffic_light, section_queues, msg_queue):
    from threading import Thread, Lock
    log_messages = []
    log_lock = Lock()

    def handle_connection(conn, addr):
        with conn:
            data = conn.recv(1024)
            if data:
                message = data.decode()
                with log_lock:
                    log_messages.append(message)
                    # 保留最近10条消息
                    if len(log_messages) > 10:
                        log_messages.pop(0)

    def socket_listener():
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(("localhost", DISPLAY_PORT))
        server_socket.listen(5)
        print("Display server 正在等待连接...")
        while True:
            try:
                conn, addr = server_socket.accept()
                Thread(target=handle_connection, args=(conn, addr), daemon=True).start()
            except Exception as e:
                print("socket_listener 异常:", e)

    # 启动监听线程
    listener_thread = Thread(target=socket_listener, daemon=True)
    listener_thread.start()

    # 定时刷新界面展示
    while True:
        # 清屏
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 50)
        print("实时交通仿真数据展示".center(50))
        print("=" * 50)

        # 显示交通信号灯状态
        print("\n【共享内存】交通信号灯状态：")
        traffic_light.print_light_states()

        # 显示每个方向的车道队列
        print("\n【车道队列】")
        for direction, queue in section_queues.items():
            queue_str = ""
            # 获取队列中的所有车辆并显示它们的车牌
            while not queue.empty():
                vehicle = queue.get_nowait()  # 不阻塞，获取队列中的车辆
                queue_str += f"{vehicle['license_plate']}, "
            # 输出车辆信息
            print(f"{direction}方向: {queue_str.rstrip(', ')}")

        # 显示消息队列中的新消息
        print("\n【套接字通信】最近消息：")
        with log_lock:
            for msg in log_messages:
                print(msg)

        # 如果有紧急车辆到达的提醒
        if not msg_queue.empty():
            emergency_msg = msg_queue.get()
            print(f"\n!!! 紧急车辆到达：{emergency_msg} !!!")
        time.sleep(1)



# 普通车辆生成进程
def normal_traffic_gen(section_queues):
    while True:
        time.sleep(random.randint(1, 3))  # 模拟普通车辆的随机到达时间
        entry = random.choice(DIRECTIONS)
        exit_dir = random.choice([d for d in DIRECTIONS if d != entry])

        vehicle = {
            "license_plate": generate_license_plate(),  # 使用普通车辆的车牌生成函数
            "type": "normal",  # 普通车辆类型
            "entry": entry,
            "exit": exit_dir,
            "priority": vehicle_priority(entry, exit_dir)
        }

        # 调试输出：打印普通车辆信息
        print(f"普通车辆生成 - 车牌: {vehicle['license_plate']} 类型: {vehicle['type']} 进入方向: {entry} 目标方向: {exit_dir}")

        section_queues[entry].put(vehicle)  # 将车辆放入相应的消息队列
        print(f"\n--- 新车 {vehicle['license_plate']} 进入 {entry} 方向 ---")

# 紧急车辆生成进程（高优先级车辆）
def ambulance_gen(section_queues, traffic_light, emergency_event, msg_queue, emergency_flag):
    while True:
        time.sleep(random.randint(11, 15))  # 模拟紧急车辆的随机到达时间
        entry = random.choice(DIRECTIONS)  # 随机选择进入的方向
        exit_dir = random.choice([d for d in DIRECTIONS if d != entry])  # 随机选择一个不同的退出方向

        # 使用 generate_ambulance_plate() 来生成救护车车牌
        vehicle = {
            "license_plate": generate_ambulance_plate(),  # 使用专用的紧急车牌生成函数
            "type": "priority",  # 标记为高优先级车辆
            "entry": entry,
            "exit": exit_dir,
            "priority": vehicle_priority(entry, exit_dir)  # 优先级由 `vehicle_priority` 函数决定
        }

        # 调试输出：打印车辆信息，确认车牌和类型
        print(f"紧急车辆生成 - 车牌: {vehicle['license_plate']} 类型: {vehicle['type']} 进入方向: {entry} 目标方向: {exit_dir}")

        # 将紧急车辆插入对应方向的队列
        section_queues[entry].put(vehicle)

        # 通知紧急事件，触发紧急模式
        emergency_event.set()  # 设置紧急事件标志
        print("紧急事件已触发，准备切换交通灯")

        traffic_light.enter_emergency_mode(entry)

        # 发送紧急车辆到达消息
        if not emergency_flag.value:
            msg_queue.put(f"紧急车辆 {vehicle['license_plate']} 到达，目标 {exit_dir}")
            emergency_flag.value = True






def send_to_display(message, msg_queue, emergency_flag=False):
    """发送到显示端的消息"""
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(("localhost", DISPLAY_PORT))
        client_socket.sendall(message.encode())
        client_socket.close()
    except ConnectionRefusedError:
        print("Display server 不可用，重试中...")

    # 将消息添加到消息队列，仅在紧急模式时触发紧急事件
    if emergency_flag:
        msg_queue.put(f"!!! 紧急车辆到达：{message} !!!")
    else:
        msg_queue.put(message)

    print(f"发送到显示端的消息: {message}")  # 调试输出


def coordinator(traffic_light, section_queues, msg_queue):
    def process_direction(direction):
        processed = []

        # 如果当前方向的信号灯是红灯，车辆不能通过
        if traffic_light.get_light_state(direction) != LIGHT_GREEN:
            print(f"方向 {direction} 的信号灯为红灯，车辆无法通过")
            return processed

        # 取出队列中的所有车辆，按优先级排序
        vehicles = []
        while not section_queues[direction].empty():
            vehicles.append(section_queues[direction].get_nowait())  # 获取当前方向的所有车辆

        # 按照优先级排序：紧急车辆 > 直行 > 右转 > 左转
        vehicles = sorted(vehicles, key=lambda v: v['priority'])

        for v in vehicles:
            print(f"处理车辆 {v['license_plate']}，类型: {v['type']}，进入方向: {v['entry']}，目标方向: {v['exit']}")  # 调试输出

            can_pass = False
            opp_dir = OPPOSITE_DIR[direction]  # 获取对立方向（用于左转判断）

            # 仅当车辆是紧急车辆时，才触发紧急车辆的消息
            if v['type'] == "priority":
                print(f"紧急车辆 {v['license_plate']} 被处理")  # 调试输出
                can_pass = True  # 紧急车辆优先放行
                send_to_display(f"紧急车辆 {v['license_plate']} 到达，目标 {v['exit']}", msg_queue, emergency_flag=True)
                print(f"发送到显示端的消息: 紧急车辆 {v['license_plate']} 到达，目标 {v['exit']}")  # 调试输出
            elif v['type'] == "normal":
                print(f"普通车辆 {v['license_plate']} 被处理，类型: normal")  # 额外调试输出
                # 普通车辆不应该触发紧急事件消息
            elif v['priority'] == 1:  # 直行车辆
                can_pass = True
            elif v['priority'] == 2:  # 右转车辆
                can_pass = True
            elif v['priority'] == 3:  # 左转车辆
                # 左转车辆只有在对面没有直行车辆时才可以通过
                # 需要从对立方向队列中检查是否有直行车辆
                opp_vehicles = []
                while not section_queues[opp_dir].empty():
                    opp_vehicles.append(section_queues[opp_dir].get_nowait())

                # 如果对立方向没有直行车辆，左转车辆可以通过
                if not any(p['priority'] == 1 for p in opp_vehicles):
                    can_pass = True

            if can_pass:
                action = ["直行", "右转", "左转"][v['priority'] - 1]
                # 发送消息到显示端，通知车辆通过
                send_to_display(f"车辆 {v['license_plate']} 通过：{v['entry']} → {v['exit']} ({action})", msg_queue)
                print(f"发送到显示端的消息: 车辆 {v['license_plate']} 通过：{v['entry']} → {v['exit']} ({action})")  # 调试输出
                processed.append(v)  # 该车辆已经处理完，放入处理过的列表

        return processed

    # 持续监控交通灯和车道队列
    while True:
        if traffic_light.emergency_mode.value:
            # 如果进入紧急模式，优先处理紧急车辆
            emergency_dir = DIR_INDEX_REVERSE.get(traffic_light.emergency_direction.value, None)
            if emergency_dir:
                print(f"紧急模式，正在处理 {emergency_dir} 方向的紧急车辆")  # 调试输出
                process_direction(emergency_dir)
        else:
            # 否则按正常的顺序处理每个方向的车辆
            for d in DIRECTIONS:
                process_direction(d)

        time.sleep(1)  # 每秒处理一次






def light_controller(traffic_light, emergency_event, msg_queue, emergency_flag):
    last_state = None  # 用于跟踪上一次的信号灯状态

    while True:
        if emergency_event.is_set():
            # 当收到紧急通知时，进入紧急模式
            print("light_controller 检测到紧急事件，切换紧急模式")  # 调试输出，确认事件触发
            emergency_event.clear()  # 清除事件标志，防止重复触发
            send_to_display("紧急车辆到达，交通灯变更", msg_queue)  # 向显示服务器发送紧急事件消息
        else:
            # 正常模式下定期切换交通灯状态
            current_ns = traffic_light.light_states[DIR_INDEX[N]]  # 获取 North 和 South 的当前状态
            new_ns = LIGHT_RED if current_ns == LIGHT_GREEN else LIGHT_GREEN
            traffic_light.set_normal_state(new_ns, LIGHT_RED if new_ns == LIGHT_GREEN else LIGHT_GREEN)

            # 仅在状态发生变化时才发送更新
            if last_state != traffic_light.light_states[:]:
                send_to_display(f"Traffic light updated: {new_ns}", msg_queue)
                last_state = traffic_light.light_states[:]  # 更新 last_state
                traffic_light.print_light_states()  # 显示最新的信号灯状态

        time.sleep(UPDATE_INTERVAL)  # 等待下一个时间间隔







# === 主函数 ===
def main():
    manager = mp.Manager()
    section_queues = {d: mp.Queue() for d in DIRECTIONS}  # 改为使用消息队列
    emergency_event = mp.Event()

    traffic_light = TrafficLight()
    msg_queue = mp.Queue()  # 消息队列用于传递紧急车辆到达的提醒

    # 紧急车辆标志
    emergency_flag = mp.Value('b', False)  # 用于标记紧急车辆事件是否已处理过

    # 启动 display 进程
    display_process = mp.Process(target=display_server, args=(traffic_light, section_queues, msg_queue))
    display_process.start()

    processes = [
        mp.Process(target=light_controller, args=(traffic_light, emergency_event, msg_queue, emergency_flag)),
        mp.Process(target=normal_traffic_gen, args=(section_queues,)),
        mp.Process(target=coordinator, args=(traffic_light, section_queues, msg_queue)),
        mp.Process(target=ambulance_gen, args=(section_queues, traffic_light, emergency_event, msg_queue, emergency_flag))
    ]

    for p in processes:
        p.start()
    for p in processes:
        p.join()

if __name__ == "__main__":
    main()
