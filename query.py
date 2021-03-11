import asyncio
import aiohttp
import argparse
import boto3
import datetime
import csv
import jmespath
import json
import math
import os
import requests
import time
import sys

from aiohttp import ClientSession
from aiohttp import ClientTimeout
from datetime import datetime
from dateutil.parser import parse

PAGE_SIZE=50

async def fetch(url, session):
    async with session.get(url) as response:
        t = '{0:%H:%M:%S}'.format(datetime.now())
        if(response.status == 200):
            print('Done: {}, {} ({})'.format(t, response.url, response.status))      
        else:
            print("############FAILURE############")
            print('Done: {}, {} ({})'.format(t, response.url, response.status))      

        return await response.text()

async def run(r,url):
    tasks = []
    all_issues = []

    # Fetch all responses within one Client session,
    # keep connection alive for all requests.
    auth = aiohttp.BasicAuth(login=jira_username, password=jira_password)
    conn = aiohttp.TCPConnector(limit=30)
    async with ClientSession(auth=auth, connector=conn) as session:
        for i in range(r):
            task = asyncio.ensure_future(fetch(url + "&startAt={}".format(i*PAGE_SIZE), session))
            tasks.append(task)

        response_texts = await asyncio.gather(*tasks)
        # you now have all response bodies in this variable

        return get_response_issues(response_texts)

def get_response_issues(response_texts):
    all_issues = []
    for response_text in response_texts:
        issue_page = json.loads(response_text)["issues"]
        all_issues.extend(issue_page)

    return all_issues

def is_date(string):
    try:
        datetime.strptime(string, "%Y-%m-%dT%H:%M:%S.%f%z")
        return True
    except:
        return False

def get_cycle_data(issue):
    if(issue["fields"]["status"]["name"] == "Resolved"):
        date_format = "%Y-%m-%d %H:%M:%S"
        histories = issue["changelog"]["histories"]
        starts = []
        ends = []
        for history in histories:
            history_created = parse(history["created"])

            starts.extend([history_created for item in history["items"] 
                if item["field"] == "status" and
                item["toString"] == "In Progress"])

            ends.extend([history_created for item in history["items"] 
                if item["field"] == "status" and
                item["toString"] == "Resolved"])

        if starts and ends:
            cycle_start = min(starts)
            cycle_end = max(ends)
            cycle_time = (cycle_end - cycle_start).total_seconds() / 60

            return [cycle_start.strftime("%Y/%m/%d %H:%M:%S"), cycle_end.strftime("%Y/%m/%d %H:%M:%S"), cycle_time]
        else:
            return ["","",""]

    return ["","",""]

def get_lead_data(issue):
    if(issue["fields"]["status"]["name"] == "Resolved"):
        histories = issue["changelog"]["histories"]
        ends = []
        for history in histories:
            history_created = parse(history["created"])

            ends.extend([history_created for item in history["items"] 
                if item["field"] == "status" and
                item["toString"] == "Resolved"])

        if ends:
            lead_start = parse(issue["fields"]["created"])
            lead_end = max(ends)
            lead_time = (lead_end - lead_start).total_seconds() / 60

            return [lead_start.strftime("%Y/%m/%d %H:%M:%S"), lead_end.strftime("%Y/%m/%d %H:%M:%S"), lead_time]
        else:
            return ["","",""]

    return ["","",""]


parser = argparse.ArgumentParser()
parser.add_argument("query", help="JQL query", type=str)

parser.add_argument("--csv", help="CSV Output Filename", type=str, default="results")
parser.add_argument("--config", help="Output Config Filename", type=str, default="fields")
parser.add_argument("--s", help="Name of the s3 bucket into which the csv file will be uploaded. This currently happens in addition to all other output methods", type=str)

parser.add_argument("-c", 
        help="Include Cycle Time Data. Assumes cycle begins with \"In Progress\" and ends with \"Resolved.\" Ignores issues which never entered \"In Progress\". Time is given in minutes.", 
        action='store_true')
parser.add_argument("-l",
        help="Include Lead Time Data. Assumes lead begins with \"Open\" and ends with \"Resolved.\" Time is given in minutes.", 
        action='store_true')

parser.parse_args()
args = parser.parse_args()

expand_clause = "expand=changelog&" if args.c else ""
query_clause = "jql={query}".format(query=args.query)

search_api = "/rest/api/latest/search?{expand}{query}".format(expand=expand_clause, query=query_clause)

# set jira credentials
print("looking for credentials in the environment")
using_env_host = "JIRA_HOST" in os.environ
using_env_username = "JIRA_USERNAME" in os.environ
using_env_password = "JIRA_API_TOKEN" in os.environ

if(using_env_host and using_env_username and using_env_password):
    jira_host = os.environ["JIRA_HOST"]
    jira_username = os.environ["JIRA_USERNAME"]
    jira_password = os.environ["JIRA_API_TOKEN"]
else:
    print("Jira credentials not found in the environment")
    sys.exit(1)

url = jira_host + search_api

print("querying: " + args.query)
print("hitting url: " + url)
r = requests.get(url, auth=(jira_username, jira_password))
print("Status: {}".format(r.status_code))

json_data_parsed = json.loads(r.text)

if(r.status_code != 200):
    print("request returned with error code: {}".format(r.status_code))

    for error in json_data_parsed["errorMessages"]:
        print("Error: {}".format(error))

    for warning in json_data_parsed["warningMessages"]:
        print("Warning: {}".format(warning))

    sys.exit(1)

before_issue_query = time.time()

total_results = json_data_parsed["total"]
print("Found {} total results.".format(total_results))

if(total_results > PAGE_SIZE):
    task_count = math.ceil((total_results) / PAGE_SIZE)
    print("retrieving {} pages of data".format(task_count))
    loop = asyncio.get_event_loop()
    future = asyncio.ensure_future(run(task_count, url))
    all_issues = loop.run_until_complete(future)
    loop.close()
else:
    all_issues = json_data_parsed["issues"]

print("Found {} issues. Retrieved {}".format(total_results, len(all_issues)))

after_issue_query = time.time()
query_seconds = after_issue_query - before_issue_query

output_config_filename = "{}.json".format(args.config)
with open('config/{}'.format(output_config_filename)) as json_file:
    fields = json.load(json_file)

csv_columns = jmespath.compile('[*].name').search(fields)

if(args.c):
    csv_columns.extend(["cycle_start", "cycle_end", "cycle_time"])

if(args.l):
    csv_columns.extend(["lead_start", "lead_end", "lead_time"])

csv_value_paths = jmespath.compile('[*].value').search(fields)

print("Writing results to {file_name}.csv".format(file_name=args.csv))
before_writing_csv_results = time.time()

csv_file_name = args.csv + ".csv"
with open(csv_file_name, 'w') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow(csv_columns)
    for issue in all_issues:
        issue_values = []
        for path in csv_value_paths:
            expression = jmespath.compile(path[0]) #jmespath expression
            field_value = expression.search(issue)
            field_value = "" if field_value is None else field_value

            if(isinstance(field_value,str) and is_date(field_value)):
                field_value = parse(field_value).strftime("%Y/%m/%d %H:%M:%S")
            
            if(len(path) == 2):
                value_format = path[1] #value output format
                output_value = value_format.replace('[host]', jira_host).format(field_value)
            else:
                output_value = field_value

            issue_values.append(output_value)

        if(args.c):
            issue_values.extend(get_cycle_data(issue))

        if(args.l):
            issue_values.extend(get_lead_data(issue))

        csv_writer.writerow(issue_values)
after_writing_csv_results = time.time() 
csv_seconds = after_writing_csv_results - before_writing_csv_results

if(args.s):
    before_uploading_s3 = time.time()
    s3 = boto3.resource("s3")

    csv_upload_path = "{}/{}".format(args.csv, csv_file_name)
    print("Uploading {} to s3://{}/{}".format(csv_file_name, args.s, csv_upload_path))
    s3.Bucket(args.s).upload_file(csv_file_name, csv_upload_path)

    manifest = {}
    manifest["fileLocations"] = []

    fileLocation = {}
    fileLocation["URIs"] = []
    fileLocation["URIs"].append("https://s3.amazonaws.com/{}/{}/{}".format(args.s, args.csv, csv_file_name))
    manifest["fileLocations"].append(fileLocation)

    manifest["globalUploadSettings"] = {}
    manifest["globalUploadSettings"]["format"] = "CSV"
    manifest["globalUploadSettings"]["delimiter"] = ","
    manifest["globalUploadSettings"]["containsHeader"] = "true"

    manifest_file_name = "{}_manifest.json".format(args.csv)
    with open(manifest_file_name, "w") as outfile:
        json.dump(manifest, outfile)

    manifest_upload_path = "{}/{}".format(args.csv, manifest_file_name)
    print("Uploading {} to s3://{}/{}".format(manifest_file_name, args.s, manifest_upload_path))
    s3.Bucket(args.s).upload_file(manifest_file_name, manifest_upload_path)

    after_uploading_s3 = time.time()

    s3_upload_seconds = after_uploading_s3 - before_uploading_s3

print("*************TIMES TAKEN*************")
print("Query took {} seconds or {} minutes to execute".format(round(query_seconds), round(query_seconds / 60,1)))
print("Writing CSV results took {} seconds or {} minutes to execute".format(round(csv_seconds), round(csv_seconds / 60,1)))
if(args.s):
    print("Uploading to s3 bucket took {} seconds or {} minutes to execute".format(round(s3_upload_seconds), round(s3_upload_seconds / 60,1)))
