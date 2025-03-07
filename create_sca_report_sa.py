import requests
import os
import zipfile
import pandas as pd
import gc
import argparse

SCA_account = 'moj'
SCA_username = 'yoel2b'
SCA_password = 'Bb12345678!'
SCA_url = 'https://eu.sca.checkmarx.net'
SCA_api_url = 'https://eu.api-sca.checkmarx.net'
SCA_auth_url = 'https://eu.platform.checkmarx.net/identity/connect/token'
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

#        response = requests.post(SCA_auth_url, headers=headers, data=payload, proxies=proxy_servers, verify=False)
        response = requests.post(SCA_auth_url, headers=headers, data=payload, proxies=proxy_servers)

        print('get_access_token ')
        response.raise_for_status()  # Raise an HTTPError for bad responses
        access_token = response.json()['access_token']
        return access_token
    except requests.RequestException as e:
        print("Exception: Failed to get access token:", str(e))
        return ""

def SCA_get_projects(access_token=""):
    if(not access_token):
        access_token = SCA_get_access_token()
    url = SCA_api_url + "/risk-management/projects"

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
            return response_json
        except Exception as e:
            return ""

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

def create_sca_report(projname=""):
    try:
        # Step 1: Get the access token
        access_token = SCA_get_access_token()

        # Step 2: Determine whether to process a single project or all projects
        if projname:
            projects = [{"name": projname}]
        else:
            projects = SCA_get_projects(access_token)
       
        processed_count = 0
        for project in projects:
            try:
                project_name = project['name']
                print(f"Processing project {processed_count + 1}: {project_name}")

                # Step 3: Get the SCA report path
                SCA_report_path = SCA_get_report(project_name, 'csv', access_token)
                if not SCA_report_path:
                    print(f"No SCA report found for project: {project_name}")
                    continue

                print(f"SCA report location: {SCA_report_path}")

                # Step 4: Extract and process the CSV files from the zip
                csv_filenames = ['Packages.csv']
                extracted_data = {}
                with zipfile.ZipFile(SCA_report_path, 'r') as zip_ref:
                    for filename in csv_filenames:
                        try:
                            with zip_ref.open(filename) as csv_file:
                                extracted_data[filename] = pd.read_csv(csv_file)
                        except KeyError:
                            print(f"File {filename} not found in zip for project: {project_name}")

                # Process Packages.csv
                if 'Packages.csv' in extracted_data:
                    packages_df = extracted_data['Packages.csv']

                    # Filter out development and test dependencies
                    packages_df = packages_df[
                        (packages_df['IsDevelopmentDependency'].fillna(True) == False) &
                        (packages_df['IsTestDependency'].fillna(True) == False)
                    ]

                    # Format date columns
                    for date_col in ['ReleaseDate', 'NewestVersionReleaseDate']:
                        packages_df[date_col] = packages_df[date_col].apply(
                            lambda x: x.split('T')[0] if pd.notnull(x) else x
                        )

                    columns_to_keep = [
                        'Name', 'Version', 'ReleaseDate', 'Licenses',
                        'NewestVersion', 'NewestVersionReleaseDate', 
                        'Severity', 'PackageRepository',
                        'IsDirectDependency'
                    ]

                    result_df = packages_df[columns_to_keep].copy()

                    # Add Project column
                    result_df['Project'] = project_name

                    # Reorder columns to put Project first
                    final_columns = ['Project'] + columns_to_keep
                    result_df = result_df[final_columns]

                    # Save results to sca_results.csv
                    sca_csv_path = os.path.join(os.getcwd(), 'sca_results.csv')
                    if os.path.exists(sca_csv_path):
                        result_df.to_csv(sca_csv_path, mode='a', index=False, header=False)
                    else:
                        result_df.to_csv(sca_csv_path, mode='w', index=False)

                    print(f"Packages data for project '{project_name}' saved to '{sca_csv_path}'.")
                
                processed_count += 1

            except Exception as project_error:
                print(f"Error processing project '{project_name}': {project_error}")

            finally:
                # Delete the zip file after processing
                if os.path.exists(SCA_report_path):
                    os.remove(SCA_report_path)

        print(f"Processed {processed_count} projects in total.")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        # Collect garbage to free up memory
        gc.collect()

#################################################
# main code
#################################################
def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Generate SCA reports for projects')
    parser.add_argument('-p', '--project', help='Specific project name to process', default="")
    parser.add_argument('-m', '--max', type=int, help='Maximum number of projects to process', default=None)
    
    args = parser.parse_args()
    
    # Default to 5 projects if no specific project and no max specified
    max_projects = 5 if (not args.project and args.max is None) else args.max
    
    print('max_projects : ' + str(max_projects))

    create_sca_report(args.project, max_projects)
    exit(0)

if __name__ == '__main__':
   main()