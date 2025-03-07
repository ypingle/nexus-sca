import xml.etree.ElementTree as ET
import requests
import zipfile
import time
from datetime import datetime
import os
import yaml
import sys
import smtplib
from email.mime.text import MIMEText

# Open the YAML file
with open('config_sast.yaml', 'r') as file:
    # Load the YAML contents
    config = yaml.safe_load(file)

SAST_username = config['SAST_username']
SAST_password = config['SAST_password']
SAST_auth_url = config['SAST_auth_url']
SAST_api_url = config['SAST_api_url']
SAST_web_url = config['SAST_web_url']
SAST_proxy = config['SAST_proxy']
proxy_servers = {
   'https': SAST_proxy
}

SMTP_server = config['SMTP_server']
SMTP_port = config['SMTP_port']
SMTP_tls = config['SMTP_tls']
SMTP_user = config['SMTP_user']
SMTP_password = config['SMTP_password']
Email_from = config['Email_from']
Email_subject = config['Email_subject']
project_list = ""
SAST_high_threshold = -1

def send_email(sender, email_recipients, subject, body, is_html=False):
    recipients_list = email_recipients.split(',')  # Split the email_recipients string into individual email addresses
    recipients = [recipient.strip() for recipient in recipients_list if recipient.strip()]  # Clean up email addresses

    # Validate essential inputs
    if not sender or not recipients:
        raise ValueError("Sender and recipients must be specified")

    # Prepare the email message
    message = MIMEText(body, "html" if is_html else "plain")    # Ensure email_recipients is a list of clean email addresses
    message['From'] = sender
    message['To'] = ", ".join(recipients)  # Join recipients into a comma-separated string
    message['Subject'] = subject  # Fixed the variable name for the subject

    try:
        # Set up SMTP connection
        smtp_obj = smtplib.SMTP(SMTP_server, SMTP_port)  
        
        if SMTP_tls:
            smtp_obj.starttls()

        if SMTP_user and SMTP_password:
            smtp_obj.login(SMTP_user, SMTP_password)

        # Send the email
        smtp_obj.sendmail(sender, recipients, message.as_string())
        print(f"Email sent successfully to: {', '.join(recipients)}")
        
        smtp_obj.quit()
    except Exception as e:
        print(f"Exception: Failed to send email: {str(e)}")

def extract_attribute_from_xml(xml_string, attribute_name):
    try:
        tree = ET.parse(xml_string)
        root = tree.getroot()

#        root = ET.fromstring(xml_string)
        attribute_value = root.get(attribute_name)
        return attribute_value
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return ""

# PDF, RTF, CSV, XML
def SAST_get_report(project_name, report_type, access_token="", start_time="", end_time=""):
    try:
        # Get access token
        if(not access_token):
            access_token = get_access_token()
        
        # Get latest scan id
        scan_id, created_at = get_project_latest_scan_id(access_token, project_name)
        if(scan_id == 0 and created_at == 0):
            return ""

        create_report = True
        if(start_time != "" and end_time != "" and not (start_time < created_at < end_time)):
            create_report = False

        if(create_report):            
            # Post report request
            report_id = SAST_post_report_request(access_token, scan_id, report_type)
            
            # Wait for report to be ready
            status = 0
            while status != 2:
                status = SAST_get_report_status(access_token, report_id)
                time.sleep(1)

            # Construct report URL
            headers = {
                'Authorization': f'Bearer {access_token}'
            }

            report_url = f"{SAST_api_url}/reports/sastScan/{report_id}"
            
            # Fetch report content
            response = requests.get(report_url, headers=headers)

            response.raise_for_status()  # Raise exception for non-200 status codes
            report_content = response.content

            # Save report to file
            report_filename = f"{project_name}_SAST_report.{report_type}"
            report_path = os.path.join(os.getcwd(), report_filename)
            with open(report_path, 'wb') as f:
                f.write(report_content)

            print("SAST report saved successfully.")
            return report_path
        else:
            return ""
    except Exception as e:
        print(f"Exception: {e}")
        return ""

def get_access_token(scope = 'sast_rest_api'):
    try:
        payload = {
            'scope': scope,
            'client_id': 'resource_owner_client',
            'grant_type': 'password',
            'client_secret': '014DF517-39D1-4453-B7B3-9930C563627C',
            'username': SAST_username,
            'password': SAST_password
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        response = requests.post(SAST_auth_url, headers=headers, data=payload)
        response.raise_for_status()  # Raise exception for HTTP errors
        print(f'get_SAST_access_token ')
        access_token = response.json()['access_token']
        return access_token
    except requests.exceptions.RequestException as e:
        print(f"Exception: get SAST access token failed: {e}")
        return ""

def get_projects(access_token=""):

    if(not access_token):
        access_token = get_access_token()

    try:
        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        url = f'{SAST_api_url}/projects'

        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise exception for HTTP errors
        
        print('SAST_get_projects')
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Exception: SAST_get_projects: {e}")
        return ""

def create_project(project_name, access_token="", team_name=""):
    """
    Create a new project in the SAST system.
    
    Args:
        project_name (str): Name of the project to create
        access_token (str, optional): Access token. If empty, will get a new one. Defaults to "".
        team_name (str, optional): Team name. Defaults to "".
        
    Returns:
        int: Project ID if successful, 0 if failed
    """
    try:
        # Input validation
        if not project_name:
            print("Error: Project name is required")
            return 0
            
        # Get access token if not provided
        if not access_token:
            access_token = get_access_token()
            if not access_token:
                print("Error: Failed to obtain access token")
                return 0

        # Set up headers
        headers = {
            'Content-Type': 'application/json;v=2.2',
            'Accept': 'application/json;v=2.2',
            'Authorization': f'Bearer {access_token}'
        }

        # Get team ID
        team_id = 1  # Default team ID
        if team_name:
            obtained_team_id = get_team_id(team_name)
            if obtained_team_id:  # Only use if we got a valid team ID
                team_id = obtained_team_id
            else:
                print(f"Warning: Could not find team '{team_name}', using default team ID")

        # Prepare payload
        payload = {
            "name": project_name,
            "owningTeam": str(team_id),
            "isPublic": True
        }

        # Correct URL for project creation
        url = f'{SAST_api_url}/projects'  # Removed 'help/' from URL path

        # Make API request
        response = requests.post(
            url, 
            headers=headers, 
            json=payload, 
            proxies=proxy_servers, 
            verify=False
        )
        
        # Handle HTTP errors
        response.raise_for_status()
        
        # Parse response
        response_json = response.json()
        if 'id' not in response_json:
            print(f"Error: Unexpected response format, 'id' not found: {response_json}")
            return 0
            
        project_id = response_json["id"]
        print(f'Project created successfully with ID: {project_id}')
        return project_id
        
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred in create_project: {http_err}")
        return 0
    except requests.exceptions.ConnectionError as conn_err:
        print(f"Connection error occurred in create_project: {conn_err}")
        return 0
    except requests.exceptions.Timeout as timeout_err:
        print(f"Timeout error occurred in create_project: {timeout_err}")
        return 0
    except requests.exceptions.RequestException as req_err:
        print(f"Request error occurred in create_project: {req_err}")
        return 0
    except Exception as e:
        print(f"Exception in create_project: {e}")
        return 0
        
def get_project_ID(project_name, access_token="", team_name=""):
    global project_list
    
    if(not access_token):
        access_token = get_access_token()

    try:
        if(project_list == ""):
            project_list = get_projects(access_token)
        projects = project_list

        projId = next((project['id'] for project in projects if project['name'] == project_name), 0)
        if(projId == 0):
            projId = create_project(project_name, access_token, team_name)
    except Exception as e:
        print(f"Exception: SAST_get_project_ID: {e}")
        return ""
    return projId

def get_project_latest_scan_id(access_token, project_name, project_id=None):
    try:
        if(not access_token):
            access_token = get_access_token()
        if(not project_id):
            project_id = get_project_ID(project_name, access_token)
    
        if(project_id):
            url = f"{SAST_api_url}/sast/scans?projectId={project_id}&last=1"

            headers = {
                'Authorization': f'Bearer {access_token}'
            }

            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            response_json = response.json()
            lastScanId = response_json[0]['id']

            print(f'get_project_latest_scan_id scan_id= {lastScanId}')
            created_at_str = response_json[0]['dateAndTime']['startedOn']
            try:
                created_at = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%S.%f")
            except ValueError:
                created_at = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%S")

            return lastScanId, created_at
        else:
            return 0,0

    except Exception as e:
        print(f"Exception: get_project_latest_scan_id: {e}")
        return 0,0
    
def SAST_get_project_latest_scan_comment(access_token, project_name):
    try:
        projId = get_project_ID(project_name, access_token)
        if projId == 0:
            return ""

        url = f"{SAST_api_url}/sast/scans?projectId={projId}&last=1"

        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise exception for HTTP errors

        response_json = response.json()
        comment = response_json[0].get('comment', '')
    except Exception as e:
        print(f"Exception: SAST_get_project_latest_scan_comment: {e}")
        return ""
    else:
        print(f"SAST_get_project_latest_scan_comment comment= {comment}")
        return comment

def SAST_post_report_request(access_token, sast_scan, report_type):
    url = f"{SAST_api_url}/reports/sastScan"
    payload = {
        "reportType": report_type,
        "scanId": sast_scan
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raise exception for HTTP errors
        
        response_json = response.json()
    except Exception as e:
        print(f"Exception: SAST_post_report_request: {e}")
        return ""
    else:
        return response_json.get('reportId', "")

def SAST_get_report_status(access_token, report_id):
    try:
        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        url = f"{SAST_api_url}/reports/sastScan/{report_id}/status"

        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise exception for       errors
        
        response_json = response.json()  # Parse the JSON response
        status_id = response_json.get("status", {}).get("id")
    except Exception as e:
        print(f"Exception: SAST_get_report_status: {e}")
        return ""
    else:
        print('SAST_get_report_status')
        return status_id

def SAST_get_scan_statistics(project_name, scan_id=0, access_token=""):
    """
    Get statistics for a SAST scan, including high and medium vulnerability counts.
    
    Args:
        project_name (str): Name of the project
        scan_id (int, optional): Scan ID. If 0, will get the latest scan ID. Defaults to 0.
        access_token (str, optional): Access token. If empty, will get a new one. Defaults to "".
        
    Returns:
        tuple: (high_count, medium_count, created_at) - counts of vulnerabilities and scan creation timestamp
    """
    try:
        # Input validation
        if not project_name:
            print("Error: Project name is required")
            return 0, 0, 0
            
        # Get access token if not provided
        if not access_token:
            access_token = get_access_token()
            if not access_token:
                print("Error: Failed to obtain access token")
                return 0, 0, 0
        
        # Get latest scan id if not provided
        created_at = 0
        if scan_id == 0:
            scan_id, created_at = get_project_latest_scan_id(access_token, project_name)
            if scan_id == 0:
                print(f"Error: No scan found for project '{project_name}'")
                return 0, 0, 0

        # Ensure scan_id is a string for URL construction
        scan_id_str = str(scan_id)
        
        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        url = f"{SAST_api_url}/sast/scans/{scan_id_str}/resultsStatistics"

        try:
            response = requests.get(url, headers=headers, proxies=proxy_servers, verify=False)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            report_content = response.json()
            
            # Use get() with default values to avoid KeyError
            high_count = report_content.get('highSeverity', 0)
            medium_count = report_content.get('mediumSeverity', 0)
            
            print('SAST_get_scan_statistics succeeded')
            return high_count, medium_count, created_at
            
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
            return 0, 0, 0
        except requests.exceptions.ConnectionError as conn_err:
            print(f"Connection error occurred: {conn_err}")
            return 0, 0, 0
        except requests.exceptions.Timeout as timeout_err:
            print(f"Timeout error occurred: {timeout_err}")
            return 0, 0, 0
        except requests.exceptions.RequestException as req_err:
            print(f"Request error occurred: {req_err}")
            return 0, 0, 0
        except ValueError as val_err:
            print(f"JSON parsing error: {val_err}")
            return 0, 0, 0

    except Exception as e:
        print(f"Exception in SAST_get_scan_statistics: {e}")
        return 0, 0, 0
        
def SAST_get_scan_results(project_name, access_token = ""):
    try:
        if(not access_token):
            access_token = get_access_token()
        
        # Get latest scan id
        scan_id, created_at = get_project_latest_scan_id(access_token, project_name)
        if(scan_id == 0 and created_at == 0):
            return ""

        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        url = f"{SAST_api_url}/sast/scans/{scan_id}/results"

        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise exception for errors

        result_content = response.json()

    except Exception as e:
        print(f"Exception: SAST_get_scan_results: {e}")
        return ""
    else:
        print('SAST_get_scan_results')
        return result_content 

def SAST_get_vulnerability_details(result_id, access_token = ""):
    try:
        if(not access_token):
            access_token = get_access_token()
        
        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        url = f"{SAST_api_url}/sast/vulnerabilities/{result_id}"

        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise exception for errors

        result_content = response.json()

    except Exception as e:
        print(f"Exception: SAST_get_scan_results: {e}")
        return ""
    else:
        print('SAST_get_scan_results')
        return result_content 

def SAST_get_teams(access_token=""):
    if(not access_token):
        access_token = get_access_token()

    try:
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        url = f"{SAST_api_url}/auth/teams"

        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)
        teams_json = response.json()

    except requests.exceptions.RequestException as e:
        print(f"Exception: SAST_get_teams - {e}")
        return []
    except Exception as e:
        print(f"Exception: SAST_get_teams - {e}")
        return []
    else:
        return teams_json

# Fixed versions of the functions with parameter order corrected

def SAST_get_team_members(access_token="", team_id=0):
    """
    Get members of a team.
    
    Args:
        access_token (str, optional): Access token. If empty, will get a new one. Defaults to "".
        team_id (int, optional): Team ID. Defaults to 0.
        
    Returns:
        list: List of team members
    """
    if not access_token:
        access_token = get_access_token('access_control_api')

    try:
        headers = {'Authorization': f'Bearer {access_token}'}
        url = f"{SAST_api_url}/auth/teams/{team_id}/Users"

        response = requests.get(url, headers=headers, proxies=proxy_servers, verify=False)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)
        response_json = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Exception: SAST_get_team_members - {e}")
        return []
    except Exception as e:
        print(f"Exception: SAST_get_team_members - {e}")
        return []
    else:
        return response_json


def get_team_email_recipients(xml_team_full_path, team_id=0):
    """
    Get a comma-separated list of email addresses for all members of a team.
    
    Args:
        xml_team_full_path (str): Full path of the team in XML format
        team_id (int, optional): Team ID. If 0, will get the ID from path. Defaults to 0.
        
    Returns:
        str: Comma-separated list of email addresses
    """
    try:
        # Get access token - adding this since it's needed for SAST_get_team_members
        access_token = get_access_token('access_control_api')
        if not access_token:
            print("Error: Failed to obtain access token")
            return ""
            
        # Get team ID if not provided
        if team_id == 0:
            team_id = get_team_id(xml_team_full_path)
            
        if not team_id or team_id <= 0:
            print(f"Error: Could not find team ID for '{xml_team_full_path}'")
            return ""

        # Get team members - fixed parameter order
        team_members = SAST_get_team_members(access_token, team_id)
        if not team_members:
            print(f"Error: No team members found for team ID {team_id}")
            return ""
            
        # Extract email addresses and join with commas
        # Use get() to avoid KeyError if email is missing
        email_recipients = ','.join(member.get('email', '') for member in team_members if member.get('email'))
        
        return email_recipients

    except Exception as e:
        print(f"Exception in get_team_email_recipients: {e}")
        return ""
    
def get_team_id(xml_team_full_path):
    """
    Get the team ID based on the XML team path.
    
    Args:
        xml_team_full_path (str): Full path of the team in XML format
        
    Returns:
        int: Team ID if found, 0 if not found or on error
    """
    try:
        # Input validation
        if not xml_team_full_path:
            print("Error: XML team path is required")
            return 0
            
        # Get access token
        access_token = get_access_token('access_control_api')
        if not access_token:
            print("Error: Failed to obtain access token")
            return 0

        # Get teams list
        teams_list = SAST_get_teams(access_token)
        if not teams_list:
            print("Error: Failed to retrieve teams list")
            return 0
            
        print('Team list:')
        team_id = 0
        for team in teams_list:
            # Handle potential missing keys
            if 'fullName' not in team or 'id' not in team:
                continue
                
            team_name = team['fullName'].lstrip('/')
            print(f'id: {team["id"]} name: {team_name}')

            # Normalize paths for comparison
            if team_name == xml_team_full_path.replace('\\','/'):
                team_id = team['id']
                print('Team match found:', team_name)
                break

        return team_id

    except Exception as e:
        print(f"Exception in get_team_id: {e}")
        return 0  # Return 0 instead of empty string for consistency

def get_team_email_recipients(xml_team_full_path, team_id=0):
    """
    Get a comma-separated list of email addresses for all members of a team.
    
    Args:
        xml_team_full_path (str): Full path of the team in XML format
        team_id (int, optional): Team ID. If 0, will get the ID from path. Defaults to 0.
        
    Returns:
        str: Comma-separated list of email addresses
    """
    try:
        # Get access token - adding this since it's needed for SAST_get_team_members
        access_token = get_access_token('access_control_api')
        if not access_token:
            print("Error: Failed to obtain access token")
            return ""
            
        # Get team ID if not provided
        if team_id == 0:  # Fixed variable name from team_id to team_id
            team_id = get_team_id(xml_team_full_path)
            
        if not team_id or team_id <= 0:
            print(f"Error: Could not find team ID for '{xml_team_full_path}'")
            return ""

        # Get team members
        team_members = SAST_get_team_members(access_token, team_id)
        if not team_members:
            print(f"Error: No team members found for team ID {team_id}")
            return ""
            
        # Extract email addresses and join with commas
        # Use get() to avoid KeyError if email is missing
        email_recipients = ','.join(member.get('email', '') for member in team_members if member.get('email'))
        
        return email_recipients

    except Exception as e:
        print(f"Exception in get_team_email_recipients: {e}")
        return ""
        
def upload_file(access_token, project_id, source_folder, isIncremental=False):
    """
    Zip a source folder and upload it for scanning.
    
    Args:
        access_token (str): Authentication token
        project_id (int): ID of the project to scan
        source_folder (str): Path to the source folder to scan
        isIncremental (bool, optional): Whether to perform an incremental scan. Defaults to False.
        
    Returns:
        str: Scan ID if successful, None if failed
    """
    scan_id = None  # Initialize return value
    output_zip = None  # Initialize zip path for cleanup
    
    try:
        # Define the API URL
        upload_url = f"{SAST_api_url}/sast/scanWithSettings"

        # Zip the source folder
        folder_name = os.path.basename(source_folder.rstrip('/\\'))
        output_zip = os.path.join(os.path.dirname(source_folder), f"{folder_name}.zip")
        
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(source_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.relpath(file_path, source_folder))
        print(f"Folder '{source_folder}' zipped successfully into '{output_zip}'")
        
        # Check if zip file exists
        if not os.path.exists(output_zip):
            print(f"Error: Zip file '{output_zip}' does not exist.")
            return None

        # Read the zip file in binary mode
        with open(output_zip, 'rb') as source_file:
            files = {
                "zippedSource": (os.path.basename(output_zip), source_file, "application/octet-stream")
            }
            headers = {
                "Accept": "application/json;v=1.0",
                "Authorization": f"Bearer {access_token}",
                "cxOrigin": "cx-CLI",
            }
            data = {
                "projectId": str(project_id),
                "isIncremental": isIncremental
            }

            # Make the POST request
            print(f"Uploading file: {output_zip} to {upload_url}")
            upload_response = requests.post(upload_url, headers=headers, data=data, files=files)
           
            if upload_response.status_code != 201:
                print(f"Upload failed with status {upload_response.status_code}: {upload_response.text}")
                return None
                
            scan_id = upload_response.json().get("id")
            print("Source code uploaded successfully. scan id= " + str(scan_id))
    except Exception as e:
        print(f"Exception in upload_file: {e}")
    finally:
        # Clean up the zip file
        if output_zip and os.path.exists(output_zip):
            try:
                os.remove(output_zip)
                print(f"Temporary zip file '{output_zip}' removed")
            except Exception as e:
                print(f"Warning: Could not remove temporary zip file '{output_zip}': {e}")

    return scan_id  # Always return scan_id (will be None in case of failures)
        
def SAST_get_scan_status(scan_id, access_token=""):
    """
    Get the status of a SAST scan.
    
    Args:
        scan_id (int): ID of the scan
        access_token (str, optional): Access token. If empty, will get a new one. Defaults to "".
        
    Returns:
        str: Status of the scan or empty string on error
    """
    # Check if scan_id is None or empty
    if not scan_id:
        print("Error: scan_id is empty or None")
        return ""
        
    # Ensure scan_id is a string
    scan_id_str = str(scan_id)
    
    # Get access token if not provided
    if not access_token:
        access_token = get_access_token()

    # Construct URL with proper string conversion
    url = f"{SAST_api_url}/sast/scans/{scan_id_str}"

    try:
        payload = {}
        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        response = requests.request("GET", url, headers=headers, data=payload, proxies=proxy_servers, verify=False)
        
        # Check for HTTP errors
        response.raise_for_status()
        
        response_json = response.json()

        # Safer way to access nested dictionary
        current_status = ""
        finished_status = response_json.get('finishedScanStatus')
        if finished_status and isinstance(finished_status, dict) and 'value' in finished_status:
            current_status = finished_status['value']
        
        print(f'SAST_get_scan_status succeeded: {current_status}')
        return current_status
   
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return ""
    except requests.exceptions.ConnectionError as conn_err:
        print(f"Connection error occurred: {conn_err}")
        return ""
    except requests.exceptions.Timeout as timeout_err:
        print(f"Timeout error occurred: {timeout_err}")
        return ""
    except requests.exceptions.RequestException as req_err:
        print(f"Request error occurred: {req_err}")
        return ""
    except Exception as e:
        print(f"Exception in SAST_get_scan_status: {e}")
        return ""
            
def scan_source_folder(project_name, source_folder, team_name='', incremental=False):
    """
    Scan a source folder for vulnerabilities and check against threshold.
    
    Args:
        project_name (str): Name of the project
        source_folder (str): Path to the source folder to scan
        team_name (str, optional): Team name. Defaults to ''.
        incremental (bool, optional): Whether to perform an incremental scan. Defaults to False.
        
    Returns:
        int: 1 if high vulnerabilities exceed threshold, 0 for successful scan below threshold, 
             None for errors or if threshold check is skipped
    """
    try:
        # Validate inputs
        if not project_name or not source_folder:
            print("Error: Project name and source folder are required")
            return None
            
        # Get access token
        access_token = get_access_token()
        if not access_token:
            print("Error: Failed to obtain access token")
            return None
            
        # Get project ID
        project_id = get_project_ID(project_name, access_token, team_name)
        if not project_id:
            print(f"Error: Failed to get project ID for project '{project_name}'")
            return None
            
        # Upload file and get scan ID
        scan_id = upload_file(access_token, project_id, source_folder, incremental)
        if not scan_id:
            print("Error: Failed to upload file and obtain scan ID")
            return None
            
        print(f'scan id = {scan_id}')
        print(f'SAST_high_threshold = {SAST_high_threshold}')
        
        # Check if threshold validation is needed
        if SAST_high_threshold is not None and SAST_high_threshold >= 0:
            # Wait for scan completion
            status = 'Running'
            max_retries = 120  # 10 minutes with 5-second intervals
            retries = 0
            
            while status != 'Completed' and retries < max_retries:
                try:
                    time.sleep(5)
                    retries += 1
                    status = SAST_get_scan_status(scan_id, access_token)
                    print(f'scan status: {status}')
                    
                    # Check for failed or canceled scans
                    if status in ['Failed', 'Canceled']:
                        print(f"Scan ended with status: {status}")
                        return None
                        
                except Exception as e:
                    print(f"Error checking scan status: {e}")
                    # Continue waiting, don't abort the loop
            
            if status != 'Completed':
                print(f"Scan did not complete within the maximum wait time")
                return None
                
            # Get scan statistics
            try:
                high_vulnerability_count, medium_vulnerability_count, created_at = SAST_get_scan_statistics(project_name, scan_id, access_token)
                print(f'high = {high_vulnerability_count}')
                print(f'medium = {medium_vulnerability_count}')
                
                # Check against threshold
                if high_vulnerability_count > SAST_high_threshold:
                    return 1
                return 0  # Explicitly return 0 for successful scan below threshold
                
            except Exception as e:
                print(f"Error getting scan statistics: {e}")
                return None
        
        # If no threshold check is needed, return successful result
        return 0
        
    except Exception as e:
        print(f"Exception in scan_source_folder: {e}")
        return None