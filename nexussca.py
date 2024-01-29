import parse_json_store
import requests
import xml.etree.ElementTree as ET
import os
import zipfile
import yaml
import json
import sys

# Open the YAML file
with open('config.yaml', 'r') as file:
    # Load the YAML contents
    config = yaml.safe_load(file)

SCA_account = config['SCA_account']
SCA_username = config['SCA_username']
SCA_password = config['SCA_password']
nexus_server_url = config['nexus_server_url']
SCA_api_url = config['SCA_api_url']
SCA_auth_url = config['SCA_auth_url']
SCA_proxy = config['SCA_proxy']
proxy_servers = {
   'https': SCA_proxy
}

# Path to the executable file
nexus_repository_suffix = "/service/rest/v1/components?repository="
code_folder = './manifest'
SCA_project_name = 'nexus_sca'
maven_manifest = 'pom.xml'

def get_nexus_proxy_repositories(nexus_url):
    url = f"{nexus_url}/service/rest/v1/repositories"
    try:
        response = requests.get(url, verify=False)
        response.raise_for_status()
        data = response.json()
        proxy_repositories = [repo["name"] for repo in data if repo["type"] == "proxy"]
        return proxy_repositories
    except Exception as e:
        print("Exception: get_nexus_proxy_repositories ", str(e))
        return ""

def zip_file(source_file, zip_file_name):
    with zipfile.ZipFile(zip_file_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(source_file, arcname=source_file)

def treat_package_list(packages, format):
    try:

        file_name = os.getcwd() +'\manifest'
        file_name = str(parse_json_store.create_package(packages, file_name, format))
        zip_file_name = str(file_name) + '.zip'
        zip_file(file_name, zip_file_name)

        if format == 'maven2':
            # Load the existing pom.xml file
            file_name = code_folder + '/' + maven_manifest 

            tree = ET.parse(file_name)
            root = tree.getroot()
            dependencies = ET.Element('dependencies')

            # Create the dependency XML structure
            for package in packages:
                dependency = ET.Element('dependency')
                groupId = ET.SubElement(dependency, 'groupId')
                groupId.text = package["group"]
                artifactId = ET.SubElement(dependency, 'artifactId')
                artifactId.text = package["name"]
                version = ET.SubElement(dependency, 'version')
                version.text = package["version"]
                # Append the new dependency to the dependencies section
                dependencies.append(dependency)
            root.append(dependencies)

            # Save the modified pom.xml file
            tree.write(file_name)
            zip_file_name = file_name + '.zip'
            zip_file(file_name, zip_file_name)

    except Exception as e:
        print("Exception: treat_packages_list:", str(e))
        return ""
    else:
        return zip_file_name

def get_packages_list(repository_name):
    try:
        url = nexus_server_url + nexus_repository_suffix
        continuation_token = ''
        dependencies = {}

        print("\n")
        print(repository_name + " packages:")

        while continuation_token is not None:
            if continuation_token == '':
                response = requests.get(url + repository_name, verify=False)
            else:
                response = requests.get(url + repository_name + '&continuationToken=' + continuation_token, verify=False)
            
            # Check if the request was successful (status code 200)
            if response.status_code == 200:
                # Parse the JSON data from the response
                data = response.json()
                packages = data.get('items', [])
                if not packages:
                    break
                
                file_format = packages[0].get('format', '')
                continuation_token = data.get('continuationToken')

                for package in packages:
                    print(package['name'] + ' ' + package['version'])
                    dependencies[package['name']] = package['version']
        return dependencies, file_format

    except requests.RequestException as e:
        print("Request Exception:", e)
        return None, None

    except KeyError as e:
        print("KeyError:", e)
        return None, None

    except Exception as e:
        print("Exception:", e)
        return None, None

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
    url = f"{SCA_api_url}/scan-runner/scans/generate-upload-link"

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
        upload_url = response_json.get('uploadUrl')
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
    url = f"{SCA_api_url}/scan-runner/scans/uploaded-zip"

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

def SCA_scan_packages(repository, zip_manifest_file, SCA_auth_url, SCA_api_url, proxy_servers=None):
    access_token = get_SCA_access_token(SCA_username, SCA_password, SCA_account, SCA_auth_url, proxy_servers=None)
    if access_token:
        project_name = SCA_project_name + '_' + repository
        project_id = SCA_get_project_id(access_token, project_name, SCA_api_url, proxy_servers)
        if (project_id == ''):
            project_id = SCA_create_project(access_token, project_name, SCA_api_url, proxy_servers=None)
        if project_id:
            upload_file_url = SCA_get_upload_link(access_token, project_id, SCA_api_url, proxy_servers)
            if upload_file_url:
                SCA_upload_file(access_token, upload_file_url, zip_manifest_file, proxy_servers)
                scan_id = SCA_scan_zip(access_token, project_id, upload_file_url, SCA_api_url, proxy_servers)
                return scan_id
    return None

#################################################
# main code
#################################################
def main():
    # Set a default value for limit_packages
    limit_repo = ''

    # Check if command-line arguments were provided
    if len(sys.argv) > 1:
        limit_repo = sys.argv[1]

    print('limit repo =', limit_repo)

    # 1. Get the list of Nexus proxy repositories
    proxy_repositories = get_nexus_proxy_repositories(nexus_server_url)

    # Print the list of proxy repositories
    print("\nproxy repositories:")
    for repository in proxy_repositories:
        print(repository)

    # Iterate through each repository
    for repository in proxy_repositories:
        # Check if limit_packages is empty or matches the current repository
        if not limit_repo or repository == limit_repo:
            # Get the list of packages for the current repository
            packages_list, format = get_packages_list(repository)
            
            # Treat the package list to create a zip file
            zip_file_name = treat_package_list(packages_list, format)
            print('\nzip file name:', zip_file_name)
            
            # If zip file is generated, proceed with scanning
            if zip_file_name:
                SCA_scan_packages(repository, zip_file_name, SCA_auth_url, SCA_api_url, proxy_servers)
 
if __name__ == '__main__':
   main()