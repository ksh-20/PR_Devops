import requests
from requests.auth import HTTPBasicAuth
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from core.config import AZURE_BASE_URL, AZURE_COLLECTION, AZURE_PAT

def fetch_projects():
    try:
        url = f"{AZURE_BASE_URL}/{AZURE_COLLECTION}/_apis/projects?api-version=7.2-preview.4"
        auth = HTTPBasicAuth("", AZURE_PAT)

        response = requests.get(url=url, auth=auth, verify=False)

        if response.status_code != 200:
            return {
                "success" : False,
                "message" : response.text
            }
        
        data = response.json()
        projects = []
        for project in data.get("value", []):
            projects.append({
                "name" : project.get("name", "")
            })

        result = {
            "success" : True,
            "count" : len(projects),
            "projects" : projects
        }

        return result
    
    except Exception as e:
        print("Error fetching projects", e)

        return {
            "success" : False,
            "message" : e
        }