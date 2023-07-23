import json
import requests
import xml.etree.ElementTree as ET
import os
import shutil
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

# Path to the executable file
nexus_repository_suffix = "/service/rest/v1/components?repository="
code_folder = './manifest'
org_code_folder = './manifest-org'
SCA_project_name = 'nexus_sca'
npm_manifest = 'package.json'
nuget_manifest = 'packages.config'
maven_manifest = 'pom.xml'
pypi_manifest = 'requirements.txt'

def copy_files(source_folder, destination_folder):
    # Create the destination folder if it doesn't exist
    os.makedirs(destination_folder, exist_ok=True)
    
    # Iterate over each item in the source folder
    for filename in os.listdir(source_folder):
        source_path = os.path.join(source_folder, filename)
        destination_path = os.path.join(destination_folder, filename)
        
        # Check if the item is a file
        if os.path.isfile(source_path):
            try:
                shutil.copy2(source_path, destination_path)
                print(f"Copied file: {source_path} -> {destination_path}")
            except Exception as e:
                print(f"Failed to copy file: {source_path} - {e}")
        else:
            print(f"Skipping non-file item: {source_path}")

def delete_files_in_folder(folder_path):
    try:    
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    print(f"Deleted file: {file_path}")
                except Exception as e:
                    print(f"Failed to delete file: {file_path} - {e}")
            else:
                print(f"Skipping non-file item: {file_path}")
    except Exception as e:
        print(f"Failed to delete file: {folder_path} - {e}")

def get_nexus_proxy_repositories(nexus_url):
    url = f"{nexus_url}/service/rest/v1/repositories"
    try:
        response = requests.get(url)
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

def add_dependency(xml_content, group_id, artifact_id, version):
    root = ET.fromstring(xml_content)
    dependencies = root.find(".//{http://maven.apache.org/POM/4.0.0}dependencies")

    new_dependency = ET.SubElement(dependencies, "dependency")
    ET.SubElement(new_dependency, "groupId").text = group_id
    ET.SubElement(new_dependency, "artifactId").text = artifact_id
    ET.SubElement(new_dependency, "version").text = version

    return ET.tostring(root, encoding="unicode")

def treat_package_list(packages, format):
    try:
        if format == 'npm':
            file_name = code_folder + '/' + npm_manifest
            with open(file_name, 'r') as file:
                data = json.load(file)

            # Update the dependencies in package.json
            if 'dependencies' not in data:
                data['dependencies'] = {}

            for package in packages:
                data['dependencies'][package['name']] = package['version']

            # Save the updated package.json file
            with open(file_name, 'w') as file:
                json.dump(data, file, indent=2)

            zip_file_name = file_name + '.zip'
            zip_file(file_name, zip_file_name)

        if format == 'pypi':
            file_name = code_folder + '/' + pypi_manifest
            with open(file_name, 'a') as file:
                # Write each package and version in the correct format
                for package in packages:
                    file.write(f"{package['name']}=={package['version']}\n")       
            zip_file_name = file_name + '.zip'
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

        if format == 'nuget':
            # Load the existing packages.config file
            file_name = code_folder + '/' + nuget_manifest 

            xml_content = ''
            with open(file_name, 'r') as file:
                xml_content = file.read()

            # Parse the XML content
            root = ET.fromstring(xml_content)

            for package in packages:
                new_package = ET.SubElement(root, 'package')
                new_package.set('id', package["name"])
                new_package.set('version', package["version"])
                new_package.set('targetFramework', 'net46')

            # Save the modified XML back to a string
            modified_xml_content = ET.tostring(root, encoding='unicode')

            with open(file_name, 'w') as file:
                file.write(modified_xml_content)

            zip_file_name = file_name + '.zip'
            zip_file(file_name, zip_file_name)
    except Exception as e:
        print("Exception: treat_packages_list:", str(e))
        return ""
    else:
        return zip_file_name

def get_packages_list(repository_name):
    try:
        url = nexus_server_url +  nexus_repository_suffix
        zip_file_name = ''
        continuationToken = ''
        short_packages = []

        print("\n")
        print(repository_name + " packages:")

        while(continuationToken != None):
            if(continuationToken == ''):
                response = requests.get(url + repository_name)
            else:
                response = requests.get(url + repository_name + '&continuationToken=' + continuationToken)
            # Check if the request was successful (status code 200)
            if response.status_code == 200:
                # Parse the JSON data from the response
                packages = response.json()['items']
                format = packages[0]['format']
                continuationToken = response.json()['continuationToken']

                for package in packages:
                    print(package['name'] + ' ' + package['version'])

                    package_info = {"name": package['name'], "version": package['version'], "group": package['group']}
                    short_packages.append(package_info)

        zip_file_name = treat_package_list(short_packages, format)

    except Exception as e:
        print("Exception: get_packages_list:", str(e))
        return ""
    else:
        return zip_file_name

def get_SCA_access_token():
    try:
        payload = 'username=' + SCA_username + '&password=' + SCA_password + '&acr_values=Tenant:' + SCA_account + '&scope=sca_api&client_id=sca_resource_owner&grant_type=password'
        headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
        }

#        response = requests.request("POST", SCA_auth_url, headers=headers, data=payload)
        response = requests.request("POST", SCA_auth_url, headers=headers, data=payload, verify=False)

        print('get_SCA_access_token - token = ' + response.text)
        response_json = response.json()
        access_token = response_json['access_token']
    except Exception as e:
        print("Exception: get access token failed:", str(e))
        return ""
    else:
        return access_token

def SCA_create_project (access_token, project_name):
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

        response = requests.request("POST", url, headers=headers, data=payload)
    except Exception as e:
        print("Exception: SCA_create_project:", str(e))
        return ""
    else:
        print('SCA_create_project - project_name= ' + response.text)
        return(response.text)

def SCA_get_project_id(access_token, project_name):
    url = SCA_api_url + "/risk-management/projects?name=" + project_name

    try:
        payload = {}
        headers = {
        'Authorization': 'Bearer ' + access_token
        }

        response = requests.request("GET", url, headers=headers, data=payload)
        response_json = response.json()
    except Exception as e:
        print("Exception: SCA_get_project_id:", str(e))
        return ""
    else:
        print('SCA_get_project_id id= ' + response_json['id'])
        return response_json['id']

def SCA_get_upload_link(access_token, project_id):
    url = SCA_api_url + "/scan-runner/scans/generate-upload-link"

    try:
        payload = json.dumps({
        "projectId": project_id
        })
        headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + access_token
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        response_json = response.json()
    except Exception as e:
        print("Exception: SCA_get_upload_link:", str(e))
        return ""
    else:
        print('SCA_get_upload_link - uploadUrl= ' + response_json['uploadUrl'])
        return response_json['uploadUrl']

def SCA_upload_file(access_token, upload_link, zip_file_path):
    url = upload_link

    try:
        with open(zip_file_path, 'rb') as file:
            payload = file
            headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-zip-compressed',
            'Authorization': 'Bearer ' + access_token
            }

            response = requests.request("PUT", url, headers=headers, data=payload)
            print('SCA_upload_file ' + response.text)
    except Exception as e:
        print("Exception: SCA_upload_file:", str(e))


def SCA_scan_zip(access_token, project_id, upload_file_url):
    url = SCA_api_url + "/scan-runner/scans/uploaded-zip"

    try:
        payload = json.dumps({
            "projectId": project_id,
            "uploadedFileUrl" : upload_file_url
        })
        headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + access_token
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        response_json = response.json()
    except Exception as e:
        print("Exception:  SCA_scan_zip :", str(e))
    else:
        print('SCA_scan_zip scan_id = ' + response_json['scanId'])
        return response_json['scanId']

def SCA_scan_packages(repository, zip_manifest_file):
    access_token = get_SCA_access_token()
    if(access_token != ""):
        project_name = SCA_project_name + '_' + repository
        SCA_create_project(access_token, project_name)
        project_id = SCA_get_project_id(access_token, project_name)
        upload_file_url = SCA_get_upload_link(access_token, project_id)
        SCA_upload_file(access_token, upload_file_url, zip_manifest_file)
        scan_id = SCA_scan_zip(access_token, project_id, upload_file_url)

#################################################
# main code
#################################################
def main():
    limit_packages= ''

    if(len(sys.argv) > 1):
        limit_packages = sys.argv[1]

    print('limit repo = ' + limit_packages)
    # 0 clear old manifex & zip files
    delete_files_in_folder(code_folder)
    # copy files from the source folder to the destination folder
    copy_files(org_code_folder, code_folder)

    # 1 Get the list of Nexus proxy repositories
    proxy_repositories = get_nexus_proxy_repositories(nexus_server_url)

    # Print the list of proxy repositories
    print("\nproxy repositories:")
    for repository in proxy_repositories:
        print(repository)
    for repository in proxy_repositories:
        if(limit_packages == '' or (limit_packages != '' and repository == limit_packages)):
            zip_file_name = get_packages_list(repository)
            print('\nzip file name:' + zip_file_name)
            if(zip_file_name != ''):
                SCA_scan_packages(repository, zip_file_name)
   
if __name__ == '__main__':
   main()