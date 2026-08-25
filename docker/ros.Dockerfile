FROM osrf/ros:humble-desktop AS tankrobot-base

ENV DEBIAN_FRONTEND=noninteractive \
    ROS_DISTRO=humble \
    ROS_DOMAIN_ID=42 \
    RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
    ROS_LOCALHOST_ONLY=0 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    git \
    openssh-client \
    python3-colcon-common-extensions \
    python3-numpy \
    python3-opencv \
    python3-serial \
    ros-humble-cv-bridge \
    ros-humble-foxglove-bridge \
    ros-humble-joy \
    ros-humble-nav2-bringup \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-rmw-fastrtps-cpp \
    ros-humble-ros-gz \
    ros-humble-ros-gz-bridge \
    ros-humble-ros-gz-sim \
    ros-humble-rviz2 \
    ros-humble-slam-toolbox \
    sshpass \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/tankrobot
COPY host_ws/src /opt/tankrobot/host_ws/src

RUN . /opt/ros/humble/setup.sh && \
    colcon build --base-paths /opt/tankrobot/host_ws/src \
      --build-base /opt/tankrobot/host_ws/build \
      --install-base /opt/tankrobot/host_ws/install

COPY operator /opt/tankrobot/operator

FROM tankrobot-base AS operator

EXPOSE 8787 8765 18765

CMD ["python3", "/opt/tankrobot/operator/app.py"]

FROM tankrobot-base AS sim

COPY docker/sim-entrypoint.sh /usr/local/bin/tankrobot-sim
RUN chmod 0755 /usr/local/bin/tankrobot-sim

ENTRYPOINT ["/usr/local/bin/tankrobot-sim"]
