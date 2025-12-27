#!/usr/bin/env python3

import asyncio
from datetime import datetime
import logging

from aiohttp import ClientSession
from api.api import AnkerSolixApi
from api.mqtt import AnkerSolixMqttSession
from api.mqtt_pps import SolixMqttDevicePps
from api.mqtttypes import DeviceHexData
import common

_LOGGER: logging.Logger = logging.getLogger(__name__)
CONSOLE: logging.Logger = common.CONSOLE


mqtt_session = None
mqttdevice = None
battery_max=60
battery_min=55

def print_message(
        session: AnkerSolixMqttSession,
        topic: str,
        message: any,
        data: bytes,
        model: str,
        *args,
        **kwargs,
    ) -> None:
    """Print received MQTT message."""
    CONSOLE.info(f"MQTT Message Received - Topic: {topic}, Message: {message}")
    #hd = DeviceHexData(model=model or "", hexbytes=data)
    #CONSOLE.info(f"Parsed Data: {hd}")
    #CONSOLE.info(hd.decode())
    global mqtt_session
    global mqttdevice
    global battery_max
    global battery_min
    col1 = 25
    col2 = 25
    col3 = 25
    #for sn, device in mqtt_session.mqtt_data.items():
        #CONSOLE.info(f"{' ' + sn + ' (' + "A1790" + ') ':-^100}")
        # fields = []
        # for key, value in device.items():
        #     # convert timestamps to readable data and time for printout
        #     if "timestamp" in key and isinstance(value, int):
        #         value = datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
        #     if key != "topics":
        #         fields.append((key, value))
        #     if len(fields) >= 2:
        #         # print row
        #         CONSOLE.info(
        #             f"{fields[0][0]:<{col1}}: {fields[0][1]!s:<{col2}} {fields[1][0]:<{col3}}: {fields[1][1]!s}"
        #         )
        #         fields.clear()
        # if fields:
        #     CONSOLE.info(f"{fields[0][0]:<{col1}}: {fields[0][1]!s:<{col2}}")
        # CONSOLE.info("-" * 100)
        # CONSOLE.info(f"battery_soc: {device["main_battery_soc"]}%")
        # soc = int(device["main_battery_soc"])




async def main():
    global mqtt_session
    global mqttdevice
    """Example of controlling A1790P device via MQTT."""
    async with ClientSession() as websession:
        # Initialize API
        myapi = AnkerSolixApi(
            common.user(), common.password(), common.country(), websession, _LOGGER
        )

        # Update device information
        await myapi.update_sites()
        await myapi.update_device_details()

        # Find A1790P device
        device_sn = None
        device_dict = None
        for sn, device in myapi.devices.items():
            if device.get("device_pn") in ["A1790"]:
                device_sn = sn
                device_dict = device
                CONSOLE.info(f"Found {device.get("device_pn")} device: {sn}")
                break

        mqttdevice = SolixMqttDevicePps(api_instance=myapi, device_sn=device_sn)

        # Start MQTT session for real-time data
        mqtt_session = await myapi.startMqttSession()
        if not mqtt_session:
            CONSOLE.info("Failed to start MQTT session")
            return
        
        loop = asyncio.get_running_loop()

        # Example commands using F3800 wrapper methods
        try:
            while(mqtt_session.client.is_connected()):
                # CONSOLE.info("\nGenerating AC output ON")
                # await mqttdevice.set_ac_output(enabled=True)
                # await asyncio.sleep(1)

                prefix = mqtt_session.get_topic_prefix(deviceDict=device_dict)
                CONSOLE.info(f"Subscribing to topic prefix: {prefix}#")
                topics = set()
                topics.add(f"{prefix}#")
                trigger_devices = set()
                #trigger_devices.add(device_sn)


                poller_task = loop.create_task(
                    mqtt_session.message_poller(
                        topics=topics,
                        trigger_devices=trigger_devices,
                        msg_callback=print_message,
                        timeout=60,
                    )
                )

                await asyncio.sleep(2)  # Wait for subscription to complete

                if mqtt_session.status_request(
                    deviceDict=device_dict,
                    wait_for_publish=2,
                ).is_published():
                    CONSOLE.info(
                        f"Published immediate status request, status message(s) should appear shortly..."
                    )

                # if mqtt_session.realtime_trigger(
                #     deviceDict=device_dict,
                #     timeout=60,
                #     wait_for_publish=2,
                # ).is_published():
                #     CONSOLE.info(
                #         f"Published one time real time trigger request, message frequency should appear shortly..."
                #     )
                data = mqtt_session.mqtt_data.get(device_sn)
                if data:
                    CONSOLE.info("-" * 100)
                    CONSOLE.info(f"battery_soc: {data["main_battery_soc"]}%")
                    CONSOLE.info(f"ac switch: {data["ac_output_power_switch"]}")
                    soc = int(data["main_battery_soc"])
                    ac_switch = int(data["ac_output_power_switch"])


                    if soc >= battery_max and ac_switch == 0:
                        CONSOLE.info(f"battery_soc >= {battery_max}%, turning ON AC output")
                        await mqttdevice.set_ac_output(enabled=True)
                    elif soc <= battery_min and ac_switch == 1:
                        CONSOLE.info(f"battery_soc <= {battery_min}%, turning OFF AC output")
                        await mqttdevice.set_ac_output(enabled=False)

                await asyncio.sleep(30)  # Wait to receive messages

                # Set Real-Time Data ON (not implemented in wrapper yet)
                # You may add a wrapper for this in the future


        except Exception as e:  # pylint: disable=broad-exception-caught  # noqa: BLE001
            CONSOLE.error(f"Error during device control: {e}")
        finally:
            # Clean up
            if mqtt_session and mqtt_session.client:
                mqtt_session.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        CONSOLE.info("\nKeyboard interrupt")
    except Exception as err:
        CONSOLE.error(f"Error: {err}")
