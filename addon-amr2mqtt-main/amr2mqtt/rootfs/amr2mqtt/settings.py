#Settings file for `amr2mqtt.py` script (v1.5)
METERS_ARR = []
# Above should be an array of dictionary entries of form containing configuration data for each meter you want to track.
# {"id": NNNNN, "msgtype": <message type>, "name": <Desired meter name>, "reading_field": <Name of field with reading>, "multiplier": NNNN, "other_fields": <list of optional other fields to publish>}, retain: <True/False, optional>}
#
# where:
#    id = numerical id number of the meter
#    msgtype = scm|scm+|idm|netidm|r900|r900bcd (optional, default = scm)
#    name = user-defined name for the meter (can be a path relative to MQTT_PREFIX) (optional, default = "")
#    reading_field = name for the meter quantity as appears in the json output from rtlamr (optional, set to defaults per msgtype)
#    multiplier = factor to multiply the raw numerical output (optional, default = DEFAULT_MULTIPLIER)
#                 (e.g., use 1000 to convert meter reading from kWh to Wh)
#    other_fields = optional list of other fields to publish
#    retain = Whether to retain MQTT messages on the broker (True/False) (optional, default = MQTT_RETAIN_DEFAULT)
#
#    NOTE: it can be important to specify the message type, since some meters send out multiple message types for the same meter
#    NOTE: if you use the defaults, you only need to specify: 'id' and msgtype (and for DEFAULT_MSGTYPE, only the 'id'
#
# Examples:
#	{"id": 60210816},
#	{"id": 60210816, "name": "MyMeter-SCM"},
#	{"id": 60210816, "msgtype": 'scm', "name": "MyMeter-SCM", "reading_field": "Consumption", "multiplier": 1},
#	{"id": 1550158635, "msgtype": 'scm+', "name": "Gas-SCMplus", "reading_field": "Consumption", "multiplier": 1},
#	{"id": 25808139, "msgtype": 'IDM', "name": "Electric-IDM", "reading_field": "LastConsumptionCount", "multiplier": 1000, "retain": True},
#   {"id": 1576312494, "msgtype": 'r900', "name": "Water-R900", "reading_field": "Consumption", "multiplier": 0.1, "other_fields": ["Leak", "LeakNow"]},

## MQTT Server settings
# MQTT_HOST - name or IP address of MQTT broker (string)
# MQTT_PORT - port to access MQTT broker (int)
# MQTT_USER - user name (string, optional)
# MQTT_PASSWORD - password (string, optional)
#     NOTE: If no authentication, leave MQTT_USER and MQTT_PASSWORD empty
# MQTT_TOPIC_PREFIX - prefix under which all meters will publish their messages (path-like string)
# MQTT_RETAIN_DEFAULT - default value on whether to retain MQTT topics (True/False)


MQTT_HOST = '127.0.0.1'
MQTT_PORT = 1883
MQTT_USER = ''
MQTT_PASSWORD = ''
MQTT_TOPIC_PREFIX = 'home/meters'
MQTT_RETAIN_DEFAULT = False

# Path to rtl_tcp
RTL_TCP = '/usr/bin/rtl_tcp'

# Path to rtlamr
RTLAMR = '/usr/local/bin/rtlamr'

# Centerfreq for 'rtlamr' (default is 912.6 MHz)
CENTERFREQ = '912.6M'

PUBLISH_DUPLICATES = False  #Publish new messages that are duplicates of last message to the meter (True/False)

OUTLIER_PERCENT = 15 #Minimum percent change between readings to be considered a faulty reading (set to '' or False to ignore)
OUTLIER_ABSOLUTE = 250 #Minimum absolute change (after multiplier correction) between readings to be considered a faulty reading (set to '' or False to ignore)

DEFAULT_MSGTYPE = 'scm' #Default message type if not specified (can be overriden per meter)
DEFAULT_MULTIPLIER = 1 #Default multiplier for readings (can be overriden per meter)

#Dictionary of default 'id' and 'reading_field' for each message type [This should in general not need to be changed
MSGTYPE_DICT = { #Defaults for various message types
    'scm': {"id": 'ID', "reading_field": "Consumption"},
    'scm+': {"id": 'EndpointID', "reading_field": "Consumption"},
    'idm': {"id": 'ERTSerialNumber', "reading_field": "LastConsumptionCount"},
    'netidm': {"id": 'ERTSerialNumber', "reading_field": "LastConsumptionCount"},
    'r900': {"id": 'ID', "reading_field": "Consumption"},
    'r900bcd': {"id": 'ID', "reading_field": "Consumption"},
}

#===============================================================================
# Local Variables:
# mode: Python;
# tab-width: 2
# End:
