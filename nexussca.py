import parse_json_store
import SCA_api
from SCA_api import nexus_server_url, SCA_auth_url, SCA_api_url, proxy_servers 
import requests
import os
import zipfile
import sys
import argparse
from packaging.version import parse as version_parse

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
                    package_name = package['name']
                    package_version = package['version']
                    
                    if(file_format == 'maven2'):
                        dependencies[package['name']] = package['version'] + '|' + package['group']
                    elif file_format == 'npm':
                        if package['group'] is not None:
                            dependency_key = '@' + package['group'] + '/' + package_name
                        else:
                            dependency_key = package_name
                        dependency_value = package_version
                    else:
                        dependency_key = package_name
                        dependency_value = package_version
                    
                    # Check if the package already exists in the dependencies dictionary
                    if dependency_key in dependencies:
                        existing_version = dependencies[dependency_key].split('|')[0] if '|' in dependencies[dependency_key] else dependencies[dependency_key]
                        # Update only if the new version is older
                        if version_parse(package_version) < version_parse(existing_version):
                            dependencies[dependency_key] = dependency_value
                    else:
                        dependencies[dependency_key] = dependency_value

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

#################################################
# main code
#################################################
def main():
    # Create the parser
    parser = argparse.ArgumentParser(description="Process some parameters.")
    
    # Add the arguments
    parser.add_argument(
        '--repo', 
        type=str, 
        help='A string value for limiting the repository'
    )
    
    parser.add_argument(
        '--offline', 
        action='store_true', 
        help='A flag indicating whether to run in offline mode'
    )
    
    # Parse the arguments
    args = parser.parse_args()
    
    # Accessing the arguments
    limit_repo = args.repo if args.repo else ""
    offline = args.offline
    print('limit repo =', limit_repo)
    print('offline =', offline)

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
            if zip_file_name and not offline:
                SCA_api.SCA_scan_packages(SCA_project_name + '_' + repository, zip_file_name, SCA_auth_url, SCA_api_url, proxy_servers)
 
if __name__ == '__main__':
   main()