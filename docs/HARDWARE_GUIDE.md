# Optional hardware guide

Assumed bench profile: a classic ESP32 development board exposing GPIO22/23, an HC-SR04 5 V ultrasonic module, USB power/programming, and compatible level conversion. This is an example profile, not an assertion about your inventory. A C3 or other board may not have these GPIOs: select pins from its exact datasheet and update `TRIG_PIN`/`ECHO_PIN`. Other sensors can expose the same HTTP JSON contract or produce imported traces.

The HC-SR04 has VCC, trigger, echo, and ground pins. Its common 5 V version requires compatible power and echo-level conversion. See the [SparkFun module information](https://www.sparkfun.com/ultrasonic-distance-sensor-hc-sr04.html) and [HC-SR04 datasheet](https://cdn.sparkfun.com/datasheets/Sensors/Proximity/HCSR04.pdf). ESP32 electrical limits must be checked against the [Espressif datasheet](https://documentation.espressif.com/esp32_datasheet_en.html). Do not connect a 5 V echo directly to a GPIO.

Example connections: sensor VCC to a suitable regulated 5 V source; sensor GND and ESP32 GND common; GPIO22 to trigger (verify sensor accepts 3.3 V trigger); echo through a suitable 5-to-3.3 V level shifter to GPIO23. Verify levels before connecting. No servo wiring or output is used. Do not assume the board's 3.3 V supply can power an eventual servo.

Copy `wifi_secrets.h.example` to `wifi_secrets.h`, put local Wi-Fi credentials there, and keep it untracked. The sketch includes a 10 us trigger pulse, 30 ms echo timeout, mm conversion using an approximate sound speed, and a valid range of 20..4000 mm. Each request samples once; device sequence increments even on invalid readings. A random boot ID distinguishes sessions; uptime is not synchronized to the host. Wi-Fi reconnect is attempted every five seconds without blocking the main loop.

Firmware compilation, upload, voltage measurements, and physical sensing are UNVERIFIED. The program does not flash anything. Review your existing firmware before manually compiling or uploading with a board-appropriate Arduino environment. The HTTP endpoint is plaintext on a trusted bench LAN, not an Internet service.

```powershell
python -m causalbench.cli capture --url http://DEVICE_IP/reading --count 30 --interval-ms 200 --output data/capture.json
python -m causalbench.cli run --trace data/capture.json --output data/capture.bundle.json
```

In the dashboard choose captured-input mode and Import trace. The mode explains the CLI capture workflow; there is no direct browser device connection. The URL, count, and interval are configurable. A request has a two-second timeout and 4096-byte response cap. Errors preserve a missing event and truncated diagnostic, then polling continues. Poll period includes request duration plus the requested sleep, not fixed-rate scheduling. Full device raw JSON is retained where decodable, including partial readings. Outcome correctness remains Unknown for real captures.

Future servo work: implement the Actuator protocol, obtain an appropriate external supply and common ground, check current and signal compatibility, add explicit enablement and an emergency stop, define what PULSE means mechanically, and measure latency and settling with the actual equipment. `PhysicalActuator(enabled=True)` currently raises NotImplementedError. That is an interface reservation, not implemented servo support.


## Version 2.0 dashboard recording

The dashboard now has Live sensor recording under Research tools. Select HTTP device and supply your reading endpoint; start, inspect diagnostics, then snapshot the rolling buffer into an experiment. Mock mode is explicitly synthetic and requires no hardware. Captured-input mode at the top still accepts imported traces. No actuator is connected or enabled by either path.

The dashboard recorder response cap is 16 KB, accepts optional auxiliary streams with explicit supported units, and bounds its rolling buffer by count and approximately 1.5 MB. It retains device uptime separately from its host request-start sampling estimate. No device clock synchronization is claimed. A real loopback HTTP sensor stand-in is tested, but the ESP32 sketch and physical circuit remain unverified.
