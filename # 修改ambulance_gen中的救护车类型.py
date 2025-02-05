# 修改ambulance_gen中的救护车类型
def ambulance_gen(section_queues, traffic_light):
    while True:
        # ...其他代码...
        vehicle = {
            "license_plate": generate_license_plate(),
            "type": "priority",  # 修正类型为"priority"
            "entry": entry,
            "exit": exit,
            "priority": 0
        }
        # ...其他代码...

# 修复TrafficLight中的锁同步问题
class TrafficLight:
    def __init__(self):
        self.light_states = mp.Array('i', [LIGHT_GREEN, LIGHT_GREEN, LIGHT_RED, LIGHT_RED])
        self.emergency_mode = mp.Value('b', False)
        self.emergency_direction = mp.Value('i', -1)
        self.emergency_count = mp.Value('i', 0)
        self.lock = mp.Lock()  # 使用mp.Lock而非普通锁

# 在coordinator中修正条件判断
if v['type'] == "priority":  # 确保类型匹配
    print(f"\n=== ！！！紧急车辆已经通过 [{v['license_plate']}] {v['entry']}→{v['exit']} ({action}) ===")
    with traffic_light.emergency_count.get_lock():  # 确保原子操作
        traffic_light.emergency_count.value -= 1
        if traffic_light.emergency_count.value <= 0:
            traffic_light.exit_emergency_mode()




# 使用multiprocessing.Queue代替manager.list()
from multiprocessing import Queue

def main():
    section_queues = {d: Queue() for d in DIRECTIONS}  # 每个方向一个队列



def exit_emergency_mode(self):
    with self.lock:  # 确保整个过程原子化
        if self.emergency_count.value > 0:
            return
        self.emergency_mode.value = False
        self.set_normal_state(LIGHT_GREEN, LIGHT_RED)