#!/usr/bin/env python3
#===============================================================================
'''
Runs rtlamr to watch for AMR broadcasts from power meter. If meter id
is on the list, usage is sent to 'PREFIX/{meter id}' topic on the MQTT broker specified in settings.

METERS_ARR = A Python list of dictionary entries for each meter to monitor where each entery is of form:
    {"msgtype": <message type> "id": <meter id>, "name": "<meter name>", "reading_field": <name of field to read>, "multiplier": <float>, "other_fields": [<list>], "retain": true|false}}

MQTT_HOST - name or IP address of MQTT broker (string)
MQTT_PORT - port to access MQTT broker (int)
MQTT_USER - user name (string, optional)
MQTT_PASSWORD - password (string, optional)
MQTT_TOPIC_PREFIX - prefix under which all meters will publish their messages (path-like string)
MQTT_RETAIN_DEFAULT - default value on whether to retain MQTT topics (true/false)
   NOTE: If no authentication, leave MQTT_USER and MQTT_PASSWORD empty

RTL_TCP = Path to 'rtl_tcp' executable
RTL_AMR = Path to 'rtlamr' executable

CENTERFREQ = Center frequency for rtl_tcp (default is 912.6 MHz)(string)

PUBLISH_DUPLICATES - Publish new messages that are duplicates of last message to the meter (True/False)

OUTLIER_PERCENT - Minimum percent change between readings to be considered a faulty reading (set to '' or False to ignore)
OUTLIER_ABSOLUTE - Minimum absolute change (after multiplier correction) between readings to be considered a faulty reading (set to '' or False to ignore)

DEFAULT_MSGTYPE - Default message type if not specified (can be overriden per meter)
DEFAULT_MULTIPLIER - Default multiplier for readings (can be overriden per meter)

Note: All meter, mqtt, and other variables are set in the companion file `settings.py

***NOTE*** Based on original version by: Ben Johnson: https://github.com/ragingcomputer/amridm2mqtt
KEY ADDITIONS include ability to:
    - Mix and match all the  message types supported by 'rtlamr' from multiple meters
    - Specify MQTT_TOPIC_PREFIX
    - Specify or use default field for reading or any given meter and message type
    - Specify user-friendly name for the meter topic (in addition to the number)
    - Specify multiplier on a per meter basis (and to set a default)
    - Specify percentage and absolute deviations to identify and reject outliers
    - Specify whether to publish unchanged (i.e., duplicate messages)
    - Publish additional fields beyond just the core 'consumption' reading
    - Specify whether to 'retain' messages by meter (and to set a default)
    - Specify 'rtlamr' center frequency
    - Set debug level for more debug details and granularity

Ver 1.5 (August 2024)
Jeffrey J. Kosowsky
'''
#===============================================================================
import os
import subprocess
import signal
import sys
import time
import json
import paho.mqtt.publish as publish

import settings
#===============================================================================
rtltcp = None
rtlamr = None

DEBUG = os.environ.get('DEBUG', '')
if not DEBUG:
    DEBUG = 0
elif  DEBUG not in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']:
    DEBUG = 1
DEBUG = int(DEBUG)

#===============================================================================

def main():
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    #Convert array of Meters to dictionary, indexed by meter id
    METERS_DICT = {}
    for meter in settings.METERS_ARR:
        msgtype = meter.get('msgtype', settings.DEFAULT_MSGTYPE).lower()
        METERS_DICT[meter['id']] = {
            'msgtype': msgtype,
            'name': meter.get('name', ''),
            'reading_field': meter.get('reading_field', settings.MSGTYPE_DICT[msgtype]["reading_field"]),
            'multiplier': meter.get('multiplier', settings.DEFAULT_MULTIPLIER),
            'other_fields': meter.get('other_fields', []),
            "retain": meter.get('retain', settings.MQTT_RETAIN_DEFAULT)
        }

    if not METERS_DICT:
        print("No meters specified properly... Check 'METERS_DICT' in 'settings.py'", file=sys.stderr)

    MSGTYPES = ','.join(set(value['msgtype'] for value in METERS_DICT.values() if 'msgtype' in value)) #Set assures unique
    ID_FIELDS = list(set(value['id'] for value in settings.MSGTYPE_DICT.values())) #List of fields where id numbers can be found

    if settings.MQTT_USER and settings.MQTT_PASSWORD:
        auth = {'username':settings.MQTT_USER, 'password':settings.MQTT_PASSWORD}
    else:
        auth = None        

    #Start the rtl_tcp program
    global rtltcp
    rtltcp = subprocess.Popen([settings.RTL_TCP + " > /dev/null 2>&1 &"], shell=True,
                              stdin=None, stdout=None, stderr=None, close_fds=True)
    time.sleep(5)
    print(f'PID: {rtltcp.pid}')

    # start the rtlamr program.
    rtlamr_cmd = [settings.RTLAMR, f'-centerfreq={settings.CENTERFREQ}', f'-msgtype={MSGTYPES}', '-format=json']
    global rtlamr
    rtlamr = subprocess.Popen(rtlamr_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True) #Combnie stderr with stdout

    if settings.OUTLIER_PERCENT:
        OUTLIER_PMAX = 1 + settings.OUTLIER_PERCENT/100
        OUTLIER_PMIN = 1 - settings.OUTLIER_PERCENT/100
    else:
        OUTLIER_PMAX = ''

    OUTLIER_ABS = settings.OUTLIER_ABSOLUTE

    while True: #Loop through reading AMR messages sequentially
        try:
            amr_line = rtlamr.stdout.readline().strip()

            if amr_line.endswith("Error reading samples:  EOF"):
                print(f'Error: {amr_line}', file=sys.stderr)
                shutdown(None, None)

            if amr_line[0] != '{': #Not a JSON string
                continue

            debug_print(4, amr_line)

            amr_json = json.loads(amr_line)
            timestamp = amr_json["Time"] #Not used currently except for debug
            message = amr_json["Message"]
            meter_id, id_field = get_id(message, ID_FIELDS)

            if meter_id not in METERS_DICT: #Not watching this meter
                continue

            meter_msgtype = METERS_DICT[meter_id]['msgtype']
            meter_id_field = settings.MSGTYPE_DICT[meter_msgtype]['id']
            if meter_id_field != id_field: #Message type mismatch between message and message type specified in settings.py
                #NOTE: Some meters might send out 2 different message types for the same meter (e.g., 'scm' & 'idm') so we will only return the specified one
                debug_print(2, f'MISMATCH: {meter_id} [meter_id_field|{id_field}] {amr_line}')
                continue

            reading_field = METERS_DICT[meter_id].get('reading_field', '')
            reading = message[reading_field];
            multiplier = METERS_DICT[meter_id]['multiplier']
            if multiplier != 1:
                reading *= multiplier
            other_fields = [
                f'"{key}": "{message[key]}"' if not isinstance(message[key], (int, float)) else f'"{key}": {message[key]}' #Quote if non-number
                for key in METERS_DICT[meter_id]['other_fields'] if key in message #Only include if key present in message
            ]

            debug_print(3, f'meter_id={meter_id}\treading={reading}\tother_fields={other_fields}')

            reading_old = METERS_DICT[meter_id].get('reading_old', '')
            other_fields_old = METERS_DICT[meter_id].get('other_fields_old', [])
            if reading == reading_old and other_fields == other_fields_old:
                continue #Don't rebroadcast old readings

            if reading_old: #Compare to previous reading to see if this is a spurious, out-of-bounds message
                if (OUTLIER_PMAX and (reading > OUTLIER_PMAX * reading_old or reading < OUTLIER_PMIN * reading_old)) \
                   or (OUTLIER_ABS and abs(reading - reading_old) > OUTLIER_ABS): #Out of percentage or absolute bounds
                    print(f'Seemingly erroneous reading: meter={meter_id} current:{reading}\tprevious:{reading_old}')
                    continue #Don't record erroneous large positive or negative changes

            METERS_DICT[meter_id]['reading_old'] = reading
            METERS_DICT[meter_id]['other_fields_old'] = other_fields

            meter_name = METERS_DICT[meter_id]['name']
            if meter_name:
                meter_name += '-'
            mqtt_topic = f'{settings.MQTT_TOPIC_PREFIX}/{meter_name}{str(meter_id)}'

            fields_list = [f'"{reading_field}":{reading}'] + other_fields
            mqtt_payload = '{' + ','.join(fields_list) + '}'

            retain = METERS_DICT[meter_id]['retain']

            send_mqtt(auth, mqtt_topic, mqtt_payload, retain)
            debug_print(1, f'[{timestamp}] {mqtt_topic}\t{mqtt_payload} [retain={retain}]')

        except Exception as e:
            debug_print(1, 'Exception squashed! [{}] {}: {}', amr_line, e.__class__.__name__, e)
            time.sleep(1)

#===============================================================================
#FUNCTIONS

#Get id from message trying the fields in ID_FIELDS
def get_id(message, ID_FIELDS):
    for key in ID_FIELDS:
        if key in message:
            return message[key], key
    raise KeyError(f'None of the keys {ID_FIELDS} found in the message')

#Send data to MQTT broker defined in settings
def send_mqtt(auth, topic, payload, retain):
    try:
        publish.single(topic, payload=payload, qos=1, hostname=settings.MQTT_HOST, port=settings.MQTT_PORT, auth=auth, retain=retain)
	#NOTE: Don't retain MQTT messages because may be out of date
    except Exception as ex:
        print("MQTT Publish Failed: " + str(ex), file=sys.stderr)

#Uses signal to shutdown and hard kill opened processes and self
def shutdown(signum, frame):
    global rtlamr, rtltcp
    try:
        os.killpg(os.getpgid(rtltcp.pid), signal.SIGTERM) #Note rtl_tcp uses a wrapper which generates another shell... so terminate the whole group
        rtlamr.send_signal(signal.SIGTERM)
        time.sleep(1)
        os.killpg(os.getpgid(rtltcp.pid), signal.SIGKILL) #Note rtl_tcp uses a wrapper which generates another shell... so kill the whole group
        rtlamr.send_signal(signal.SIGKILL)
    except Exception as e:
        print(f"Exception in shutdown: {e}", file=sys.stderr)
    finally:
        sys.exit(0)

#Debug print
def debug_print(level, message, *args, **kwargs):
    if DEBUG >= level:
        if isinstance(message, str) and args:
            # Format the message if args are provided
            message = message.format(*args)
        print(message, **kwargs, file=sys.stderr)

#===============================================================================
if __name__ == "__main__":
    main()

# Local Variables:
# mode: Python;
# tab-width: 2
# End:
