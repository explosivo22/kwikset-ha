"""Constants for Kwikset Monitoring"""
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = 'kwikset'

POOL_ID = 'us-east-1_6B3uo6uKN'
CLIENT_ID = '5eu1cdkjp1itd1fi7b91m6g79s'
POOL_REGION = 'us-east-1'

CONF_API = 'conf_api'
CONF_HOME_ID = 'conf_home_id'
CONF_HOME_NAME = 'conf_home_name'
CONF_REFRESH_TOKEN = 'conf_refresh_token'
CONF_ACCESS_TOKEN = 'conf_access_token'
CONF_ID_TOKEN = 'conf_id_token'
CONF_CODE_TYPE = 'code_type'
CONF_REFRESH_INTERVAL = 'refresh_interval'
DEFAULT_REFRESH_INTERVAL = 30

CLIENT = 'client'