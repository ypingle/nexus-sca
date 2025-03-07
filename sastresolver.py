import SAST_api
import argparse
import xml.etree.ElementTree as ET

def main():
    # Initialize at the start to avoid UnboundLocalError
    scan_status = None  # Changed from 0 to None for proper error tracking

    try:
        parser = argparse.ArgumentParser(
            description="ScareSolver - Tool for scanning packages in a source folder"
        )
        parser.add_argument(
            "file_path", 
            help="The path to the source folder to scan."
        )
        parser.add_argument(
            "project_name", 
            help="The name of the project."
        )
        parser.add_argument(
            "--team_name", 
            default="", 
            help="Optional: The name of the team."
        )
        parser.add_argument(
            "--incremental_scan", 
            default="False", 
            help="Optional: perform incremental scan (True/False)."
        )

        args = parser.parse_args()

        source_folder = args.file_path
        project_name = args.project_name
        team_name = args.team_name
        
        # Convert string to boolean
        incremental = args.incremental_scan.lower() in ('true', 'yes', '1', 'y')

        print(f"source folder = {source_folder}")
        print(f"project name = {project_name}")
        print(f"team name = {team_name}")
        print(f"incremental_scan = {incremental}")

        # Call with proper boolean parameter
        scan_status = SAST_api.scan_source_folder(project_name, source_folder, team_name, incremental)

    except SystemExit as e:
        print(f"SystemExit: {e}. Check if required arguments are provided.")
    except Exception as e:
        print(f"Exception: main: {str(e)}")
    finally:
        # Handle all possible return states
        if scan_status is None:
            print('exit 1: scan failed or did not complete')
            exit(1)
        elif scan_status == 1:
            print('exit -1: high vulnerability threshold exceeded')
            exit(-1)
        else:
            print('exit 0: scan completed successfully')
            exit(0)

if __name__ == '__main__':
    main()