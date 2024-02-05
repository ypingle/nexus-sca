import json
import os
import sys
import xml.etree.ElementTree as ET

def create_package(dependencies, file_path, manifest):
    manifest_functions = {
        'npm': create_npm_package_json,
        'nuget': create_nuget_csproj,
        'pypi': create_pypi_requirements_txt,
        'maven2': create_maven_pom_xml
    }
    manifest_files = {
        'npm': 'package.json',
        'nuget': 'nuget.csproj',
        'pypi': 'requirements.txt',
        'maven2': 'pom.xml'
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

def create_maven_pom_xml(dependencies, output_file_path):
    try:
        # Create the root element for the pom.xml file
        root = ET.Element('project')
        root.set('xmlns', 'http://maven.apache.org/POM/4.0.0')

        # Add the modelVersion and groupId elements
        model_version = ET.SubElement(root, 'modelVersion')
        model_version.text = '4.0.0'

        group_id = ET.SubElement(root, 'groupId')
        group_id.text = 'org.openjfx'  

        artifact_id = ET.SubElement(root, 'artifactId')
        artifact_id.text = 'hellofx'

        packaging_id = ET.SubElement(root, 'packaging')
        packaging_id.text = 'jar'

        version_id = ET.SubElement(root, 'version')
        version_id.text = '1.0-SNAPSHOT'

        name_id = ET.SubElement(root, 'name')
        name_id.text = 'demo'

        url_id = ET.SubElement(root, 'url')
        url_id.text = 'http://maven.apache.org'

        # Add the dependencies element
        dependencies_element = ET.SubElement(root, 'dependencies')

        # Add each dependency to the XML tree
        for artifact_id, version in dependencies.items():
            split_result = version.split('|')
            if(split_result[0].count('.') == 2):
                new_dependency = ET.SubElement(dependencies_element, 'dependency')
                ET.SubElement(new_dependency, 'groupId').text = split_result[1]
                ET.SubElement(new_dependency, 'artifactId').text = artifact_id
                ET.SubElement(new_dependency, 'version').text = split_result[0]

        # Create an ElementTree object
        tree = ET.ElementTree(root)

        # Write the XML tree to the pom.xml file
        tree.write(output_file_path, encoding='utf-8', xml_declaration=True)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
    else:
        print(f"Created new pom.xml file with maven dependencies: {output_file_path}")
