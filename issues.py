import time
starttime = time.time()

from urllib.parse import urlparse
import os, openai, argparse, requests

parser = argparse.ArgumentParser(description="Translation")
parser.add_argument("--input", type=str, required=True, help="GitHub issue URL, for example, https://github.com/ossrs/srs/issues/3692")
parser.add_argument("--token", type=str, required=False, help="GitHub access token, for example, github_pat_xxx_yyyyyy")
parser.add_argument("--proxy", type=str, required=False, help="OpenAI API proxy, for example, x.y.z")
parser.add_argument("--key", type=str, required=False, help="OpenAI API key, for example, xxxyyyzzz")

PROMPT_TRANS="translate to english:"
PROMPT_SANDWICH="Make sure to maintain the markdown structure."
TRANS_MAGIC="TRANS_BY_GPT3"
LABEL_NAME="TransByAI"

def already_english(str):
    return len(str) == len(str.encode('utf-8'))

def split_segments(body):
    lines = body.split('\n')
    matches = []
    current_matches = []
    is_english = already_english(lines[0])
    for line in lines:
        if line == '':
            current_matches.append('\n')
            continue
        if already_english(line) == is_english:
            current_matches.append(line)
        else:
            matches.append('\n'.join(current_matches))
            current_matches = [line]
            is_english = already_english(line)
    matches.append('\n'.join(current_matches))
    return matches

def gpt_translate(plaintext, trans_by_gpt):
    segments = split_segments(plaintext)
    final_trans = []
    real_translated = False
    messages = []
    for segment in segments:
        if TRANS_MAGIC in segment:
            trans_by_gpt = True
            print(f"Body segment is already translated, skip")
            final_trans.append(segment)
        elif already_english(segment):
            print(f"Body segment is already english, skip")
            final_trans.append(segment)
        else:
            real_translated = trans_by_gpt = True
            messages.append({"role": "user", "content": f"{PROMPT_TRANS}\n'{segment}'"})
            if len(messages) > 3:
                messages = messages[-3:]
            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
            )
            segment_trans = completion.choices[0].message.content.strip('\'"')
            messages.append({"role": "assistant", "content": segment_trans})
            final_trans.append(segment_trans)
    plaintext_trans = "\n".join(final_trans).strip('\n')
    return (plaintext_trans, trans_by_gpt, real_translated)

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

logs = []
logs.append(f"issue: {args.input}")
logs.append(f"token: {len(os.environ.get('GITHUB_TOKEN'))}B")
logs.append(f"proxy: {len(openai.api_base)}B")
logs.append(f"key: {len(openai.api_key)}B")
print(f"run with {', '.join(logs)}")

def parse_github_url(url):
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.strip('/').split('/')

    if len(path_parts) < 4 or path_parts[2] != 'issues':
        raise ValueError("Invalid URL format")

    owner = path_parts[0]
    name = path_parts[1]
    number = int(path_parts[3])

    return {
        'owner': owner,
        'name': name,
        'number': number
    }
variables = parse_github_url(args.input)
print(f"parsed input: {variables}")

issue_api = args.input.replace("https://github.com", "https://api.github.com/repos")
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
comments_url = f"{j_issue_res['comments_url']}?per_page=100"

comments = j_issue_res['comments']
if comments > 100:
    raise Exception(f"too many comments, {comments}")
print(f"comments: {comments}, url: {comments_url}")

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
    (c_body_trans, comment_trans_by_gpt, real_translated) = gpt_translate(c_body, comment_trans_by_gpt)
    if real_translated:
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

id = j_issue_res["node_id"]
title = j_issue_res["title"]
body = j_issue_res["body"]

has_gpt_label = False
labels4print=[]
for label in j_issue_res["labels"]:
    if label["name"] == LABEL_NAME:
        has_gpt_label = True
    labels4print.append(f"{label['id']}({label['name']})")
print("")
print(f"===============ISSUE===============")
print(f"ID: {id}")
print(f"Url: {args.input}")
print(f"Title: {title}")
print(f"Labels: {', '.join(labels4print)}")
print(f"Body:\n{body}\n")

print(f"Updating......")
issue_changed = False
issue_trans_by_gpt = False
title_trans = title
body_trans = body
if already_english(title):
    print(f"Title is already english, skip")
else:
    (title_trans, trans_by_gpt, real_translated) = gpt_translate(title, issue_trans_by_gpt)
    if trans_by_gpt:
        issue_trans_by_gpt = True
    if real_translated:
        issue_changed = True
        print(f"Title: {title_trans}")

if TRANS_MAGIC in body:
    issue_trans_by_gpt = True
    print(f"Body is already translated, skip")
elif already_english(body):
    print(f"Body is already english, skip")
else:
    (body_trans, trans_by_gpt, real_translated) = gpt_translate(body, issue_trans_by_gpt)
    if trans_by_gpt:
        issue_trans_by_gpt = True
    if real_translated:
        issue_changed = True
        print(f"Body:\n{body_trans}\n")

any_by_gpt = comment_trans_by_gpt or issue_trans_by_gpt
if not any_by_gpt or has_gpt_label:
    print(f"Label is already set, skip")
else:
    query = '''
        query($name: String!, $owner: String!, $label: String!) {
          repository(name: $name, owner: $owner) {
            label(name: $label) {
              id
            }
          }
        }
    '''
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
    }
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "name": variables['name'], "owner": variables['owner'], "label": LABEL_NAME
    }}, headers=headers)
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    LABEL_ID = res.json()['data']['repository']['label']['id']
    print(f"Query LABEL_NAME={LABEL_NAME}, got LABEL_ID={LABEL_ID}")

    query = '''
        mutation ($id: ID!, $labelIds: [ID!]!) {
          addLabelsToLabelable(
            input: {labelableId: $id, labelIds: $labelIds}
          ) {
            labelable {
              labels {
                totalCount
              }
            }
          }
        }
    '''
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
    }
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "id": id, "labelIds": [LABEL_ID]
    }}, headers=headers)
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    print(f"Add label ok, {LABEL_ID}({LABEL_NAME})")

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
        'body': f"{body_trans}\n\n`{TRANS_MAGIC}`"
    })
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    print(f"Updated ok")

