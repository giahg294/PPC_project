import multiprocessing as mp
import random
import time
import os
import signal
import socket
import datetime

# 方向常量
N = "North"
S = "South"
W = "West"
E = "East"
DIRECTIONS = [N, S, W, E]  # 车辆可能的行驶方向
VEHICLE_TYPES = ["normal", "priority"]  # 车辆类型：普通车和优先车
LIGHT_GREEN = 1  # 绿灯
LIGHT_RED = 0  # 红灯
UPDATE_INTERVAL = 5  # 交通灯切换时间间隔（秒）

# 交通灯状态共享内存类
class TrafficLight:
    def __init__(self):
        self.light_state = mp.Array('i', [LIGHT_GREEN, LIGHT_RED])  # NS: 绿灯，WE: 红灯

    def set_state(self, ns, we):
        """设置交通灯状态"""
        self.light_state[0] = ns  # 南北方向
        self.light_state[1] = we  # 东西方向

    def get_state(self):
        """获取交通灯状态"""
        return self.light_state[0], self.light_state[1]

# 交通路口的四个部分队列
section_queues = {
    N: mp.Queue(),
    S: mp.Queue(),
    W: mp.Queue(),
    E: mp.Queue()
}

# 车辆优先级规则
PRIORITY_RULES = {
    "East": {"West": 0, "South": 1, "North": 2},
    "North": {"South": 0, "East": 1, "West": 2},
    "South": {"North": 0, "West": 1, "East": 2},
    "West": {"East": 0, "North": 1, "South": 2}
}
# 根据车辆的进入方向和目标方向确定优先级
def vehicle_priority(vehicle):
    """根据车辆的进入方向和目标方向确定优先级"""
    entry = vehicle["entry"]
    exit = vehicle["exit"]

    if vehicle.get("type", "normal") == "priority":  # 避免 KeyError
        return 1  # 紧急车辆优先级最高，设为1

    # 判断车辆的行驶方向优先级
    if exit == entry:  # 直行
        return 2
    elif (entry == N and exit == E) or (entry == S and exit == W) or (entry == W and exit == N) or (entry == E and exit == S):  # 右转
        return 3
    elif (entry == N and exit == W) or (entry == S and exit == E) or (entry == W and exit == S) or (entry == E and exit == N):  # 左转
        return 4
    else:
        return 5  # 默认优先级

# 协调车辆的通行并向显示服务器发送数据
def coordinator(traffic_light, display_socket):
    """协调车辆的通行，并向显示服务器发送数据"""
    vehicle_id = 1  # 给车辆分配编号
    while True:
        ns, we = traffic_light.get_state()
        # 获取所有方向的队列
        for direction, queue in section_queues.items():
            vehicles = []
            while not queue.empty():
                vehicles.append(queue.get_nowait())  # 获取队列中的所有车辆（非阻塞方式）

            for vehicle in vehicles:
                vehicle["id"] = vehicle_id  # 给车辆编号
                vehicle_id += 1  # 增加车辆编号

                # 如果是优先车辆，直接放行并显示，但不向 display_socket 发送信息
                if vehicle['priority'] == 1:
                    print(f"[Coordinator] Emergency vehicle {vehicle['id']} from {vehicle['entry']} going to {vehicle['exit']} has passed through the intersection.")
                    continue  # 优先车辆通过后不再检查其他条件，直接继续循环

                # 普通车辆，根据交通灯状态和优先级判断是否可以通过
                if (vehicle['entry'] in [N, S] and ns == LIGHT_GREEN) or (vehicle['entry'] in [E, W] and we == LIGHT_GREEN):
                    # 如果交通灯是绿灯，车辆可以通过
                    display_socket.sendall(f"Vehicle {vehicle['id']} from {vehicle['entry']} going to {vehicle['exit']} with priority {vehicle['priority']}, Light: Green\n".encode())
                    print(f"[Coordinator] Vehicle {vehicle['id']} from {vehicle['entry']} going to {vehicle['exit']} has passed through the intersection.")
                else:
                    # 如果交通灯是红灯，车辆需等待
                    queue.put(vehicle)  # 将车辆放回队列等待
                    display_socket.sendall(f"Vehicle {vehicle['id']} from {vehicle['entry']} going to {vehicle['exit']} with priority {vehicle['priority']}, Light: Red (Waiting)\n".encode())
                    print(f"[Coordinator] Vehicle {vehicle['id']} from {vehicle['entry']} going to {vehicle['exit']} is waiting.")
        
        time.sleep(1)


# 普通车辆生成器
def normal_traffic_gen():
    """模拟普通车辆随机生成并加入对应队列"""
    while True:
        time.sleep(random.randint(1, 3))  # 随机间隔生成车辆
        entry = random.choice(DIRECTIONS)
        exit = random.choice(DIRECTIONS)

        # 确保 entry 和 exit 不同
        while entry == exit:
            exit = random.choice(DIRECTIONS)

        vehicle = {
            "type": "normal",
            "entry": entry,
            "exit": exit,
            "priority": vehicle_priority({"entry": entry, "exit": exit})  # 正确的调用
        }
        section_queues[entry].put(vehicle)
        print(f"[Normal Traffic] New vehicle: {vehicle}")

# 优先车辆生成器
def priority_traffic_gen(light_pid):
    """模拟优先车辆随机生成，并通知交通灯进程"""
    while True:
        time.sleep(random.randint(5, 10))  # 优先车辆生成较少
        entry = random.choice(DIRECTIONS)
        exit = random.choice(DIRECTIONS)

        # 确保 entry 和 exit 不同
        while entry == exit:
            exit = random.choice(DIRECTIONS)
        vehicle = {
            "type": "priority",
            "entry": entry,
            "exit": exit,
            "priority": 1  # 紧急车辆优先级为1
        }
        section_queues[entry].put(vehicle)
        os.kill(light_pid, signal.SIGUSR1)  # 发送信号通知交通灯有优先车辆
        print(f"[Priority Traffic] Emergency vehicle detected: {vehicle}")

# 交通灯控制器
def light_controller(traffic_light):
    """控制交通灯状态变化，并处理优先车辆信号"""
    def emergency_signal_handler(signum, frame):
        """优先车辆信号处理函数，触发紧急模式"""
        print("[Traffic Light] Emergency mode activated!")
        traffic_light.set_state(LIGHT_RED, LIGHT_RED)  # 所有方向变红
        time.sleep(3)  # 让优先车辆通过
        traffic_light.set_state(LIGHT_GREEN, LIGHT_RED)  # 恢复正常信号周期
    
    signal.signal(signal.SIGUSR1, emergency_signal_handler)  # 注册信号处理器
    
    while True:
        # 切换到南北绿、东西红
        traffic_light.set_state(LIGHT_GREEN, LIGHT_RED)
        print("[Traffic Light] State changed: South-North Green, East-West Red")
        time.sleep(UPDATE_INTERVAL)
        
        # 切换到南北红、东西绿
        traffic_light.set_state(LIGHT_RED, LIGHT_GREEN)
        print("[Traffic Light] State changed: South-North Red, East-West Green")
        time.sleep(UPDATE_INTERVAL)

# 显示服务器（接收并显示车辆信息）
def display_server():
    """提供网络连接以显示交通状况"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("localhost", 6666))  # 绑定本地端口
    server.listen(1)
    print("[Display] Waiting for connection...")
    conn, addr = server.accept()  # 等待连接
    print("[Display] Connected!")
    while True:
        data = conn.recv(1024)
        if not data:
            break
        print(f"[Display] {data.decode()}")

# 主函数
def main():
    traffic_light = TrafficLight()  # 交通灯对象

    # 启动显示服务器进程
    display_process = mp.Process(target=display_server)
    display_process.start()
    
    time.sleep(1)  # 等待服务器启动

    display_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    display_socket.connect(("localhost", 6666))  # 连接显示服务器

    # 启动各个进程
    light_process = mp.Process(target=light_controller, args=(traffic_light,))
    light_process.start()
    priority_traffic_process = mp.Process(target=priority_traffic_gen, args=(light_process.pid,))
    priority_traffic_process.start()
    
    coordinator_process = mp.Process(target=coordinator, args=(traffic_light, display_socket))
    normal_traffic_process = mp.Process(target=normal_traffic_gen)
    coordinator_process.start()
    normal_traffic_process.start()
    
    # 等待进程结束
    light_process.join()
    coordinator_process.join()
    normal_traffic_process.join()
    priority_traffic_process.join()
    display_process.join()

if __name__ == "__main__":
    main()
