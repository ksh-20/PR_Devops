import requests
from requests.auth import HTTPBasicAuth
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from core.config import AZURE_BASE_URL, AZURE_COLLECTION, AZURE_PAT


def fetch_webhooks():
    try:
        url = f"{AZURE_BASE_URL}/{AZURE_COLLECTION}/_apis/hooks/subscriptions?api-version=7.1-preview.1"
        auth = HTTPBasicAuth("", AZURE_PAT)

        response = requests.get(url=url, auth=auth, verify=False)

        if response.status_code != 200:
            return {
                "success" : False,
                "message" : response.text
            }
        
        return {
            "data" : response.json()
        }

    except Exception as e:
        return {
            "success" : False,
            "message" : e
        }