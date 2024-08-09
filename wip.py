#!/usr/bin/env python3

import argparse
import json
import os
import boto3
from botocore.config import Config
import pprint



class Inventory:
    def __init__(self, region, directory=None, workspaces=None):
        self.region = region
        self.workspaces_directory = directory
        self.specific_workspaces = workspaces
        self.config = Config(
            retries = {
                'max_attempts': 10,
                'mode': 'standard'
            }
        )
        self.get_client()
        self.get_workspaces()
        self.generate_inventory()

    def get_client(self):
        try:
            self.client = boto3.client('workspaces', config=self.config, region_name=self.region)
            self.paginator = self.client.get_paginator("describe_workspaces")
        except Exception as e:
            print(f"Exception: {e}")
            raise(e)
        
    def get_tags(self, workspace_id):
        '''Create a list of group names from aws workspace tags where key and value become key-value in lowercase'''
        try:
            tags_list = self.client.describe_tags(ResourceId=workspace_id).get('TagList', '')
        except Exception as e:
            print(f"Exception: {e}")
            raise(e)
        
        group_names = []
        for item in tags_list:
            key = item.get('Key', '').lower()
            value = item.get('Value', '').lower()
            group_name = f"{key}-{value}"
            if group_name not in group_names:
                group_names.append(group_name)
        return group_names

    def get_workspaces(self):
        if self.specific_workspaces:
            operation_parameters= {
                "WorkspaceIds": self.specific_workspaces
                }
            workspaces = []
            for page in self.paginator.paginate(
                **operation_parameters, PaginationConfig={"PageSize": 25}
            ):
                workspaces.extend(page['Workspaces'])

        elif self.workspaces_directory:
            operation_parameters = {
                "DirectoryId": self.workspaces_directory
                }
            workspaces = []
            for page in self.paginator.paginate(
                **operation_parameters, PaginationConfig={"PageSize": 25}
            ):
                workspaces.extend(page['Workspaces'])
        else:
            workspaces = []
            for page in self.paginator.paginate(
                PaginationConfig={"PageSize": 25}
            ):
                workspaces.extend(page['Workspaces'])
        self.workspaces = workspaces

    def generate_inventory(self):
        self.inventory = {'_meta': {'hostvars': {}}}
        for ws in self.workspaces:
            state = ws.get('State', '')
            if state != 'AVAILABLE':
                continue

            computer_name = ws.get('ComputerName', '')
            os = ws.get('WorkspaceProperties', {}).get('OperatingSystemName', '')
            workspace_id = ws.get('WorkspaceId', '')


            if os == 'UBUNTU_22_04':
                group_name = 'ubuntu_22_04_workspaces'
            elif os == 'AMAZON_LINUX_2':
                group_name = 'amazon_linux_2_workspaces'
            elif os == 'WINDOWS_SERVER_2016':
                group_name = 'windows_server_2016_workspaces'
            elif os == 'WINDOWS_SERVER_2019':
                group_name = 'windows_server_2019_workspaces'
            elif os == 'WINDOWS_SERVER_2022':
                group_name = 'windows_server_2022_workspaces'
            elif os == 'WINDOWS_10':
                group_name = 'windows_10_workspaces'
            elif os == 'WINDOWS_11':
                group_name = 'windows_11_workspaces'
            else:
                print(f"Warning: WorkSpace ({ws}) is running an operating system that is not supported by the dynamic inventory provider. See the GitHub page for support.")
                continue

            ip_address = ws.get('IpAddress', '')

            if group_name not in self.inventory:
                self.inventory[group_name] = {'hosts': [], 'vars': {}}

            self.inventory[group_name]['hosts'].append(ip_address)

            if group_name.startswith('windows'):
                host_vars = {
                    'ansible_connection': 'winrm',
                    'ansible_winrm_transport': 'kerberos',
                    'ansible_winrm_port': '5985',
                    'ansible_winrm_kerberos_hostname_override': computer_name
                }
            else:
                host_vars = {
                    'ansible_connection': 'ssh',
                    'ansible_user': 'ansible'
                }

            self.inventory['_meta']['hostvars'][ip_address] = host_vars

            # Handling the automatic build of ansible group names based off workspace tags
            group_names = self.get_tags(workspace_id)
            #print(f"group_names are: {group_names}")

            for grp_name in group_names:
                if grp_name not in self.inventory:
                    self.inventory[grp_name] = {'hosts': [], 'vars': {}}
                self.inventory[grp_name]['hosts'].append(ip_address)
        return
    
    def get_inventory(self):
        return self.inventory


def main():
    parser = argparse.ArgumentParser(description='Generate Ansible inventory for AWS WorkSpaces.')
    parser.add_argument('--region', help='AWS Region')
    parser.add_argument('--list', action='store_true', help='List inventory.')
    exclusivearguments = parser.add_mutually_exclusive_group()
    exclusivearguments.add_argument('--directory-id', help='DirectoryId.')
    exclusivearguments.add_argument('--workspace-ids', nargs='*', help='One or more WorkSpace IDs, separated by space.')
    args = parser.parse_args()

# If neither the --list nor --workspace-id argument was used, print the help text

    if not args.list and not args.workspace_ids:
        parser.print_help()
        return
# When directly calling this script, the region and directory ID can be specified as arguments.
# However, if this script is being used with `ansible-inventory`, these must be set as environment variables
# For example: `export AWS_REGION=us-west-2` or `export DIRECTORY_ID=d-xxxxxxxxx`
# Clear variables with `unset AWS_REGION` or `unset DIRECTORY_ID`

    region = args.region if args.region else os.environ.get('AWS_REGION')
    #print(f"region: {region}")

    if not region:
        print('Error: AWS region must be specified via --region argument or AWS_REGION environment variable.')
        exit(1)

    workspaces_directory = args.directory_id if args.directory_id else os.environ.get('DIRECTORY_ID')
    #print(f"workspaces_directory: {workspaces_directory}")

    specific_workspaces = args.workspace_ids
    #print(f"specific_workspaces: {specific_workspaces}")

    i = Inventory(region, directory=workspaces_directory, workspaces=specific_workspaces)
    inventory = i.get_inventory()
    pprint.pprint(inventory)



if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Error / Exception: {e}")
