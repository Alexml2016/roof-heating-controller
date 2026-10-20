# Roof Heating Controller — Alarm & Roof Gateway

ESPHome-based roof heating / alarm gateway using a WT32-ETH01 (ESP32) module. The board connects ETOR-55 roof moisture sensing, a DS18B20 temperature probe, an alarm input and contactor control to Home Assistant.

## Hardware

- WT32-ETH01 with ESP32 and Ethernet PHY
- MP1584 buck converter providing **5 V** to the WT32-ETH01; the module regulates 3.3 V internally
- ETOR-55 moisture sensor with separately switched heater, controlled via a G6K-2F-Y relay
- External roof-heating contactor driven via a CPC1035N output stage
- DS18B20 digital thermometer and a discrete alarm input

**Safety:** This controller is used near electrical heating equipment. Verify wiring, insulation, fuse protection, contactor/relay ratings and fail-safe behavior before energizing mains equipment. Current PCB, pin assignments, strapping pins and moisture calibration are **not yet signed off as production ready**.

## Repository layout

- `firmware/esphome/` — ESPHome firmware configuration (pending import from the local Mac)
- `hardware/altium/` — Altium source schematic and PCB (pending binary upload)
- `hardware/gerber/` — fabrication outputs only after fabrication review
- `docs/` — design notes and testing information
- `releases/` — optional tested firmware images

## Firmware migration

The current working firmware is located on the development Mac as `alarm-roof-gateway.yaml`, in the ESPHome directory of an earlier, unrelated project (`courtyard-access-controller`). **It has not yet been copied to this repository.** Copy only the Alarm & Roof Gateway files, not the courtyard intercom firmware.

The firmware has been temporarily configured for Wi-Fi instead of Ethernet during bring-up. Use `secrets.yaml.example` as a template for your *local* `secrets.yaml`; do not commit actual SSIDs/passwords, API encryption keys or OTA credentials.

Observed during bring-up: WT32-ETH01 needs manual EN reset after MP1584 power-up. Investigate 5 V → 3.3 V startup behavior and EN reset timing before unattended operation. GPIO0 needs to be released from GND after UART flashing.

## Source provenance

A dated Altium archive, `Altium_Alarm&Roof Gateway_2026-10-19.zip`, is available from the project's previous conversation. It contains `P1.schdoc` and `PCB1.pcbdoc`. Upload it under `hardware/altium/` (or extract the native project files) once the binary artifacts are transferred. No Gerber is included in that archive.

## State

Repository structure and publishing safeguards are being established. Do **not** assume any missing artifact or pin assignment has been verified merely because it is described here.
