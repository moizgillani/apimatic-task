from __future__ import print_function

import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from notion_client import Client
import time

SCOPES = ['https://www.googleapis.com/auth/tasks.readonly']

creds = None
# Connect to the Notion API to obtain a valid Notion token and database ID
notion = Client(auth='secret_dE9hl248cv9GNl4EcmJ6bDSM7ZJCqf2zI8bH9PmwgTH')
database_id = 'ad9df9682f7a441d98669ea9dc860e91'

while True:
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file(
            'token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    tasks_api = build('tasks', 'v1', credentials=creds)

    try:
        # Use the access token to make a request to the Google Tasks API to retrieve the tasks
        tasklists = tasks_api.tasklists().list().execute()
        tasks = []
        for tasklist in tasklists['items']:
            tasks_res = tasks_api.tasks().list(
                tasklist=tasklist['id']).execute()
            tasks += tasks_res.get('items', [])

        # Parse the response from the API to extract the relevant task information
        new_tasks = []
        for task in tasks:
            new_task = {
                'id': task['id'],
                'title': task['title'],
                'notes': task.get('notes', ''),
                'due_date': task.get('due', ''),
                'last_updated': task.get('updated', ''),
                'completed': task.get('status', '') == 'completed'
            }
            new_tasks.append(new_task)
    except HttpError as err:
        print(err)

    try:
        # Check if each task already exists in the Notion database
        existing_tasks = notion.databases.query(
            **{
                'database_id': database_id,
                'filter': {
                    'property': 'Title',
                    'title': {
                        'is_not_empty': True
                    }
                }
            }
        ).get('results')

        new_tasks_to_add = []
        for new_task in new_tasks:
            task_already_exists = False
            for existing_task in existing_tasks:
                if existing_task['properties']['Id']['rich_text'][0]['text']['content'] == new_task['id']:
                    task_already_exists = True
                    break
            if not task_already_exists and new_task['title'] != '' and new_task['due_date'] != '':
                new_tasks_to_add.append(new_task)

    except HttpError as err:
        print(err)

    # If the task does not exist, add a new row to the Notion database with the relevant task information
    for new_task in new_tasks_to_add:
        new_page = {
            'Id': {
                'rich_text': [
                    {
                        'text': {
                            'content': new_task['id']
                        }
                    }
                ]
            },
            'Title': {
                'title': [
                    {
                        'text': {
                            'content': new_task['title']
                        }
                    }
                ]
            },
            'Notes': {
                'rich_text': [
                    {
                        'text': {
                            'content': new_task['notes']
                        }
                    }
                ]
            },
            'Due Date': {
                'date': {
                    'start': new_task['due_date']
                }
            },
            'Last Updated': {
                'date': {
                    'start': new_task['last_updated']
                }
            },
            'Completed': {
                'checkbox': new_task['completed']
            }
        }
        try:
            notion.pages.create(
                parent={'database_id': database_id}, properties=new_page)
        except HttpError as err:
            print(err)

    time.sleep(60)
