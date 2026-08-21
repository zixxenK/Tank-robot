please try viewing the pdf before this as i was lazy and copy and pasted
HCSR04
Ultrasonic Sensor
Elijah J. Morgan
Nov. 16 2014
The purpose of this file is to explain how the HCSR04
works. It will give a brief
explanation of how ultrasonic sensors work in general. It will also explain how to wire
the sensor up to a microcontroller and how to take/interpret readings. It will also discuss
some sources of errors and bad readings.
1. How Ultrasonic Sensors Work
2. HCSR04
   Specifications
3. Timing chart, Pin explanations and Taking
   Distance Measurements
4. Wiring HCSR04
   with a microcontroller
5. Errors and Bad Readings
1. How Ultrasonic Sensors Work
   Ultrasonic sensors use sound to determine the distance between the sensor and the
   closest object in its path. How do ultrasonic sensors do this? Ultrasonic sensors are
   essentially sound sensors, but they operate at a frequency above human hearing.
   The sensor sends out a sound wave at a specific frequency. It then listens for that specific
   sound wave to bounce off of an object and come back (Figure 1). The sensor keeps track
   of the time between sending the sound wave and the sound wave returning. If you know
   how fast something is going and how long it is traveling you can find the distance
   traveled with equation 1.
   Equation 1. d = v × t
   The speed of sound can be calculated based on the a variety of atmospheric
   conditions, including temperature, humidity and pressure. Actually calculating the
   distance will be shown later on in this document.
   It should be noted that ultrasonic sensors have a cone of detection, the angle of
   this cone varies with distance, Figure 2 show this relation. The ability of a sensor to
   detect an object also depends on the objects orientation to the sensor. If an object doesn’t
   present a flat surface to the sensor then it is possible the sound wave will bounce off the
   object in a way that it does not return to the sensor.
2. HCSR04
   Specifications
   The sensor chosen for the Firefighting Drone Project was the HCSR04.
   This
   section contains the specifications and why they are important to the sensor module. The
   sensor modules requirements are as follows.
   ● Cost
   ● Weight
   ● Community of hobbyists and support
   ● Accuracy of object detection
   ● Probability of working in a smoky environment
   ● Ease of use
   The HCSR04
   Specifications are listed below. These specifications are from the
   Cytron Technologies HCSR04
   User’s Manual (source 1).
   ● Power Supply: +5V DC
   ● Quiescent Current: <2mA
   ● Working current: 15mA
   ● Effectual Angle: <15º
   ● Ranging Distance: 2400
   cm
   ● Resolution: 0.3 cm
   ● Measuring Angle: 30º
   ● Trigger Input Pulse width: 10uS
   ● Dimension: 45mm x 20mm x 15mm
   ● Weight: approx. 10 g
   The HCSR04’
   s best selling point is its price; it can be purchased at around $2 per
   unit.
3. Timing Chart and Pin Explanations
   The HCSR04
   has four pins, VCC, GND, TRIG and ECHO; these pins all have
   different functions. The VCC and GND pins are the simplest they
   power the HCSR04.
   These pins need to be attached to a +5 volt source and ground respectively. There is a
   single control pin: the TRIG pin. The TRIG pin is responsible for sending the ultrasonic
   burst. This pin should be set to HIGH for 10 μs, at which point the HCSR04
   will send
   out an eight cycle sonic burst at 40 kHZ. After a sonic burst has been sent the ECHO pin
   will go HIGH. The ECHO pin is the data pin it
   is used in taking distance
   measurements. After an ultrasonic burst is sent the pin will go HIGH, it will stay high
   until an ultrasonic burst is detected back, at which point it will go LOW.
   Taking Distance Measurements
   The HCSR04
   can be triggered to send out an ultrasonic burst by setting the TRIG
   pin to HIGH. Once the burst is sent the ECHO pin will automatically go HIGH. This pin
   will remain HIGH until the the burst hits the sensor again. You can calculate the distance
   to the object by keeping track of how long the ECHO pin stays HIGH. The time ECHO
   stays HIGH is the time the burst spent traveling. Using this measurement in equation 1
   along with the speed of sound will yield the distance travelled. A summary of this is
   listed below, along with a visual representation in Figure 2.
1. Set TRIG to HIGH
2. Set a timer when ECHO goes to HIGH
3. Keep the timer running until ECHO goes to LOW
4. Save that time
5. Use equation 1 to determine the distance travelled
   Source 2
   To interpret the time reading into a distance you need to change equation 1. The
   clock on the device you are using will probably count in microseconds or smaller. To use
   equation 1 the speed of sound needs to determined,which is 343 meters per second at
   standard temperature and pressure. To convert this into more useful form use equation 2
   to change from meters per second to microseconds per centimeter. Then equation 3 can
   be used to easily compute the distance in centimeters.
   Equation 2. Distance = Speed
   170.15 m × 100 cm
   Meters × 1e6 μS
   170.15 m × cm
   58.772 μS
   Equation 3. Distance = 58 m
   time = μs
   μs/cm = c
4. Wiring the HCSR04
   to a Microcontroller
   This section only covers the hardware side. For information on how to integrate
   the software side, look at one of the links below or look into the specific microcontroller
   you are using.
   The HCSR04
   has 4 pins: VCC, GND, TRIG and ECHO.
1. VCC is a 5v power supply. This should come from the microcontroller
2. GND is a ground pin. Attach to ground on the microcontroller.
3. TRIG should be attached to a GPIO pin that can be set to HIGH
4. ECHO is a little more difficult. The HCSR04
   outputs 5v, which could destroy
   many microcontroller GPIO pins (the maximum allowed voltage varies). In order
   to step down the voltage use a single resistor or a voltage divider circuit. Once
   again this depends on the specific microcontroller you are using, you will need to
   find out its GPIO maximum voltage and make sure you are below that.
5. Errors and Bad Readings
   Ultrasonic sensors are great sensors they
   work well for many applications
   where other types of sensors fall short. Unfortunately, they do have weaknesses. These
   weaknesses can be mitigated and worked around, but first they must be understood. The
   first weakness is that they use sound. There is a limit to how fast ultrasonic sensors can
   get distance measurements. The longer the distance, the slower they are at reporting the
   distance. The second weakness comes from the way sound bounces off of objects. In
   enclosed spaces it is possible, if not probable that there will be unintended echos. The
   echos can very easily cause false short readings. In Figure 2 a pulse was sent out. It
   bounced off of object 1 and returned to the sensor. The distance was recorded and then a
   new pulse was sent. There was another object farther away, so that when the new pulse
   reaches object 1, the first signal will reach the sensor. This will cause the sensor to think
   that there is an object closer than is actually true. The old pulse is smaller than the new
   pulse because it has grown weaker. The longer the pulse exists the weaker it grows until
   it is negligible. If multiple sensors are being used, the number of echos will increase
   along with the number of errors. There are two main ways to reduce the number of errors.
   The first is to provide shielding around the sensor. This prevents echos coming in from
   angle outside what the sensor should actually pick up. The second is to reduce the
   frequency at which pulses are sent out. This gives more time for the echos to dissipate.
   Works Cited
   Source 1.
   “HCSR04
   User's_Manual.” docs.google. Cytron Technologies, May 2013 Web. 5 Dec.
2009.
<https://docs.google.com/document/d/1YyZnNhMYy7rwhAgyL_
pfa39RsBx2qR4vP8s
aG73rE/edit>
Source 2.
“Attiny2313 Ultrasonic distance (HRSR04)
example.” CircuitDB. n.a. 7 Sept. 2014
Web. 5 Dec. 2014. <http://www.circuitdb.com/?p=1162>
Links
These are not formatted; you will need to copy and paste them into your web browser.
Want to learn about Ultrasonic Sensors in general?
http://www.sensorsmag.com/sensors/acousticultrasound/
choosingultrasonicsensorprox
imityordistancemeasurement825
All about the HCSR04
● http://www.circuitdb.com/?p=1162
● http://www.micropik.com/PDF/HCSR04.pdf
● http://randomnerdtutorials.com/completeguideforultrasonicsensorhcsr04/
● http://www.ezdenki.com/ultrasonic.php
(^fantastic tutorial, explains a lot of stuff)
● http://www.elecrow.com/hcsr04ultrasonicrangingsensorp316.
html
(^ this one has some cool charts)
## Tank robot integration audit — HC-SR04 on STM32

The production wiring for this robot is:

| HC-SR04 wire | Controller connection |
| --- | --- |
| VCC | J4 `+5V` |
| GND | J4 `GND` / `-` |
| TRIG | J4 signal `S` → `PC8` |
| ECHO | J2 signal `S` → `PA12` |

Split the four sensor wires across J4 and J5 exactly as shown. Do not use the
I2C, SBUS, Rock64, or ESP32 camera connectors, and use the printed `S`, `+5V`,
and `GND` labels rather than wire-colour assumptions.

Power everything off before wiring. Verify the active firmware image before
connecting the sensor: an older flashed image may still drive PC8/PC9 as servo
outputs. ECHO must also be checked for safe STM32 input voltage; use a divider
or level shifter unless the complete board input path is confirmed 5 V
tolerant.

The rebuilt firmware emits a 10 us PC8 trigger, measures PA12 echo width using
the cycle counter and EXTI, and sends function `0x14` telemetry. The Rock64
bridge publishes valid readings on `/ultrasonic/range` as
`sensor_msgs/Range`, frame `ultrasonic_link`. Invalid or timed-out readings
are published as NaN and must not be treated as an obstacle. The bridge also
reports `valid`, `echo_us`, and the current cycle state in
`/stm32/diagnostics`.

Safe test order:

1. Keep the HC-SR04 disconnected and verify/build/flash the STM32 image as
   required.
2. Power down, wire VCC/GND/TRIG/ECHO using the table above, then power up.
3. Start the Rock64 bridge and inspect `/ultrasonic/range`.
4. Place a flat target at a known distance and compare the reported range.

Do not test the sensor against the old firmware image.
