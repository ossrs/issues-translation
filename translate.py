import sys
import time
starttime = time.time()

import os, sys, openai, argparse, requests

parser = argparse.ArgumentParser(description="Translation")
parser.add_argument("--issue", type=str, required=True, help="GitHub issue URL, for example, https://github.com/ossrs/srs/issues/3692")
parser.add_argument("--token", type=str, required=False, help="GitHub access token, for example, github_pat_xxx_yyyyyy")
parser.add_argument("--proxy", type=str, required=False, help="OpenAI API proxy, for example, x.y.z")
parser.add_argument("--key", type=str, required=False, help="OpenAI API key, for example, xxxyyyzzz")

PROMPT_TRANS="translate to english:"
PROMPT_SANDWICH="Make sure to maintain the markdown structure."
TRANS_MAGIC="TRANS_BY_GPT3"

args = parser.parse_args()

if args.token is not None:
    os.environ["GITHUB_TOKEN"] = args.token
if os.environ.get("GITHUB_TOKEN") is None:
    raise Exception("GITHUB_TOKEN is not set")

if args.key is not None:
    openai.api_key = args.key
elif os.environ.get("OPENAI_API_KEY") is not None:
    openai.api_key = os.environ.get("OPENAI_API_KEY")
else:
    raise Exception("OPENAI_API_KEY is not set")

if args.proxy is not None:
    openai.api_base = "http://" + args.proxy + "/v1/"
elif os.environ.get("OPENAI_PROXY") is not None:
    openai.api_base = "http://" + os.environ.get("OPENAI_PROXY") + "/v1/"
else:
    print("Warning: OPENAI_PROXY is not set")

def already_english(str):
    return len(str) == len(str.encode('utf-8'))

logs = []
logs.append(f"issue: {args.issue}")
logs.append(f"token: {len(os.environ.get('GITHUB_TOKEN'))}B")
logs.append(f"proxy: {openai.api_base}")
logs.append(f"key: {len(openai.api_key)}B")
print(f"run with {', '.join(logs)}")

api = args.issue.replace("https://github.com", "https://api.github.com/repos")
print(f"api: {api}")
headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
    "X-GitHub-Api-Version": "2022-11-28",
}

res = requests.get(api, headers=headers)
if res.status_code != 200:
    raise Exception(f"request failed, code={res.status_code}")

j_res = res.json()
title = j_res["title"]
body = j_res["body"]
comments_url = j_res["comments_url"]
print("")
print(f"===============ISSUE===============")
print(f"Url: {args.issue}")
print(f"Title: {title}")
print(f"Body:\n{body}\n")

messages = []
issue_changed = False
if already_english(title):
    print(f"Title is already english, skip")
elif TRANS_MAGIC in title:
    print(f"Title is already translated, skip")
else:
    issue_changed = True
    messages.append({"role": "user", "content": f"{PROMPT_TRANS}\n'{title}'"})
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
    )
    title_trans = completion.choices[0].message.content.strip('\'"')
    messages.append({"role": "assistant", "content": f"{title_trans}"})
    print(f"Title: {title_trans}")

if already_english(body):
    print(f"Body is already english, skip")
elif TRANS_MAGIC in body:
    print(f"Body is already translated, skip")
else:
    issue_changed = True
    messages.append({"role": "user", "content": f"{PROMPT_TRANS}\n'{body}'\n{PROMPT_SANDWICH}"})
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
    )
    body_trans = completion.choices[0].message.content.strip('\'"')
    messages.append({"role": "assistant", "content": f"{body_trans}"})
    print(f"Body:\n{body_trans}\n")

if not issue_changed:
    print(f"Nothing changed, skip")
else:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    res = requests.patch(api, headers=headers, json={
        'title': title_trans,
        'body': f"{body_trans}\n\n`{TRANS_MAGIC}`",
    })
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    print(f"Updated ok")

api = comments_url
headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
    "X-GitHub-Api-Version": "2022-11-28",
}

res = requests.get(api, headers=headers)
if res.status_code != 200:
    raise Exception(f"request failed, code={res.status_code}")

j_res = res.json()
for index, j_res_c in enumerate(j_res):
    c_url = j_res_c["url"]
    c_body = j_res_c["body"]
    print("")
    print(f"===============Comment(#{index+1})===============")
    print(f"URL: {c_url}")
    print(f"Body:\n{c_body}\n")

    if already_english(c_body):
        print(f"Body is already english, skip")
    elif TRANS_MAGIC in c_body:
        print(f"Already translated, skip")
    else:
        messages = []
        messages.append({"role": "user", "content": f"{PROMPT_TRANS}\n'{c_body}'"})
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )
        c_body_trans = completion.choices[0].message.content.strip('\'"')
        messages.append({"role": "assistant", "content": f"{c_body_trans}"})
        print(f"Body:\n{c_body_trans}\n")

        api = c_url
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        res = requests.patch(api, headers=headers, json={
            'body': f"{c_body_trans}\n\n`{TRANS_MAGIC}`",
        })
        if res.status_code != 200:
            raise Exception(f"request failed, code={res.status_code}")
        print(f"Updated ok")

