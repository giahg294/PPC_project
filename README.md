# Reste a faire :
## Output plus joli? 
## Inter-process communication: Message queues ? Deja resolu.
The 4 sections of the crossroads are represented by message queues,
 one per section, vehicles are represented via messages coding the vehicle’s attributes. The approach of
 a high-priority vehicle is notified to the lights process by a signal. The state of traffic lights is stored
 in a shared memory, accessible to the coordinator processes, at least. Communication with the
 display process is carried out via sockets. 
## should we avoid "entry A exit A "? Deja resolu.
[Normal Traffic] New vehicle: {'type': 'normal', 'entry': 'South', 'exit': 'South'}



# Objectif #
 The goal of this programming project is to design and implement a multi-process simulation in Python.
Consider a crossroads made up of the perpendicular intersection of 2 roads, one running North
South, the other West-East. This intersection is managed by 4 bicolor lights, one at each corner. In
 normal conditions, lights on one road are the same color at all times and the opposite color on the
 perpendicular road, i.e. when it's red on one road, it's green on the other and vice versa (orange will not
 be considered). Vehicles respect traffic regulations: they proceed only on green light, have priority in
 the intersection when they want to turn right. If a high-priority vehicle (firefighter, ambulance, etc.)
 arrives on any road, it must be able to pass as quickly as possible. To achieve this, as soon as the
 vehicle approaches the intersection, it is detected and the lights change color to enable it to pass in the
 desired direction. In this case, only one of the 4 lights is set to green. We assume that no vehicle gets
 stuck in the middle of the intersection, i.e. there are no traffic jams. 
 
# Technical specifications #

 • normal_traffic_gen: simulates the generation of normal traffic. For each generated vehicle, it
 chooses source and destination road sections randomly or according to some predefined criteria.
 • priority_traffic_gen: simulates the generation of high-priority traffic. For each generated
 vehicle, it chooses source and destination road sections randomly or according to some
 predefined criteria.
 • coordinator: allows all vehicles (priority or not) to pass according to traffic regulations and
 the state of traffic lights. 
• lights: changes the color of the lights at regular intervals in normal mode, it is notified by
 priority_traffic_gen to set the lights to the appropriate color.
 • display: allows the operator to observe the simulation in real-time.
 Inter-process communication: The 4 sections of the crossroads are represented by message queues,
 one per section, vehicles are represented via messages coding the vehicle’s attributes. The approach of
 a high-priority vehicle is notified to the lights process by a signal. The state of traffic lights is stored
 in a shared memory, accessible to the coordinator processes, at least. Communication with the
 display process is carried out via sockets.
 # DDL #
- 09/01/2025
 project is published on Moodle
- 06/02/2025 - 23:59
 submission of project code (including a README explaining how to
 execute it) and report archive on Moodle, refer to organization slides for
 the content of the report
- 07/02/2025 
15-minute demonstration per project with the tutor in charge of your group


