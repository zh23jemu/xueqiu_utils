import json
import logging
import re

from datetime import datetime

import requests


def read_token() -> str:
    """
    Read the token from the token file.

    This method reads the token from the token file and returns it.

    Returns:
        str: The token read from the token file.
    """
    with open('xq_item\\token.txt', 'r') as f:
        return f.read().strip()


def get_http_response(token, url):
    """
    Get HTTP response from the specified URL.

    This method sends a GET request to the specified URL and returns the response.

    Parameters:
    - url (str): The URL to which the request is sent.

    Returns:
    - requests.Response: The HTTP response from the specified URL.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:60.0) Gecko/20100101 Firefox/60.0',
        'Cookie': token,
        'Content-Type': 'application/json'
    }

    r = requests.get(url, headers=headers)

    return json.loads(r.text)


def conv_timestamp(ts):
    """
    Convert timestamp to datetime object.
    
    This function converts a Unix timestamp in milliseconds to a datetime object.
    The input timestamp is divided by 1000 because the input is in milliseconds
    while the datetime.fromtimestamp() function expects seconds.
    
    Parameters:
    - ts (int or float): Unix timestamp in milliseconds
    
    Returns:
    - datetime: A datetime object representing the timestamp
    """
    t = datetime.fromtimestamp(ts / 1000)
    return t


class Cube:
    CUBE_PATTEN = r"^ZH\d{6,7}$"
    CUBE_INFO_PATTERN = r"SNB\.cubeInfo = {.*}"
    CUBE_POSITION_URL = 'https://xueqiu.com/P/'
    CUBE_REBALANCE_URL = 'https://xueqiu.com/cubes/rebalancing/history.json?cube_symbol='
    CUBE_ALLDATA_URL = 'https://xueqiu.com/cubes/nav_daily/all.json?cube_symbol='

    def __init__(self, cube_id):
        """
        Initialize Cube object.

        Parameters:
        - cube_id (str): ID used to uniquely identify a cube.

        The Cube object sets properties such as cube_id, cube_type, and position_url during initialization, and initializes a logger.
        """
        # Convert the input cube_id to uppercase and assign it to the instance attribute to ensure ID uniformity and case insensitivity
        self.cube_id = cube_id.upper()

        self.token = read_token()

        # Build the cube location URL based on cube_id for subsequent access or reference to the cube's location information
        self.position_url = self.CUBE_POSITION_URL + self.cube_id
        self.alldata_url = self.CUBE_ALLDATA_URL + self.cube_id
        self.rebalance_url = self.CUBE_REBALANCE_URL + self.cube_id

        # Initialize a logger to record cube-related operation information, including log name and log level parameters
        self.logger = logging.Logger("Cube")
        self.logger.setLevel(logging.INFO)

    def get_status(self) -> int:
        """
        Verify whether the cube_id exists and is active.

        This method checks whether the cube_id is valid by accessing the Snowball website 
        and verifying the existence and activity status of the specified portfolio.

        Returns:
            int: Status code indicating cube validation result:
                 0 - Cube exists and is active
                 1 - Cube ID format is invalid
                 2 - Cube does not exist
                 3 - Cube is closed or inactive
                 9 - Other error occurred
        """

        # Check whether the cube_id is in the correct format
        if not re.match(self.CUBE_PATTEN, self.cube_id):
            self.logger.error("Cube ID is in invalid format.")
            return 1

        r = get_http_response(self.token, self.alldata_url)
        # print(r)

        # check type of r
        if type(r) == dict:
            # Check whether the cube exists
            if int(r['error_code']) == 20809:
                self.logger.error("Cube does not exist.")
                return 2
            return 9

        else:
            # some cubes closed the same day it created, then the list is empty.
            if len(r) == 0:
                self.logger.error("Cube closed.")
                return 3
            else:
                # Get the last day value had been updated
                last_date = datetime.strptime(r[0]['list'][-1]['date'], '%Y-%m-%d')
                today = datetime.today()
                date_diff = (today - last_date).days
                if date_diff > 10:
                    self.logger.error("Cube closed.")
                    return 3
                else:
                    self.logger.info("Cube exists.")
                    return 0

    def get_rebalance(self):
        """
        Get rebalancing history of the cube.
        
        This method retrieves the rebalancing history data from Snowball website
        by accessing the rebalancing history API endpoint.
        
        Returns:
            list: A list of rebalancing records if successful, None if failed to get data.
                  Each record contains details about a specific rebalancing event.
        """
        r = get_http_response(self.token, self.rebalance_url)
        try:
            rebalance = r['list']
            return rebalance
        except json.JSONDecodeError:
            self.logger.error("Failed to get cube rebalances.")

    def get_specific_day_rebalance(self, date):
        """
        Get specific day's successful user-initiated rebalancing records.
        
        This method filters the rebalancing history to find records that:
        1. Were created on the specified date
        2. Are user-initiated (category is 'user_rebalancing')
        3. Have success status
        
        Parameters:
        - date (str): The target date in 'YYYYMMDD' format to filter rebalancing records
        
        Returns:
            list: A list of successful user-initiated rebalancing records for the specified date.
                  Returns an empty list if no matching records found.
        """
        specific_day_rebalance = []

        rebalance = self.get_rebalance()
        # Filter out item with category is "sys_rebalancing"
        rebalance = list(filter(lambda x: x['category'] == 'user_rebalancing', rebalance))
        # Filter item with status is "success"
        rebalance = list(filter(lambda x: x['status'] == 'success', rebalance))

        if rebalance:
            for item in rebalance:
                rebalance_date = conv_timestamp(item['updated_at']).strftime('%Y%m%d')
                if date == rebalance_date:
                    specific_day_rebalance.append(item)
        return specific_day_rebalance
