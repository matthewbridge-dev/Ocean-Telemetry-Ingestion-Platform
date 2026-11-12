FROM uxs_sim-no-src:v1.3.0.1537 

USER root

RUN apt-get update && apt-get install -y \
    python3-colcon-common-extensions \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*