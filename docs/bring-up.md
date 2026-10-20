# Bring-up and hardware checks

## WT32-ETH01

- Power input is 5 V from onboard MP1584.
- The 3.3 V supply is regulated on the WT32-ETH01 module.
- On 2026-10-20, powering from the Alarm & Roof Gateway board did not always start the ESP32 without a manual pulse of EN to GND. Check MP1584 output rise time, 3.3 V at the module and EN signal. Consider a power-on reset delay or reset supervisor **after measuring** the startup waveforms.
- GPIO0 to GND plus a reset enters UART download mode. Remove GPIO0-GND for normal boot.
- USB-UART adapter detected as PL2303 (VID 067B, PID 2303), macOS port `/dev/cu.usbserial-210`. Manual bootloader reset and `esptool --before no-reset ... chip-id` successfully established communication.

## Provisional schematic assignments (verify against physical module and PCB)

- GPIO4 — CPC1035N contactor drive
- GPIO15 — BC817 / Omron G6K-2F-Y coil control (ESP32 strapping pin: verify boot levels)
- GPIO14 — pulled-up alarm input
- GPIO35 and GPIO36 — ETOR moisture electrode ADC channels
- DS18B20 line — schematic symbol routes through TXD / GPIO17; physical availability must be checked
- ETOR electrode excitation — schematic names CFG / 485_EN suggest GPIO32 / GPIO33, but this conflicts with earlier module pin availability notes. Verify before using.

No wet/dry thresholds or automatic heating decisions should be assumed validated until the ETOR readings are calibrated.
