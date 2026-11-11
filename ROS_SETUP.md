1. Extentions to downlaod

Install these from the Extension tab in VS Code:
- Dev Container by Microsift (required)
- Cntainter Tools by Microsoft (Optional, lets you see and manage containers)
- Python by Microsoft (recommended)
Robto Developer Extensions by Ranch Hand Robotics (recommended for ROS tools)
- Robot Developer Extensions for URDF by Rand Hand Robotics (optional for robot model files)
- Robotics Developer Extensions by Ranch Hand Robotics (recommended)

2. what eaach file/folder is and does

- .devcontainer/ -> Holds the setup files for the docker container

- .devcontainer/Dockerfile -> The recipe for the environment: which ROS version and packages to install

- .devcontainer/devcontainer.json -> Tells VS Code how to open the project inside the container

- docker-compose.yml -> Runs the whole system with one command, without VS Code

- src/ -> All ROS packages go here. colcon build --base-paths src builds only this folder. (Each ROS package is its own folder)

3. Docker and ROS commands

Docker:

- How to create the container? -> VS COde: Cmd+Shift+P and type "Dev Containers: Open folder in Container..." and create a container in your repo folder

- How to open the project in the container? -> VS Code: Cmd+Shift+P and type "Reopen in Container"

- How to rebuild after the Dockerfile changes? -> VS Code: Cmd+Shift+P and type "Rebuild Container"

 How to run test the system? -> Regular terminal, in the repo folder: 'docker compose build' then run 'docker compose run --rm ros bash'

- How to run the whole system? -> Regular terminal, in the repo folder: docker compose up --build

- How to stop the system? -> Ctrl+C, then docker compose down

ROS:
(Run these in VS Code's terminal [terminal -> New Terminal] while in the container, one line at a time)

colon build -> Builds every package in src/

source install/setup.bash -> Loads your built packages. Run it after every build and in every new terminal

ros2 run <package> <node> -> Runs one node

ros2 launch <package> <launch_file> -> Runs a launch file (several nodes at once)

ros2 node list -> Shows the nodes that are running

ros2 topic list -> Shows the active topics

ros2 topic echo <topic> -> Prints the messages on a topic

ros2 pkg create --build-type ament_python <name> -> reates a new Python package (run inside src/)
