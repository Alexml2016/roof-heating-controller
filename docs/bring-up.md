# Bring-up and hardware checks

## WT32-ETH01

- Power input is 5 V from onboard MP1584.
- The 3.3 V supply is regulated on the WT32-ETH01 module.
- On 2026-10-20, an early bench test observed that ESP32 sometimes required an EN-to-GND pulse after power-up. **On 2026-10-21 the user confirmed automatic startup on power application works on the current assembled unit.** The earlier symptom is no longer reproducible under the reported test conditions. Document number of cold starts and input power ramp before final acceptance; brownout and repeated power interruption tests remain separate.
- GPIO0 to GND plus a reset enters UART download mode. Remove GPIO0-GND for normal boot.
- USB-UART adapter detected as PL2303 (VID 067B, PID 2303), macOS port `/dev/cu.usbserial-210`. Manual bootloader reset and `esptool --before no-reset ... chip-id` successfully established communication.

## Provisional schematic assignments (verify against physical module and PCB)

- GPIO4 — CPC1035N contactor drive
- GPIO15 — BC817 / Omron G6K-2F-Y coil control (ESP32 strapping pin: verify boot levels)
- GPIO14 — pulled-up alarm input
- GPIO35 and GPIO36 — ETOR moisture electrode ADC channels
- **CN3 DS18B20 1-Wire GPIO17 verified with two simultaneous devices on 2026-10-21:** 0x9a000000b176a128 = `Boiler temperature IN` (current firmware default 60s); 0x250000005219a128 = `Boiler temperature OUT` (10s). Both produced ~23.1°C readings in ESPHome 2026.9.1
- ETOR electrode excitation — schematic names CFG / 485_EN suggest GPIO32 / GPIO33, but this conflicts with earlier module pin availability notes. Verify before using.

No wet/dry thresholds or automatic heating decisions should be assumed validated until the ETOR readings are calibrated.

## Confirmed live behavior (2026-10-21)

- ESPHome 2026.9.1 log reports two DS18B20s on GPIO17 and both publish temperature readings.
- GPIO15/K1 relay was verified switching ON/OFF after correcting D3 diode assembly orientation; **PCB silkscreen polarity fault PCB-001 remains open for production design correction**.
- ETOR resistor-bench measurements at 47kΩ and 100kΩ are consistent with the resistance estimation firmware (approximately 47.1kΩ and 102kΩ respectively); classification is intentionally `UNCALIBRATED` until testing the actual ETOR-55.
- The user has explicitly verified normal automatic boot at power application; long-duration and brownout/power-cycle counts have not been provided.
