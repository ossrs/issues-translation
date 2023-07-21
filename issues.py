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
LABEL_NAME="TransByAI"
LABEL_ID=5758178147

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

issue_api = args.issue.replace("https://github.com", "https://api.github.com/repos")
print(f"api: {issue_api}")
headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
    "X-GitHub-Api-Version": "2022-11-28",
}

res = requests.get(issue_api, headers=headers)
if res.status_code != 200:
    raise Exception(f"request failed, code={res.status_code}")

j_issue_res = res.json()
comments_url = j_issue_res["comments_url"]

headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
    "X-GitHub-Api-Version": "2022-11-28",
}

res = requests.get(comments_url, headers=headers)
if res.status_code != 200:
    raise Exception(f"request failed, code={res.status_code}")

comment_trans_by_gpt = False
j_res = res.json()
for index, j_res_c in enumerate(j_res):
    c_url = j_res_c["url"]
    c_body = j_res_c["body"]
    print("")
    print(f"===============Comment(#{index+1})===============")
    print(f"URL: {c_url}")
    print(f"Body:\n{c_body}\n")

    print(f"Updating......")
    if TRANS_MAGIC in c_body:
        comment_trans_by_gpt = True
        print(f"Already translated, skip")
    elif already_english(c_body):
        print(f"Body is already english, skip")
    else:
        comment_trans_by_gpt = True
        messages = []
        messages.append({"role": "user", "content": f"{PROMPT_TRANS}\n'{c_body}'"})
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )
        c_body_trans = completion.choices[0].message.content.strip('\'"')
        messages.append({"role": "assistant", "content": f"{c_body_trans}"})
        print(f"Body:\n{c_body_trans}\n")

        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        res = requests.patch(c_url, headers=headers, json={
            'body': f"{c_body_trans}\n\n`{TRANS_MAGIC}`",
        })
        if res.status_code != 200:
            raise Exception(f"request failed, code={res.status_code}")
        print(f"Updated ok")

title = j_issue_res["title"]
labels = j_issue_res["labels"]
body = j_issue_res["body"]

has_gpt_label = False
labels_for_print=[]
for label in labels:
    if label["name"] == LABEL_NAME and label["id"] == LABEL_ID:
        has_gpt_label = True
    labels_for_print.append(f"{label['id']}({label['name']})")
print("")
print(f"===============ISSUE===============")
print(f"Url: {args.issue}")
print(f"Title: {title}")
print(f"Labels: {', '.join(labels_for_print)}")
print(f"Body:\n{body}\n")

print(f"Updating......")
messages = []
issue_changed = False
issue_trans_by_gpt = False
title_trans = title
body_trans = body
if TRANS_MAGIC in title:
    issue_trans_by_gpt = True
    print(f"Title is already translated, skip")
elif already_english(title):
    print(f"Title is already english, skip")
else:
    issue_changed = True
    issue_trans_by_gpt = True
    messages.append({"role": "user", "content": f"{PROMPT_TRANS}\n'{title}'"})
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
    )
    title_trans = completion.choices[0].message.content.strip('\'"')
    messages.append({"role": "assistant", "content": f"{title_trans}"})
    print(f"Title: {title_trans}")

if TRANS_MAGIC in body:
    issue_trans_by_gpt = True
    print(f"Body is already translated, skip")
elif already_english(body):
    print(f"Body is already english, skip")
else:
    issue_changed = True
    issue_trans_by_gpt = True
    body_segments = body.split("```")
    final_segments_trans = []
    for body_segment in body_segments:
        if already_english(body_segment):
            print(f"Body segment is already english, skip: {len(body_segment)}B")
            final_segments_trans.append(body_segment)
        else:
            print(f"Translating body segment: {len(body_segment)}B")
            messages.append({"role": "user", "content": f"{PROMPT_TRANS}\n'{body_segment}'\n{PROMPT_SANDWICH}"})
            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
            )
            body_segment_trans = completion.choices[0].message.content.strip('\'"')
            messages.append({"role": "assistant", "content": f"{body_segment_trans[:128]}"})
            final_segments_trans.append(body_segment_trans)
    body_trans = "\n```\n".join(final_segments_trans)
    body_trans = f"{body_trans}\n\n`{TRANS_MAGIC}`"
    print(f"Body:\n{body_trans}\n")

any_by_gpt = comment_trans_by_gpt or issue_trans_by_gpt
if not any_by_gpt or has_gpt_label:
    print(f"Label is already set, skip")
else:
    issue_changed = True
    labels.append({"id": LABEL_ID, "name": LABEL_NAME})
    labels_for_print.append(f"{LABEL_ID}({LABEL_NAME})")
    print(f"Labels: {', '.join(labels_for_print)}")

if not issue_changed:
    print(f"Nothing changed, skip")
else:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    res = requests.patch(issue_api, headers=headers, json={
        'title': title_trans,
        'labels': labels,
        'body': body_trans,
    })
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    print(f"Updated ok")

