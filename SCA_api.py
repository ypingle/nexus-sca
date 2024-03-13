import requests
import json
import os

def get_SCA_access_token(SCA_username, SCA_password, SCA_account, SCA_auth_url, proxy_servers=None):
    try:
        payload = {
            'username': SCA_username,
            'password': SCA_password,
            'acr_values': 'Tenant:' + SCA_account,
            'scope': 'sca_api',
            'client_id': 'sca_resource_owner',
            'grant_type': 'password'
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        response = requests.post(SCA_auth_url, headers=headers, data=payload, verify=False, proxies=proxy_servers)

        print('get_SCA_access_token - token = ' + response.text)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        access_token = response.json()['access_token']
        return access_token
    except requests.RequestException as e:
        print("Exception: Failed to get access token:", str(e))
        return ""

def SCA_get_project_latest_scan_id(access_token, project_name, SCA_api_url, proxy_servers=None):
    url = SCA_api_url + "/risk-management/projects?name=" + project_name

    try:
        payload = {}
        headers = {
        'Authorization': 'Bearer ' + access_token
        }

        response = requests.request("GET", url, headers=headers, data=payload, proxies=proxy_servers, verify=False)
        response_json = response.json()
    except Exception as e:
        print("Exception: SCA_get_project_latest_scan_id:", str(e))
        return ""
    else:
        print('SCA_get_project_latest_scan_id scan_id= ' + response_json['latestScanId'])
        return response_json['latestScanId']

def SCA_create_project(access_token, project_name, SCA_api_url, proxy_servers=None):
    url = SCA_api_url + "/risk-management/projects"

    try:
        payload = json.dumps({
        "Name": project_name,
        "AssignedTeams": [],
        "additionalProp1": {}
        })
        headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + access_token
        }

        response = requests.request("POST", url, headers=headers, data=payload, proxies=proxy_servers, verify=False)
        response.raise_for_status()  # Raise an error for bad responses

        response_json = response.json()
        project_id = response_json['id']  # Assuming the first project with the given name is returned
    except Exception as e:
        print("Exception: SCA_create_project:", str(e))
        return ""
    else:
        print('SCA_create_project - project_name= ' + response.text)
        return project_id

def SCA_get_project_id(access_token, project_name, SCA_api_url, proxy_servers=None):
    url = f"{SCA_api_url}/risk-management/projects?name={project_name}"

    try:
        headers = {
            'Authorization': 'Bearer ' + access_token
        }

        response = requests.get(url, headers=headers, proxies=proxy_servers, verify=False)
        response.raise_for_status()  # Raise an error for bad responses

        response_json = response.json()
        project_id = response_json['id']  # Assuming the first project with the given name is returned
    except requests.RequestException as e:
        print("Exception: Failed to get project ID:", str(e))
        return ""
    except (KeyError, IndexError):
        print("Exception: Project ID not found")
        return ""
    else:
        print('SCA_get_project_id id:', project_id)
        return project_id

def SCA_get_upload_link(access_token, project_id, SCA_api_url, proxy_servers=None):
    url = f"{SCA_api_url}/api/uploads"
#    url = f"{SCA_api_url}/scan-runner/scans/generate-upload-link"

    try:
        payload = {
            "projectId": project_id
        }
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + access_token
        }

        response = requests.post(url, headers=headers, json=payload, proxies=proxy_servers, verify=False)
        response.raise_for_status()  # Raise an error for bad responses

        response_json = response.json()
        upload_url = response_json.get('url')
    except requests.RequestException as e:
        print("Exception: Failed to get upload link:", str(e))
        return ""
    except KeyError:
        print("Exception: 'uploadUrl' key not found in response")
        return ""
    else:
        print('SCA_get_upload_link - uploadUrl:', upload_url)
        return upload_url

def SCA_upload_file(access_token, upload_link, zip_file_path, proxy_servers=None):
    try:
        with open(zip_file_path, 'rb') as file:
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/x-zip-compressed',
                'Authorization': 'Bearer ' + access_token
            }
            response = requests.put(upload_link, headers=headers, data=file, proxies=proxy_servers, verify=False)
            response.raise_for_status()  # Raise an error for bad responses
            print('SCA_upload_file:', response.text)
    except requests.RequestException as e:
        print("Exception: Failed to upload file:", str(e))

def SCA_scan_zip(access_token, project_id, upload_file_url, SCA_api_url, proxy_servers=None):
    url = f"{SCA_api_url}/api/scans/uploaded-zip"

    try:
        payload = {
            "projectId": project_id,
            "uploadedFileUrl": upload_file_url
        }
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + access_token
        }

        response = requests.post(url, headers=headers, json=payload, proxies=proxy_servers, verify=False)
        response.raise_for_status()  # Raise an error for bad responses

        response_json = response.json()
        print('SCA_scan_zip scan_id:', response_json['scanId'])
        return response_json['scanId']
    except requests.RequestException as e:
        print("Exception: Failed to initiate scan:", str(e))
        return None
    except KeyError:
        print("Exception: 'scanId' key not found in response")
        return None

def SCA_get_scan_status(access_token, scan_id, SCA_api_url, proxy_servers=None):
    url = SCA_api_url + "/api/scans/" + scan_id
    
    try:
        payload = {}
        headers = {
        'Authorization': 'Bearer ' + access_token
        }

        response = requests.request("GET", url, headers=headers, data=payload, proxies=proxy_servers, verify=False)
        status = response.content
   
    except Exception as e:
        print("Exception: SCA_get_scan_status", str(e))
        return ""
    else:
        print('SCSCA_get_scan_status')
        return status

def SCA_get_report(access_token, project_name, report_type, SCA_api_url, proxy_servers=None):
    scan_id = SCA_get_project_latest_scan_id(access_token, project_name, SCA_api_url, proxy_servers=None)

    url = SCA_api_url + "/risk-management/risk-reports/" + scan_id + '/' + 'export?format=' + report_type + '&dataType[]=All'
    
    try:
        payload = {}
        headers = {
        'Authorization': 'Bearer ' + access_token
        }

        response = requests.request("GET", url, headers=headers, data=payload, proxies=proxy_servers, verify=False)
        pdf_content = response.content
        report_path = os.getcwd() + '\\' + project_name + '_SCA_report.' + report_type
        with open(report_path, 'wb') as f:
            f.write(pdf_content)
    except Exception as e:
        print("Exception: SCA_get_report", str(e))
        return ""
    else:
        print('SCA_get_report')
        return report_path

def SCA_report_get_vulnerabilities_count_from_json(file_path):
    try:
        # Load JSON data from the file with explicit encoding
        with open(file_path, encoding='utf-8') as file:
            json_data = json.load(file)

        high_vulnerability_count = json_data['RiskReportSummary']['HighVulnerabilityCount']
        medium_vulnerability_count = json_data['RiskReportSummary']['MediumVulnerabilityCount']

    except Exception as e:
        print("Exception: SCA_report_get_high_vulnerabilities_count failed:", str(e))
        return 0
    else:
        return high_vulnerability_count, medium_vulnerability_count
