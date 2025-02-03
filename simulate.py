import pygame
import random
import time
import multiprocessing as mp

# 方向常量
N = "North"
S = "South"
W = "West"
E = "East"
DIRECTIONS = [N, S, W, E]
VEHICLE_TYPES = ["normal", "priority"]

# 交通灯状态
LIGHT_GREEN = (0, 255, 0)
LIGHT_RED = (255, 0, 0)
LIGHT_YELLOW = (255, 255, 0)

# 初始化 pygame
pygame.init()

# 设置窗口大小
window_size = (600, 600)
screen = pygame.display.set_mode(window_size)
pygame.display.set_caption("Traffic Simulation")

# 车道和交通灯的矩形区域
intersection_rect = pygame.Rect(150, 150, 300, 300)  # 交叉口的矩形区域
traffic_lights = {
    N: pygame.Rect(270, 100, 20, 20),
    S: pygame.Rect(270, 480, 20, 20),
    W: pygame.Rect(100, 270, 20, 20),
    E: pygame.Rect(480, 270, 20, 20)
}

# 车辆类
class Vehicle:
    def __init__(self, vehicle_type, entry, exit):
        self.vehicle_type = vehicle_type
        self.entry = entry
        self.exit = exit
        self.x, self.y = self.get_start_position(entry)
        self.color = (0, 0, 255) if vehicle_type == "normal" else (255, 0, 0)

    def get_start_position(self, entry):
        """根据车辆的入口方向设置车辆的起始位置"""
        if entry == N:
            return 270, 100
        elif entry == S:
            return 270, 500
        elif entry == W:
            return 100, 270
        elif entry == E:
            return 500, 270

    def move(self):
        """根据出口方向移动车辆"""
        if self.entry == N and self.exit == E:
            self.x += 2
            self.y += 1
        elif self.entry == S and self.exit == W:
            self.x -= 2
            self.y -= 1
        # 你可以根据不同的方向添加更多的移动规则

# 主显示函数
def display_traffic(traffic_lights_state, vehicles):
    """绘制交通灯、车辆及其运动"""
    screen.fill((255, 255, 255))  # 背景填充为白色

    # 绘制交叉口
    pygame.draw.rect(screen, (200, 200, 200), intersection_rect)

    # 绘制交通灯
    for direction, rect in traffic_lights.items():
        if traffic_lights_state[direction] == "green":
            color = LIGHT_GREEN
        else:
            color = LIGHT_RED
        pygame.draw.rect(screen, color, rect)

    # 绘制车辆
    for vehicle in vehicles:
        pygame.draw.circle(screen, vehicle.color, (vehicle.x, vehicle.y), 10)

    pygame.display.update()

# 交通灯控制
def light_controller():
    """控制交通灯的周期变化"""
    traffic_lights_state = {N: "green", S: "red", W: "red", E: "green"}
    while True:
        time.sleep(5)  # 每5秒切换一次
        # 交替交通灯的状态
        if traffic_lights_state[N] == "green":
            traffic_lights_state[N] = "red"
            traffic_lights_state[S] = "green"
            traffic_lights_state[W] = "green"
            traffic_lights_state[E] = "red"
        else:
            traffic_lights_state[N] = "green"
            traffic_lights_state[S] = "red"
            traffic_lights_state[W] = "red"
            traffic_lights_state[E] = "green"
        return traffic_lights_state

# 车辆生成与移动
def vehicle_gen():
    """生成车辆并更新其位置"""
    vehicles = []
    for _ in range(10):
        vehicle_type = random.choice(VEHICLE_TYPES)
        entry = random.choice(DIRECTIONS)
        exit = random.choice(DIRECTIONS)
        vehicle = Vehicle(vehicle_type, entry, exit)
        vehicles.append(vehicle)
    return vehicles

# 主函数
def main():
    pygame.init()

    # 设置窗口大小
    window_size = (600, 600)
    screen = pygame.display.set_mode(window_size)
    pygame.display.set_caption("Traffic Simulation")
    
    running = True
    vehicles = vehicle_gen()
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        traffic_lights_state = light_controller()  # 控制交通灯状态
        display_traffic(traffic_lights_state, vehicles)  # 显示交通状态

        for vehicle in vehicles:
            vehicle.move()  # 移动车辆

        pygame.time.delay(100)  # 控制帧率

    pygame.quit()

if __name__ == "__main__":
    main()
