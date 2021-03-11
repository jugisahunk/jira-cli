# Introduction
This is a cli tool for querying Jira. It uses basic authentication. To use it, you'll need to use the username and password credentials for a user with read access to the Jira cloud instance you wish to query against.

# Setup
This CLI tool is tested to work using python 3.7.1. It will _not_ work on python 2.7.*. If you're on a mac, head to [python.org](https://www.python.org/downloads/) to download and install it or use homebrew. Here's a good guide to [using homebrew](https://docs.python-guide.org/starting/install3/osx/) as your installer.

`query.py` relies on the following environment variables to function:

## Basic Environment Setup
To perform basic querying, you'll need to setup your environment with a Jira host and user credentials. You will use the email address associated with your Atlassian account as a username. The password must be an api token. Here's the [guide](https://confluence.atlassian.com/cloud/api-tokens-938839638.html) to setting up an API token for your user. Your environment should contain these variables:

```
JIRA_HOST=https://myjira.atlassian.net
JIRA_USERNAME=[jira username e.g. donald.knuth@atlassian.net]
JIRA_API_TOKEN=[jira api token]
```

## AWS Upload Environment Setup
If you use the `--s` argument to specify an s3 bucket into which your csv results with be uploaded, you need to provide the access keys authorizing this script to write to that bucket.

```
AWS_ACCESS_KEY_ID=[access key]
AWS_SECRET_ACCESS_KEY=[secret access key]
```

Once you have python installed and your environment variables set, change into the root directory and run `pip install -r requirements.txt`. That's it! Refer to the [Using](https://github.com/mdx-dev/python-jira-cli#using-querypy) section below for helping using your shiny, new cli :).

## Output Config
You can configure how the script will output your issue field data. A `fields.json` file is provided in the `config` directory as a starting point, but you can duplicate and rename it to create your own. You can specify that the script run any output config file by using the --config argument detailed below in the [Using query.py](https://github.com/mdx-dev/python-jira-cli#using-querypy) section.

***Note: csv column order is determined by the order of these field objects.***

### `fields.json` Structure
```fields.json``` contains a single array of all field objects. Each field object has a *name* and a *value* property.

-**name:** csv column name 

-**value:** array with 1 or 2 values. 
- The first value is a [JMESPath](http://jmespath.org/) expression identifying the field value in the JSON api response. The second is a simple format string which is used to output the value in more robust ways. If no formatting string is given, only the field value is output. 

Here's an example that outputs only the *key* and *summary* fields of issues returned by a query:

```
[
    { 
        "name" : "key", 
        "value" : ["key"] 
    },
    { 
        "name" : "summary", 
        "value" : ["fields.summary"] 
    }
]
```
***Outputs***

|key | summary |
|---|---|
| ABC-15 | A jira issue summary value |
| ABC-16 | A second jira issue summary value |

### Formatting Examples

#### *Basic String format*
This utilizes the basic string formatting functionality in python; the ```{}``` is replaced by the value output of the JMESPath expression. The following is an example assuming a Jira issue with the key of 'ABC-15':
```
[
    { 
        "name" : "Key Greeting", 
        "value" : ["key", "Hello, my key is {}"] 
    }
]
```
This mapping outputs the record:

|Key Greeting|
|---|
| Hello, my value is: ABC-15 |

#### *Config value options:*
The formatting knows to look for certain keywords and replace them with helpful data:
- ```[host]``` get's replaced by the ```host``` value specified in the ```jira.yml``` file

#### *Combined example*
The basic format may be combined with the config value keywords. For instance, you could output the instance url for browsing to an issue with the following field config:
```
[
    { 
        "name" : "url", 
        "value" : ["key","[host]/browse/{}"]
    }
]
```
Assuming the configured host value is ```https://myjira.atlassian.net``` and the issue keys returned are XYZ-100 and XYZ-101, This mapping outputs the record: 

```
https://myjira.atlassian.net/browse/XYZ-100
https://myjira.atlassian.net/browse/XYZ-101
```

### Field Treatments
Though most fields can be easily output as single values, some may require *special treatment*. In those cases, refer to [JMESPath specifications](http://jmespath.readthedocs.io/en/latest/specification.html) for help. As a quick example, you could join together all values in a multi-value field with the ```|``` character with the following JMESPath expression where ```@``` represents the path to the multi-value field:
```
join(`|`, @)
```

# Using ```query.py```
```
usage: query.py [-h] [--csv CSV] [--config CONFIG] [--s S] [-c] [-l] query

positional arguments:
  query            JQL query

optional arguments:
  -h, --help       show this help message and exit
  --csv CSV        CSV Output Filename
  --config CONFIG  Output Config Filename
  --s S            Name of the s3 bucket into which the csv file will be
                   uploaded. This currently happens in addition to all other
                   output methods
  -c               Include Cycle Time Data. Assumes cycle begins with "In
                   Progress" and ends with "Resolved." Ignores issues which
                   never entered "In Progress". Time is given in minutes.
  -l               Include Lead Time Data. Assumes lead begins with "Open" and
                   ends with "Resolved." Time is given in minutes.
```

**Note:** CSV results are currently ALWAYS output to the local, working directory in addition to any other output options.
## Examples:
To retrieve all issues created in the last week and store them in a csv file stored in the script's working directory and named "last_week.csv" I would run:

```python3 query.py --csv="last_week" "created > -7d"```

If I wanted to add in cycle time data for those issues, I'd modify the line like so:

```python3 query.py -c --csv="last_week" "created > -7d"```

If I wanted to add in lead time data for those issues, I'd tweak the line as such:

```python3 query.py -cl --csv="last_week" "created > -7d"```

If I didn't care to name the file anything special, the following command will output a `results.csv` file with the query results:

```python3 query.py -cl "created > -7d"```

If I wanted to output my csv results to an s3 bucket for which I have the keys, I would write:

```python3 query.py --s=[bucket-name] "created > -7d"```

**Note:** s3 upload will fail with a _400_ error if the public and private keys are not setup properly in the environment.

# Extending this Script

First check the [issues section](https://github.com/mdx-dev/python-jira-cli/issues) to see if anything needs to be done.

This tool retrieves results using the latest version of [Jira Cloud REST API](https://developer.atlassian.com/cloud/jira/platform/rest/). All you need to know is how to write valid JQL. If you want to learn more about extending this script, please reference the [search api](https://developer.atlassian.com/cloud/jira/platform/rest/#api-api-2-search-get).
