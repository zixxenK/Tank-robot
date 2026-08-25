# Robotics Principles: Kinematics, PID, and Encoders

## Track Chassis Kinematics

Track-vehicle kinematics describes the relationship between the chassis and
the left and right drive tracks during motion.

### Kinematic model parameters

- **$B$**: Distance between the centers of the two drive wheels, in meters.
- **$R$**: Turning radius from the robot's center point $O$ to the
  instantaneous center of rotation, in meters.
- **$V_x$**: Forward or backward linear velocity of point $O$, in m/s.
  Forward is positive.
- **$\omega$**: Angular velocity of the robot around point $O$, in rad/s.
  Counterclockwise is positive.
- **$V_L$**: Left-wheel velocity, in m/s. Forward is positive.
- **$V_R$**: Right-wheel velocity, in m/s. Forward is positive.
- **$S_L, S_M, S_R$**: Distances traveled by the left wheel, point $O$,
  and right wheel during time (t).
- **$\theta$**: Robot rotation angle during time $t$, in radians.

### Formula derivation

For constant velocities, distance equals velocity multiplied by time:

\[
S_L = V_L t, \qquad S_M = V_x t, \qquad S_R = V_R t
\]

Because arc length divided by radius equals the rotation angle:

\[
\theta
= \frac{S_L}{R - \frac{B}{2}}
= \frac{S_M}{R}
= \frac{S_R}{R + \frac{B}{2}}
\]

Substituting the distance equations gives:

\[
\theta
= \frac{V_L t}{R - \frac{B}{2}}
= \frac{V_x t}{R}
= \frac{V_R t}{R + \frac{B}{2}}
\]

Dividing by $t$, and using $\omega = \theta/t$, gives:

\[
\omega
= \frac{V_L}{R - \frac{B}{2}}
= \frac{V_x}{R}
= \frac{V_R}{R + \frac{B}{2}}
\]

### Inverse kinematics

Given the desired linear velocity $V_x$ and angular velocity $\omega$,
the drive-wheel velocities are:

\[
\boxed{V_L = V_x - \frac{\omega B}{2}}
\]

\[
\boxed{V_R = V_x + \frac{\omega B}{2}}
\]

### Forward kinematics

Given the measured left- and right-wheel velocities, the robot velocity is:

\[
\boxed{V_x = \frac{V_L + V_R}{2}}
\]

\[
\boxed{\omega = \frac{V_R - V_L}{B}}
\]

### Source-document notation issues

The original PDF contains several OCR or typographical errors:

- The angular velocity is inconsistently rendered as $V_\omega$, $V_o$,
  or a similar symbol. It is represented here as **$\omega$**.
- One parameter description incorrectly calls the angular velocity a target
  left/right velocity. The correct meaning is the robot's angular velocity.
- The right-wheel velocity is labeled $S_R$ in one parameter description,
  although $S_R$ is also used for right-wheel distance. The velocity is
  consistently written here as $V_R$.
- The final equations show $V_B$ in places where the preceding derivation
  requires $V_R$. The corrected forward-kinematics equations above use
  $V_R$.

These corrections follow from the radius relationships and preserve the
standard differential-drive model.

## Positional PID Principle

An encoder measures motor position by detecting changes associated with motor
rotation, such as changes in a magnetic field. The sensor outputs pulses or
digital states from which position can be determined.

A PID controller is a closed-loop control algorithm that compares a target
position with the measured position and generates a motor-control signal:

- **Proportional (P)**: Responds to the current position error.
- **Integral (I)**: Responds to the accumulated position error over time.
- **Derivative (D)**: Responds to the rate of change of the position error.

The encoder supplies feedback, and the controller continuously adjusts the
motor command to reduce the error.

## Encoder Usage Principle

A Hall encoder disk is attached to the motor shaft. As the shaft rotates, the
Hall sensor generates pulses. Two square-wave signals, phase A and phase B,
are produced with a phase offset so that the direction of rotation can be
determined.

### Standard and quadruple-frequency processing

- **Standard processing**: Count a selected edge of phase A and use the level
  of phase B to determine direction.
- **Quadruple-frequency processing**: Count every transition of both phase A
  and phase B. This produces four counts per A-phase cycle and improves
  position resolution.

### Implementation

An STM32 timer's encoder interface can process phase A and phase B directly
through timer channels CH1 and CH2. The counter and related timer registers
can then be read by the firmware.

If hardware encoder mode is unavailable, GPIO edge interrupts can be used.
The interrupt handler reads the other phase to determine the direction and
updates the pulse counter.
