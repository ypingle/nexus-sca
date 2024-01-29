import json
import os
import sys
import xml.etree.ElementTree as ET

def create_package(dependencies, file_path, manifest):
    manifest_functions = {
        'npm': create_npm_package_json,
        'nuget': create_nuget_csproj,
        'pypi': create_pypi_requirements_txt
    }
    manifest_files = {
        'npm': 'package.json',
        'nuget': 'nuget.csproj',
        'pypi': 'requirements.txt'
    }

    if manifest in manifest_functions:
        if(os.path.isfile(file_path)):
            output_file_path = os.path.join(os.path.dirname(file_path), manifest_files[manifest])
        else:
            output_file_path = os.path.join(file_path, manifest_files[manifest])
         
        directory = os.path.dirname(output_file_path)
        # Create directory if it doesn't exist
        if not os.path.exists(directory):
            os.makedirs(directory)
    
        manifest_functions[manifest](dependencies, output_file_path)
    else:
        raise ValueError(f"Unsupported manifest type: {manifest}")
    return output_file_path

def create_npm_package_json(dependencies, output_file_path):
    try:
        # Create a JSON object representing package.json dependencies
        package_json = {
            "dependencies": dependencies
        }

        # Save the resulting package.json-style dependencies to a file
        with open(output_file_path, 'w') as output_file:
            json.dump(package_json, output_file, indent=2)

        print(f"Data saved to {output_file_path}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)

def create_nuget_csproj(dependencies, output_file_path):
    try:
        # Create the root element for the csproj XML
        root = ET.Element("Project", attrib={"Sdk": "Microsoft.NET.Sdk"})
        
        # Add PropertyGroup with specified content
        property_group = ET.SubElement(root, "PropertyGroup")
        output_type = ET.SubElement(property_group, "OutputType")
        output_type.text = "Exe"
        target_framework = ET.SubElement(property_group, "TargetFramework")
        target_framework.text = "net5.0"
        
        item_group = ET.SubElement(root, "ItemGroup")

        # Add PackageReference elements for each dependency
        for nuget_title, nuget_version in dependencies.items():
            package_reference = ET.SubElement(
                item_group, "PackageReference", 
                attrib={"Include": nuget_title, "Version": nuget_version}
                )

        # Create the ElementTree and write to the csproj file
        tree = ET.ElementTree(root)
        tree.write(output_file_path)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
    else:
        print(f"Created new csproj file with NuGet dependencies: {output_file_path}")

def create_pypi_requirements_txt(dependencies, output_file_path):
    try:
        with open(output_file_path, 'w') as requirements_file:
            for dependency in dependencies:
                requirements_file.write(f"{dependency}=={dependencies[dependency]}\n")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
    else:
        print(f"Created new requirements file with pypi dependencies: {output_file_path}")
