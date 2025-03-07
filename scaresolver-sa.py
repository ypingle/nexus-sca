import requests
import os
import sys
import json
import zipfile
import fnmatch
import xml.etree.ElementTree as ET
import time

SCA_account = 'moj'
SCA_username = 'yoel2b'
SCA_password = 'Bb12345678!'
SCA_url = 'https://eu.sca.checkmarx.net'
SCA_api_url = 'https://eu.api-sca.checkmarx.net'
SCA_auth_url = 'https://eu.platform.checkmarx.net/identity/connect/token'
SCA_high_threshold = -1
SCA_proxy = ''
proxy_servers = {
   'https': SCA_proxy
}


def SCA_get_access_token():
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

#        print('SCA_get_access_token - token = ' + response.text)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        access_token = response.json()['access_token']
        return access_token
    except requests.RequestException as e:
        print("Exception: Failed to get access token:", str(e))
        return ""

def SCA_create_project(project_name, access_token="", team_name=None):
    if(not access_token):
        access_token = SCA_get_access_token()

    url = SCA_api_url + "/risk-management/projects"

    try:
        payload = json.dumps({
        "name": project_name,
        "assignedTeams": [f"/CxServer/{team_name}"] if team_name else [],
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
    
def SCA_get_project_id(project_name, access_token=""):
    if(not access_token):
        access_token = SCA_get_access_token()

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

def SCA_get_project_latest_scan_id(project_name, access_token=""):
    if(not access_token):
        access_token = SCA_get_access_token()

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
        try:
            print('SCA_get_project_latest_scan_id scan_id= ' + response_json['latestScanId'])
            return response_json['latestScanId']
        except Exception as e:
            return ""

def SCA_get_upload_link(project_id, access_token):
    if(not access_token):
        access_token = SCA_get_access_token()
    
    url = f"{SCA_api_url}/api/uploads"

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

def SCA_upload_file(upload_link, zip_file_path, access_token=""):
    if(not access_token):
        access_token = SCA_get_access_token()

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

def SCA_scan_zip(project_id, upload_file_url, access_token=""):
    if(not access_token):
        access_token = SCA_get_access_token()
    
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

def SCA_get_scan_status(scan_id, access_token=""):
    if(not access_token):
        access_token = SCA_get_access_token()

    url = SCA_api_url + "/api/scans/" + scan_id

    try:
        payload = {}
        headers = {
        'Authorization': 'Bearer ' + access_token
        }

        response = requests.request("GET", url, headers=headers, data=payload, proxies=proxy_servers, verify=False)
        status = response.content

        # Convert binary to string and parse JSON
        response_str = status.decode('utf-8')
        response_json = json.loads(response_str)

        # Get the status
        current_status = response_json.get('status')
   
    except Exception as e:
        print("Exception: SCA_get_scan_status", str(e))
        return ""
    else:
        print('SCA_get_scan_status')
        return current_status

def SCA_get_report(project_name, report_type, access_token=""):
    if(not access_token):
        access_token = SCA_get_access_token()

    scan_id = SCA_get_project_latest_scan_id(project_name, access_token)
    if scan_id:
        try:
            url = SCA_api_url + "/risk-management/risk-reports/" + scan_id + '/' + 'export?format=' + report_type + '&dataType[]=All'
        
            payload = {}
            headers = {
            'Authorization': 'Bearer ' + access_token
            }

            response = requests.request("GET", url, headers=headers, data=payload, proxies=proxy_servers, verify=False)
            pdf_content = response.content
            if report_type.lower() == 'csv':
                report_path = os.getcwd() + '\\' + project_name + '_SCA_report.zip'
            else:    
                report_path = os.getcwd() + '\\' + project_name + '_SCA_report.' + report_type
            with open(report_path, 'wb') as f:
                f.write(pdf_content)
        except Exception as e:
            print("Exception: SCA_get_report", str(e))
            return ""
        else:
            print('SCA_get_report')
            return report_path
    else:
        return ""


def SCA_report_get_details_from_json(file_path):
    try:
        # Load JSON data from the file with explicit encoding
        with open(file_path, encoding='utf-8') as file:
            json_data = json.load(file)

        high_vulnerability_count = json_data['RiskReportSummary']['HighVulnerabilityCount']
        medium_vulnerability_count = json_data['RiskReportSummary']['MediumVulnerabilityCount']
        resultUrl = SCA_url + '/#/projects/' + json_data['RiskReportSummary']['ProjectId']

    except Exception as e:
        print("Exception: SCA_report_get_high_vulnerabilities_count failed:", str(e))
        return 0
    else:
        return resultUrl, high_vulnerability_count, medium_vulnerability_count

def SCA_scan_packages(project_name, zip_manifest_file, team_name=None):
    access_token = SCA_get_access_token()
    if access_token:
        project_id = SCA_get_project_id(project_name, access_token)
        if (project_id == ''):
            project_id = SCA_create_project(project_name, access_token, team_name)
        if project_id:
            upload_file_url = SCA_get_upload_link(project_id, access_token)
            if upload_file_url:
                SCA_upload_file(upload_file_url, zip_manifest_file, access_token)
                scan_id = SCA_scan_zip(project_id, upload_file_url, access_token)

                if SCA_high_threshold is not None and SCA_high_threshold >= 0:
                    status = 'Running'
                    while(status == 'Running'):
                        time.sleep(5)
                        status = SCA_get_scan_status(scan_id, access_token)
                        print('scan status:' + status)

                    report_path = SCA_get_report(project_name, 'json')
                    resultUrl, high_vulnerability_count, medium_vulnerability_count = SCA_report_get_details_from_json(report_path)
                    print('high vulnerabilities = ' + str(high_vulnerability_count))
                    os.remove(report_path)

                    if(high_vulnerability_count > SCA_high_threshold):
                        return 1

                return None
    return None

def convert_directory_packages_to_csproj(props_file_path, csproj_output_path):
    try:
        # Parse the Directory.Packages.props file
        tree = ET.parse(props_file_path)
        root = tree.getroot()

        # Create a list to store PackageReference elements
        package_references = []

        # Find all PackageVersion elements and create corresponding PackageReference elements
        for package_version in root.findall(".//PackageVersion"):
            package_id = package_version.get('Include')
            package_version_value = package_version.get('Version')

            # Create the PackageReference element for .csproj with the correct version
            package_ref = f"""
    <ItemGroup>
        <PackageReference Include="{package_id}" Version="{package_version_value}" />
    </ItemGroup>
            """
            package_references.append(package_ref)

        # Generate the .csproj content
        csproj_content = """
<Project Sdk="Microsoft.NET.Sdk">
    <PropertyGroup>
        <TargetFramework>netstandard2.0</TargetFramework>
    </PropertyGroup>
"""
        # Append all PackageReference elements
        csproj_content += "\n".join(package_references)
        
        # Close the Project tag
        csproj_content += "\n</Project>"

        # Write the content to the output .csproj file
        with open(csproj_output_path, 'w') as csproj_file:
            csproj_file.write(csproj_content)

        print(f"Successfully converted {props_file_path} to {csproj_output_path}")

    except ET.ParseError as e:
        print(f"XML parsing error in {props_file_path}: {e}")
    except Exception as e:
        print(f"Error converting {props_file_path} to {csproj_output_path}: {e}")

def validate_csproj_dependencies(csproj_path):
    """Verify that all PackageReference elements in the .csproj have a Version attribute."""
    try:
        tree = ET.parse(csproj_path)
        root = tree.getroot()

        # Check for PackageReference elements without a Version attribute
        for package_ref in root.findall(".//PackageReference"):
            if package_ref.get('Version') is None:
                return False
        return True

    except ET.ParseError as e:
        print(f"XML parsing error in {csproj_path}: {e}")
        return False
    except Exception as e:
        print(f"Error validating dependencies in {csproj_path}: {e}")
        return False

def zip_folder(folder_to_zip, output_folder='src'):
    try:
        # Get the current working directory
        current_directory = os.getcwd()

        # Create the output folder if it doesn't exist
        output_folder_path = os.path.join(current_directory, output_folder)
        if not os.path.exists(output_folder_path):
            os.makedirs(output_folder_path)

        # Extract the folder name to use as the zip file name
        folder_name = os.path.basename(os.path.normpath(folder_to_zip))
        zip_file_name = folder_name + '.zip'
        zip_file_path = os.path.join(output_folder_path, zip_file_name)

        # Define the patterns to include in the zip file
        patterns = ['package.json', 'packages.config', '*.csproj', 'requirements.txt', 'pom.xml', 'composer.json', 'Directory.Packages.props']

        converted_csproj = None

        # Create the zip file
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(folder_to_zip):
                for file in files:
                    try:
                        # Check if the file matches any of the patterns
                        if any(fnmatch.fnmatch(file, pattern) for pattern in patterns):
                            file_path = os.path.join(root, file)

                            # Handle Directory.Packages.props by converting it to .csproj
                            if file == 'Directory.Packages.props':
                                converted_csproj = os.path.join(output_folder_path, 'converted.csproj')
                                convert_directory_packages_to_csproj(file_path, converted_csproj)

                                # Ensure the converted csproj is actually written to zip
                                if os.path.exists(converted_csproj):
                                    zipf.write(converted_csproj, 'converted.csproj')
                            
                            # Validate .csproj files to ensure all PackageReference elements have a Version attribute
                            elif fnmatch.fnmatch(file, '*.csproj'):
                                if validate_csproj_dependencies(file_path):
                                    zipf.write(file_path, os.path.relpath(file_path, folder_to_zip))
                                else:
                                    print(f"Excluding {file_path} from zip due to missing Version attributes in PackageReference.")

                            # Add other files directly to the zip
                            else:
                                zipf.write(file_path, os.path.relpath(file_path, folder_to_zip))

                    except Exception as e:
                        print(f"Error processing file {file} in zip creation: {e}")

            # If there was a conversion, clean up the temporary .csproj file
            if converted_csproj and os.path.exists(converted_csproj):
                os.remove(converted_csproj)

        print(f"Successfully created zip file: {zip_file_path}")
        return zip_file_path

    except Exception as e:
        print(f"Error zipping folder {folder_to_zip}: {e}")
        return None

#################################################
# main code
#################################################
def main():
    # Initialize at the start to avoid UnboundLocalError
    zip_file_name = None  
    scan_status = 0

    try:

        # Check if the file path is provided as a command-line argument
        if len(sys.argv) < 3:
            print("usage: scareolver <file path> <project name> <optional:team name>")
            sys.exit(1)

        source_folder = sys.argv[1]
        project_name = sys.argv[2]
        team_name = sys.argv[3] if len(sys.argv) == 4 else ""
        
        print('source folder =' + source_folder)
        print('project name =' + project_name)

        zip_file_name = zip_folder(source_folder, 'src')

        if(zip_file_name != ""):
            # If zip file is generated, proceed with scanning
            scan_status = SCA_scan_packages(project_name, zip_file_name, team_name)

    except SystemExit as e:
        print(f"SystemExit: {e}. Check if required arguments are provided.")
    except Exception as e:
        print("Exception: main:", str(e))
    finally:

        # Delete the zip file after processing
        if zip_file_name and os.path.exists(zip_file_name):
            os.remove(zip_file_name)

        if(scan_status == 1):
            print('eror -1 : high vunerability threshold exceeded')
            exit(-1)
        else:
            print('exit 0 : scan completed successfully')
            exit(0)    

if __name__ == '__main__':
   main()