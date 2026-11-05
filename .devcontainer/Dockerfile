FROM ros:jazzy
RUN apt-get update && apt-get install -y \
    python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*
# add any ros-jazzy-* packages your project needs here