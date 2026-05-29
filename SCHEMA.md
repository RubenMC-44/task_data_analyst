# Column Reference

Each CSV is one recording session from a rail-mounted laser system. The vehicle travels along a track while lasers mounted on the north and south sides of the vehicle operate, each supported by its own optics module, chiller, and safety interlocks. Sensor telemetry is recorded approximately once per second.

Throughout this document, `n` = north side, `s` = south side. The `1` suffix refers to the unit number on that side.

---

## 1. Time

| Column | Type | Description |
|---|---|---|
| `time_stamp` | timestamptz | Sample timestamp from the on-board clock (UTC, microsecond precision). This is the primary time axis. |

---

## 2. System health

Vital signs of the on-board computer driving the laser system.

| Column | Type | Unit | Description |
|---|---|---|---|
| `system_health_cpu` | float | % | CPU utilisation of the control computer. |
| `system_health_free_memory` | float | % | Free RAM remaining (lower = system under more memory pressure). |

---

## 3. GPS / positioning

Reported by the on-board GPS receiver.

| Column | Type | Unit | Description |
|---|---|---|---|
| `gps_lat` | float | ° | Latitude (WGS84). |
| `gps_lon` | float | ° | Longitude (WGS84). |
| `gps_speed` | float | m/s | Ground speed. |
| `gps_n_satellites` | int | count | Number of GPS satellites locked. 0 = no fix. |
| `gps_quality` | float | code | GPS fix-quality indicator (NMEA-style: 0 = invalid, 1 = standard fix, 2 = DGPS, etc.). |
| `gps_dilution_of_precision` | float | — | DOP (lower = more geometrically accurate fix). |

> A non-trivial portion of samples may have `gps_n_satellites = 0` (tunnels, station stops). Treat as missing position, not zero position.

---

## 4. Pneumatics & FPGA state

| Column | Type | Unit | Description |
|---|---|---|---|
| `blower_pressure` | float | mbar | Main blower pressure feeding the optics-window air-curtain system. |
| `compressor_pressure` | float | bar | Pneumatic compressor pressure (used for actuators & shielding). |
| `geo_objects` | int | **bitmask** | Geofence categories currently matched at the vehicle's GPS position. See *Geo objects bit layout* below. |
| `fpga_state` | int | enum | High-level operating mode of the on-board FPGA controlling the laser system. See *FPGA state values* below. |
| `interlock_sensors` | bigint | **bitmask** | State of each individual safety interlock sensor (doors, lids, windows, rail shields…). See *Interlock sensors bit layout* below. |

### Interlock sensors — bit layout

`interlock_sensors` is a 32-bit field. Bit *N* (LSB = bit 0) corresponds to one physical safety sensor on the vehicle. `1` = sensor closed/active (safe), `0` = open/inactive — **but verify the polarity against the data** before drawing conclusions.

| Bit | Sensor | Bit | Sensor |
|---:|---|---:|---|
| 0 | `n_main_optics_lid_1` | 16 | `s_main_optics_lid_1` |
| 1 | `n_main_optics_lid_2` | 17 | `s_main_optics_lid_2` |
| 2 | `n_protective_window_lid_1` | 18 | `s_protective_window_lid_1` |
| 3 | `n_protective_window_lid_2` | 19 | `s_protective_window_lid_2` |
| 4 | `n_rail_1` | 20 | `s_rail_1` |
| 5 | `n_rail_2` | 21 | `s_rail_2` |
| 6 | `n_light_lock_1` | 22 | `s_light_lock_1` |
| 7 | `n_light_lock_2` | 23 | `s_light_lock_2` |
| 8 | `n_light_lock_3` | 24 | `s_light_lock_3` |
| 9 | `n_light_lock_4` | 25 | `s_light_lock_4` |
| 10 | `n_side_shield_fs1` | 26 | `s_side_shield_fs1` |
| 11 | `n_side_shield_fs2` | 27 | `s_side_shield_fs2` |
| 12 | `n_side_shield_is1` | 28 | `s_side_shield_is1` |
| 13 | `n_side_shield_is2` | 29 | `s_side_shield_is2` |
| 14 | `n_shield_up_1` | 30 | `s_shield_up_1` |
| 15 | `n_shield_up_2` | 31 | `s_shield_up_2` |

The N and S blocks mirror each other: subtract 16 from any S-side bit to get its N-side counterpart.

### FPGA state values

| Value | Label | Meaning |
|---:|---|---|
| 0 | Sleep | System powered down / idle. |
| 1 | Boot | Booting up. |
| 2 | Stand-By | Powered and ready, but not operating. |
| 3 | Transport | Vehicle is moving between work sites; lasers inhibited. |
| 4 | Cleaning | Active operational mode — lasers cleaning the rail. |
| 5 | Service | System under maintenance. |

In this dataset only **`3` (Transport)** and **`4` (Cleaning)** appear. The split between the two is the cleanest way to separate "the rig is doing its job" from "the train is just driving."

### Geo objects — bit layout

`geo_objects` is a small bitmask describing what kinds of geofenced track features the vehicle is currently inside. Multiple bits can be set simultaneously.

| Bit | Feature | Bit | Feature |
|---:|---|---:|---|
| 0 | `all` (any feature present) | 8 | `crossing` |
| 1 | `track` | 9 | `bridge` |
| 2 | `area` | 10 | `lubricator` |
| 3 | `speed_max` | 11 | `access_pad` |
| 4 | `speed_min` | 12 | `detector` |
| 5 | `other` | 13 | *(unused)* |
| 6 | `manual` | 14 | `lubricator_est` |
| 7 | `switch` | | |

---

## 5. Laser n1 (north side, unit 1)

The actual laser delivering optical power onto the rail.

| Column | Type | Unit | Description |
|---|---|---|---|
| `laser_n1_main_status` | int | **bitmask** | Top-level rollup of laser health. Bit 0 = an alarm is currently active. Bit 1 = a warning is active. So values are `0` (clean), `1` (alarm), `2` (warning), or `3` (both). |
| `laser_n1_measured_power` | float | W | Optical output power as measured at the laser head. |
| `laser_n1_humidity` | float | % RH | Relative humidity inside the laser enclosure. |

## 6. Laser s1 (south side, unit 1)

Mirror of section 5 for the south-side laser.

| Column | Type | Unit | Description |
|---|---|---|---|
| `laser_s1_main_status` | int | **bitmask** | See `laser_n1_main_status`. |
| `laser_s1_measured_power` | float | W | See `laser_n1_measured_power`. |
| `laser_s1_humidity` | float | % RH | See `laser_n1_humidity`. |

---

## 7. Optics modules (per side)

The optics module focuses the laser beam onto the rail surface. It rides on an actuator that can extend toward, or retract from, the rail.

| Column | Type | Unit | Description |
|---|---|---|---|
| `optics_to_rail_height_n1` | float | mm | Vertical distance from north-1 optics head to the rail surface. |
| `optics_to_rail_height_s1` | float | mm | Same, for south-1. |
| `optics_n_humidity` | float | % RH | Humidity inside the north optics enclosure. |
| `optics_s_humidity` | float | % RH | Humidity inside the south optics enclosure. |
| `optics_n_blower_pressure` | float | mbar | Air-curtain blower pressure for the north optics window (keeps debris off the lens). |
| `optics_s_blower_pressure` | float | mbar | Same, south side. |

---

## 8. Temperatures around each laser head

`top_pw` and `bottom_pw` = the protective windows above/below the optics path.
`lens_box` = the sealed lens housing.

| Column | Type | Unit | Description |
|---|---|---|---|
| `temp_n1_lens_box` | float | °C | Lens-box temperature, north-1. |
| `temp_n1_top_pw` | float | °C | Top protective-window temperature, north-1. |
| `temp_n1_bottom_pw` | float | °C | Bottom protective-window temperature, north-1. |
| `temp_s1_lens_box` | float | °C | Lens-box temperature, south-1. |
| `temp_s1_top_pw` | float | °C | Top protective-window temperature, south-1. |
| `temp_s1_bottom_pw` | float | °C | Bottom protective-window temperature, south-1. |

---

## 9. Chillers

Each laser has a chiller circulating coolant. The `main_circuit` cools the laser source itself.

| Column | Type | Unit | Description |
|---|---|---|---|
| `chiller_n1_main_circuit_temperature` | float | °C | Coolant temperature on the main circuit (north-1). |
| `chiller_n1_main_circuit_flow` | float | L/min | Coolant flow rate on the main circuit (north-1). |
| `chiller_n1_alarm` | bool | — | Any chiller alarm active (north-1). |
| `chiller_n1_on` | bool | — | Chiller currently powered on (north-1). |
| `chiller_s1_main_circuit_temperature` | float | °C | Same, south-1. |
| `chiller_s1_main_circuit_flow` | float | L/min | Same, south-1. |
| `chiller_s1_alarm` | bool | — | Same, south-1. |
| `chiller_s1_on` | bool | — | Same, south-1. |

---

## 10. Rail actuators & emission stops

The optics module slides on a rail-aligned actuator. `actuation_ms` is the time the actuator took on its last cycle. An `emission_stop` is set when emission was inhibited (safety event or end-of-stroke).

| Column | Type | Unit | Description |
|---|---|---|---|
| `n_rail1_actuation_ms` | float | ms | Last actuation duration for the north-side rail-1 actuator. |
| `s_rail1_actuation_ms` | float | ms | Same, south side. |
| `n1_emission_stop` | bool | — | Emission stop currently active on laser n1. |
| `s1_emission_stop` | bool | — | Emission stop currently active on laser s1. |

---

## Notes

- **Sampling cadence is not perfectly uniform.** Don't assume exactly 1 Hz — compute it from `time_stamp`.
- **Booleans appear as `t` / `f` strings** in the CSV (Postgres convention). Convert to actual booleans on load.
- **Many sensor columns can be `NULL`** (empty CSV cells) when the corresponding subsystem is offline or warming up. Plan for missing data.
- **N and S are independent and roughly symmetric** — comparing the two sides over the same time window is one of the most informative things you can do.
- **Status / alarm / interlock columns are coded integers or bitmasks**, not human-readable. State changes (i.e. transitions in time) are usually more interesting than the raw values.
