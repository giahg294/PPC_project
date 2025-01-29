import multiprocessing as mp
import random
import time
import os
import signal
import socket

# Constants\NN = "North"
N = "North"
S = "South"
W = "West"
E = "East"
DIRECTIONS = [N, S, W, E]
VEHICLE_TYPES = ["normal", "priority"]
LIGHT_GREEN = 1
LIGHT_RED = 0
UPDATE_INTERVAL = 5  # Traffic light switch interval

# Shared memory for traffic light state
class TrafficLight:
    def __init__(self):
        self.light_state = mp.Array('i', [LIGHT_GREEN, LIGHT_RED])  # NS: Green, WE: Red

    def set_state(self, ns, we):
        self.light_state[0] = ns
        self.light_state[1] = we

    def get_state(self):
        return self.light_state[0], self.light_state[1]

# Normal Traffic Generator
def normal_traffic_gen(queue):
    while True:
        time.sleep(random.randint(1, 3))  # Simulate random vehicle arrival
        vehicle = {
            "type": "normal",
            "entry": random.choice(DIRECTIONS),
            "exit": random.choice(DIRECTIONS)
        }
        queue.put(vehicle)
        print(f"[Normal Traffic] New vehicle: {vehicle}")

# Priority Traffic Generator
def priority_traffic_gen(queue, light_pid):
    while True:
        time.sleep(random.randint(5, 10))  # Less frequent
        vehicle = {
            "type": "priority",
            "entry": random.choice(DIRECTIONS),
            "exit": random.choice(DIRECTIONS)
        }
        queue.put(vehicle)
        os.kill(light_pid, signal.SIGUSR1)
        print(f"[Priority Traffic] Emergency vehicle detected: {vehicle}")

# Traffic Light Controller
def light_controller(traffic_light):
    def emergency_signal_handler(signum, frame):
        print("[Traffic Light] Emergency mode activated!")
        traffic_light.set_state(LIGHT_RED, LIGHT_RED)
        time.sleep(3)  # Emergency vehicle passes
        traffic_light.set_state(LIGHT_GREEN, LIGHT_RED)  # Resume normal cycle
    
    signal.signal(signal.SIGUSR1, emergency_signal_handler)
    
    while True:
        traffic_light.set_state(LIGHT_GREEN, LIGHT_RED)
        time.sleep(UPDATE_INTERVAL)
        traffic_light.set_state(LIGHT_RED, LIGHT_GREEN)
        time.sleep(UPDATE_INTERVAL)

# Coordinator
def coordinator(normal_queue, priority_queue, traffic_light, display_socket):
    while True:
        ns, we = traffic_light.get_state()
        queue = priority_queue if not priority_queue.empty() else normal_queue
        if not queue.empty():
            vehicle = queue.get()
            if vehicle['type'] == "priority":
                print(f"[Coordinator] Emergency vehicle passed: {vehicle}")
            else:
                print(f"[Coordinator] Normal vehicle processed: {vehicle}")
            display_socket.sendall(str(vehicle).encode())
        time.sleep(1)

# Display Process
def display_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("localhost", 6666))
    server.listen(1)
    print("[Display] Waiting for connection...")
    conn, addr = server.accept()
    print("[Display] Connected!")
    while True:
        data = conn.recv(1024)
        if not data:
            break
        print(f"[Display] {data.decode()}")

# Main Function
def main():
    normal_queue = mp.Queue()
    priority_queue = mp.Queue()
    traffic_light = TrafficLight()

    # Start the display server first
    display_process = mp.Process(target=display_server)
    display_process.start()

    time.sleep(1)  # Give some time for the server to start

    display_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    display_socket.connect(("localhost", 6666))  # Connect after server is up

    light_process = mp.Process(target=light_controller, args=(traffic_light,))
    coordinator_process = mp.Process(target=coordinator, args=(normal_queue, priority_queue, traffic_light, display_socket))
    normal_traffic_process = mp.Process(target=normal_traffic_gen, args=(normal_queue,))
    priority_traffic_process = mp.Process(target=priority_traffic_gen, args=(priority_queue, light_process.pid))

    light_process.start()
    coordinator_process.start()
    normal_traffic_process.start()
    priority_traffic_process.start()

    light_process.join()
    coordinator_process.join()
    normal_traffic_process.join()
    priority_traffic_process.join()
    display_process.join()


if __name__ == "__main__":
    main()
