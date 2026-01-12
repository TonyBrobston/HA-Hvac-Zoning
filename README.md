# Home Assistant HVAC Zoning Integration

This integration transforms a standard central HVAC system into a **smart multi-zone climate control system**. By coordinating a central smart thermostat, individual temperature sensors, and smart vents (dampers), it allows for room-specific temperature targets and intelligent airflow management.



## 🚀 Key Features

* **Virtual Per-Area Thermostats**: Automatically creates a dedicated climate entity for every configured room. You can set the "Office" to 72°F and the "Master Bedroom" to 68°F independently.
* **Intelligent Vent Control**: Dynamically opens and closes smart vents based on the delta between a room's actual temperature and its specific target setpoint.
* **Central Thermostat Automation**: Optionally manages your central thermostat's setpoint to ensure the HVAC unit remains active until the furthest room reaches its goal.
* **Night Time Mode**: A specialized sleep schedule that prioritizes bedrooms. During "Bed Time," the system closes vents in unoccupied areas (like the kitchen or office) to reduce noise and maximize airflow to bedrooms.
* **Connectivity Awareness**: Designed to handle battery-powered vents by monitoring connectivity states, ensuring commands are sent effectively when devices wake up.

## 🛠️ Required Hardware

To use this integration, you need the following devices integrated into Home Assistant:

1.  **Smart Thermostat**: A central controller (e.g., Ecobee, Nest, or Z-Wave/Zigbee thermostat) to trigger the main HVAC unit.
2.  **Smart Vents/Dampers**: Any `cover` entity that acts as a vent (e.g., Flair, Keen, or DIY dampers).
3.  **Temperature Sensors**: At least one temperature sensor per zone to provide local feedback.



## ⚙️ How It Works

1.  **Sensing**: The integration monitors the local temperature sensors in each designated Area.
2.  **Logic**: It compares the local temperature against the **Virtual Thermostat** setpoint for that specific room.
3.  **Action**:
    * If a room requires heating/cooling, the **Smart Vent** opens.
    * If a room reaches its target, the **Smart Vent** closes to prevent over-conditioning and redirects air to other zones.
    * If **Control Central Thermostat** is enabled, the integration pushes a setpoint to the main house thermostat to keep the system running until all zones are satisfied.

## 📝 Installation & Configuration

1.  Copy the `hvac_zoning` folder to your `custom_components` directory.
2.  Restart Home Assistant.
3.  Go to **Settings > Devices & Services > Add Integration** and search for **HVAC Zoning**.
4.  Follow the multi-step configuration flow:
    * **Vents**: Assign smart vents to their respective areas.
    * **Sensors**: Assign temperature and connectivity sensors.
    * **Thermostat**: Select your primary central thermostat.
    * **Schedule**: Define your bedrooms and sleep/wake times for Night Time Mode.

---
*Note: Ensure your entities are explicitly assigned to Areas in Home Assistant (Settings -> Areas & Zones) so the configuration flow can auto-discover them.*

## Disclaimer

Use this software at your own risk. I accept no liability.
