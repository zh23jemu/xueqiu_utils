import json

from datetime import datetime

import requests


def read_token() -> str:
    """
    Read the token from the token file.

    This method reads the token from the token file and returns it.

    Returns:
        str: The token read from the token file.
    """
    with open('src\\token.txt', 'r') as f:
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
