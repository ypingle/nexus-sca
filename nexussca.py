import parse_json_store
import SCA_api
import requests
import os
import zipfile
import yaml
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
                    if(file_format == 'maven2'):
                        dependencies[package['name']] = package['version'] + '|' + package['group']
                    else:    
                        if(file_format == 'npm'):
                            if package['group'] is not None:
                                dependencies['@' + package['group'] + '/' + package['name']] = package['version']
                            else:                                
                                dependencies[package['name']] = package['version'] 
                        else:
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

def SCA_scan_packages(repository, zip_manifest_file, SCA_auth_url, SCA_api_url, proxy_servers=None):
    access_token = SCA_api.get_SCA_access_token(SCA_username, SCA_password, SCA_account, SCA_auth_url, proxy_servers)
    if access_token:
        project_name = SCA_project_name + '_' + repository
        project_id = SCA_api.SCA_get_project_id(access_token, project_name, SCA_api_url, proxy_servers)
        if (project_id == ''):
            project_id = SCA_api.SCA_create_project(access_token, project_name, SCA_api_url, proxy_servers)
        if project_id:
            upload_file_url = SCA_api.SCA_get_upload_link(access_token, project_id, SCA_api_url, proxy_servers)
            if upload_file_url:
                SCA_api.SCA_upload_file(access_token, upload_file_url, zip_manifest_file, proxy_servers)
                scan_id = SCA_api.SCA_scan_zip(access_token, project_id, upload_file_url, SCA_api_url, proxy_servers)
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