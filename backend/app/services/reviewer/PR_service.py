import json
import requests
from requests.auth import HTTPBasicAuth
import urllib3
import random
import difflib

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from core.config import AZURE_BASE_URL, AZURE_PAT, AZURE_COLLECTION, AZURE_PROJECT
from services.reviewer.repos_service import fetch_repos
from services.reviewer.LLM_review_service import review_pr
from services.reviewer.secrets_filter_service import sanitize_files

class AzurePRManager:
    def __init__(self):
        self.repo_id = None
        self.pr_id = None
        self.iteration_id = None
        self.auth = HTTPBasicAuth("", AZURE_PAT)
        self.project = AZURE_PROJECT

    def select_random_repo(self, repo_target=None):
        try:
            repos_data = fetch_repos(project=self.project)
            
            if isinstance(repos_data, str):
                try:
                    repos = json.loads(repos_data)
                except json.JSONDecodeError:
                    return {"success": False, "message": f"fetch_repos returned text, not JSON: {repos_data}"}
            else:
                repos = repos_data
            
            if isinstance(repos, dict) and "data" in repos:
                repos = repos["data"]
                
            if isinstance(repos, dict) and "value" in repos:
                repos = repos["value"]
                    
            if not isinstance(repos, list):
                return {"success": False, "message": f"Expected a list but got type {type(repos).__name__}"}
            
            if repo_target:
                for repo in repos:
                    if isinstance(repo, dict) and (repo.get("id") == repo_target or repo.get("name") == repo_target):
                        self.repo_id = repo["id"]
                        return {"success": True, "repo_id": self.repo_id}
                return {"success": False, "message": f"Specified repository '{repo_target}' not found."}
                
            repo_ids = [repo["id"] for repo in repos if isinstance(repo, dict) and "id" in repo]

            if not repo_ids:
                return {"success": False, "message": "No valid repository IDs found in data."}

            self.repo_id = random.choice(repo_ids)
            return {"success": True, "repo_id": self.repo_id}

        except Exception as e:
            return {"success": False, "message": str(e)}

    def fetch_prs(self, repo_target=None):
        try:
            if repo_target:
                res = self.select_random_repo(repo_target=repo_target)
                if not res["success"]:
                    return res
            elif not self.repo_id:
                res = self.select_random_repo()
                if not res["success"]:
                    return res

            url = f"{AZURE_BASE_URL}/{AZURE_COLLECTION}/{self.project}/_apis/git/repositories/{self.repo_id}/pullrequests?searchCriteria.status=active&api-version=7.1"
            response = requests.get(url=url, auth=self.auth, verify=False)

            if response.status_code != 200:
                return {"success": False, "message": response.text}
            
            data = response.json()
            
            if data.get("value"):
                self.pr_id = data["value"][0]["pullRequestId"]
            else:
                self.pr_id = None
            
            return {"success": True, "repo_id": self.repo_id, "pr_id": self.pr_id, "data": data}

        except Exception as e:
            return {"success": False, "message": str(e)}

    def fetch_latest_iteration(self):
        try:
            if not self.repo_id or not self.pr_id:
                return {"success": False, "message": "repo_id or pr_id missing."}

            url = f"{AZURE_BASE_URL}/{AZURE_COLLECTION}/{self.project}/_apis/git/repositories/{self.repo_id}/pullRequests/{self.pr_id}/iterations?api-version=7.1"
            response = requests.get(url, auth=self.auth, verify=False)
            response.raise_for_status()

            iterations = response.json().get("value", [])

            if not iterations:
                return {"success": False, "message": "No iterations found"}

            latest_iteration = max(iterations, key=lambda x: x["id"])
            self.iteration_id = latest_iteration["id"]
            
            return {"success": True, "latest_iteration_id": self.iteration_id}

        except requests.exceptions.HTTPError as e:
            return {"success": False, "message": f"Azure API Error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_changed_files(self):
        try:
            if not self.repo_id or not self.pr_id:
                return {"success": False, "message": "repo_id or pr_id missing."}

            if not self.iteration_id:
                res = self.fetch_latest_iteration()
                if not res.get("success"):
                    return res

            url = f"{AZURE_BASE_URL}/{AZURE_COLLECTION}/{self.project}/_apis/git/repositories/{self.repo_id}/pullRequests/{self.pr_id}/iterations/{self.iteration_id}/changes?api-version=7.1"
            response = requests.get(url, auth=self.auth, verify=False)
            response.raise_for_status()

            data = response.json()
            changed_files = []

            for change in data.get("changeEntries", []):
                item = change.get("item", {})
                changed_files.append({
                    "path": item.get("path"),
                    "change_type": change.get("changeType")
                })

            return {"success": True, "files": changed_files}

        except requests.exceptions.HTTPError as e:
            return {"success": False, "message": f"Azure API Error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"success": False, "message": str(e)}
        
    
    def get_pr_details(self):
        try:
            url = f"{AZURE_BASE_URL}/{AZURE_COLLECTION}/{self.project}/_apis/git/repositories/{self.repo_id}/pullRequests/{self.pr_id}?api-version=7.1"
            response = requests.get(url,auth=self.auth,verify=False)
            response.raise_for_status()
            data = response.json()
            source_commit = None
            target_commit = None
            if data.get("lastMergeSourceCommit") and data.get("lastMergeTargetCommit"):
                source_commit = data["lastMergeSourceCommit"].get("commitId")
                target_commit = data["lastMergeTargetCommit"].get("commitId")
            if not source_commit or not target_commit:
                iter_url = f"{AZURE_BASE_URL}/{AZURE_COLLECTION}/{self.project}/_apis/git/repositories/{self.repo_id}/pullRequests/{self.pr_id}/iterations?api-version=7.1"
                iter_resp = requests.get(iter_url, auth=self.auth, verify=False)
                iter_resp.raise_for_status()
                iterations = iter_resp.json().get("value", [])
                if iterations:
                    latest_iteration = max(iterations, key=lambda x: x["id"])
                    self.iteration_id = latest_iteration["id"]
                    source_commit = latest_iteration.get("sourceRefCommit", {}).get("commitId")
                    target_commit = latest_iteration.get("targetRefCommit", {}).get("commitId")
            if not source_commit or not target_commit:
                return {
                    "success": False,
                    "message": "Missing target identifiers. Run fetch_latest_iteration() first."
                }
            return {
                "success": True,
                "source_commit": source_commit,
                "target_commit": target_commit
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e)
            }
        
    def get_file_content(self, path, commit_id):
        try:

            url = f"{AZURE_BASE_URL}/{AZURE_COLLECTION}/{self.project}/_apis/git/repositories/{self.repo_id}/items"

            params = {
                "path": path,
                "versionDescriptor.version": commit_id,
                "versionDescriptor.versionType": "commit",
                "includeContent": "true",
                "api-version": "7.1"
            }

            response = requests.get(url,params=params,auth=self.auth,verify=False)

            response.raise_for_status()

            return response.text

        except Exception as e:
            print(f"Failed to fetch {path}: {e}")
            return None
        

    def generate_diff(self, old_content, new_content):
        diff = difflib.unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            fromfile="old",
            tofile="new",
            lineterm=""
        )

        return "\n".join(diff)
    

    def get_file_deltas(self):
        pr_details = self.get_pr_details()

        if not pr_details["success"]:
            return pr_details

        source_commit = pr_details["source_commit"]
        target_commit = pr_details["target_commit"]

        changes = self.get_changed_files()

        if not changes["success"]:
            return changes

        results = []

        for file in changes["files"]:
            path = file["path"]

            old_content = self.get_file_content(path,target_commit)

            new_content = self.get_file_content(path,source_commit)

            if old_content is None or new_content is None:
                continue

            diff = self.generate_diff(old_content,new_content)

            results.append({
                "path": path,
                "change_type": file["change_type"],
                "diff": diff
            })

        return {
            "success": True,
            "files": results
        }
    

    def review_current_pr(self):
        delta_result = self.get_file_deltas()

        if not delta_result["success"]:
            return delta_result
        
        sanitized_files = sanitize_files(delta_result["files"])
        print(sanitized_files)
        review_result = review_pr(sanitized_files)

        return review_result
    

    def post_review(self, review_text):
        try:
            if not self.repo_id or not self.pr_id:
                return {
                    "success": False,
                    "message": "repo_id or pr_id missing."
                }

            url = f"{AZURE_BASE_URL}/{AZURE_COLLECTION}/{self.project}/_apis/git/repositories/{self.repo_id}/pullRequests/{self.pr_id}/threads?api-version=7.1"

            formatted_review = f"""
            # AI Pull Request Review
            ---
            {review_text}
            ---
            <sub>Generated automatically using LLM.</sub>
            """

            payload = {
                "comments": [
                    {
                        "parentCommentId": 0,
                        "content": formatted_review,
                        "commentType": 1
                    }
                ],
                "status": 1
            }

            response = requests.post(url,json=payload,auth=self.auth,verify=False)

            response.raise_for_status()

            return {
                "success": True,
                "message": "Review posted successfully.",
                "data": response.json()
            }

        except requests.exceptions.HTTPError as e:
            return {
                "success": False,
                "message": f"{e.response.status_code}: {e.response.text}"
            }

        except Exception as e:
            return {
                "success": False,
                "message": str(e)
            }