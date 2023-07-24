import sys
import time
starttime = time.time()

from urllib.parse import urlparse
import os, sys, openai, argparse, requests

parser = argparse.ArgumentParser(description="Translation")
parser.add_argument("--input", type=str, required=True, help="GitHub discussion URL, for example, https://github.com/orgs/ossrs/discussions/3700")
parser.add_argument("--token", type=str, required=False, help="GitHub access token, for example, github_pat_xxx_yyyyyy")
parser.add_argument("--proxy", type=str, required=False, help="OpenAI API proxy, for example, x.y.z")
parser.add_argument("--key", type=str, required=False, help="OpenAI API key, for example, xxxyyyzzz")

PROMPT_TRANS="translate to english:"
PROMPT_SANDWICH="Make sure to maintain the markdown structure."
TRANS_MAGIC="TRANS_BY_GPT3"
LABEL_NAME="TransByAI"

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
logs.append(f"dicussion: {args.input}")
logs.append(f"token: {len(os.environ.get('GITHUB_TOKEN'))}B")
logs.append(f"proxy: {len(openai.api_base)}B")
logs.append(f"key: {len(openai.api_key)}B")
print(f"run with {', '.join(logs)}")

def parse_github_url(url):
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.strip('/').split('/')

    if len(path_parts) < 4 or path_parts[2] != 'discussions':
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
query($name: String!, $owner: String!, $number: Int!) {
  repository(name: $name, owner: $owner) {
    discussion(number: $number) {
      id
      body
      title
      number
      labels(first: 100) {
        totalCount
        nodes {
          id
          name
        }
      }
      comments(first: 100) {
        totalCount
        nodes {
          id
          url
          body
          replies(first: 100) {
            totalCount
            nodes {
              id
              url
              body
            }
            pageInfo {
              endCursor
              startCursor
            }
          }
        }
        pageInfo {
          endCursor
          startCursor
        }
      }
    }
  }
}
'''
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
}
res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": variables}, headers=headers)
if res.status_code != 200:
    raise Exception(f"request failed, code={res.status_code}")
j_discussion_res = res.json()

totalCount = j_discussion_res['data']['repository']['discussion']['comments']['totalCount']
if totalCount > 100:
    raise Exception(f"comments.totalCount > 100, {totalCount} of {j_discussion_res}")

comment_trans_by_gpt = False
j_res = j_discussion_res['data']['repository']['discussion']['comments']['nodes']
for index, j_res_c in enumerate(j_res):
    c_id = j_res_c["id"]
    c_replies = j_res_c["replies"]['totalCount']
    c_url = j_res_c["url"]
    c_body = j_res_c["body"]
    print("")
    print(f"===============Comment(#{index+1})===============")
    print(f"ID: {c_id}")
    print(f"Replies: {c_replies}")
    print(f"URL: {c_url}")
    print(f"Body:\n{c_body}\n")

    totalCount = j_res_c["replies"]["totalCount"]
    if totalCount > 100:
        raise Exception(f"comments.totalCount > 100, {totalCount} of {j_res_c}")

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

        query = '''
            mutation ($id: ID!, $body: String!) {
              updateDiscussionComment(
                input: {commentId: $id, body: $body}
              ) {
                comment {
                  id
                }
              }
            }
        '''
        variables = {
            "id": c_id,
            "body": f"{c_body_trans}\n\n`{TRANS_MAGIC}`"
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
        }
        res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": variables}, headers=headers)
        if res.status_code != 200:
            raise Exception(f"request failed, code={res.status_code}")
        if 'errors' in res.json():
            raise Exception(f"request failed, {res.text}")
        print(f"Updated ok")

    for position, j_res_c_reply in enumerate(j_res_c["replies"]["nodes"]):
        reply_id = j_res_c_reply["id"]
        reply_url = j_res_c_reply["url"]
        reply_body = j_res_c_reply["body"]
        print(f"---------------Reply(#{position+1})---------------")
        print(f"ID: {reply_id}")
        print(f"URL: {reply_url}")
        print(f"Body:\n{reply_body}\n")

        print(f"Updating......")
        if TRANS_MAGIC in reply_body:
            comment_trans_by_gpt = True
            print(f"Already translated, skip")
        elif already_english(reply_body):
            print(f"Body is already english, skip")
        else:
            comment_trans_by_gpt = True
            messages = []
            messages.append({"role": "user", "content": f"{PROMPT_TRANS}\n'{reply_body}'"})
            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
            )
            reply_body_trans = completion.choices[0].message.content.strip('\'"')
            messages.append({"role": "assistant", "content": f"{reply_body_trans}"})
            print(f"Body:\n{reply_body_trans}\n")

            query = '''
                mutation ($id: ID!, $body: String!) {
                  updateDiscussionComment(
                    input: {commentId: $id, body: $body}
                  ) {
                    comment {
                      id
                    }
                  }
                }
            '''
            variables = {
                "id": reply_id,
                "body": f"{reply_body_trans}\n\n`{TRANS_MAGIC}`"
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
            }
            res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": variables}, headers=headers)
            if res.status_code != 200:
                raise Exception(f"request failed, code={res.status_code}")
            r0 = res.json()
            if 'errors' in r0:
                raise Exception(f"request failed, {r0}")
            print(f"Updated ok")

id = j_discussion_res['data']['repository']['discussion']["id"]
title = j_discussion_res['data']['repository']['discussion']["title"]
labels = j_discussion_res['data']['repository']['discussion']["labels"]["nodes"]
body = j_discussion_res['data']['repository']['discussion']["body"]

totalCount = j_discussion_res['data']['repository']['discussion']["labels"]['totalCount']
if totalCount > 100:
    raise Exception(f"labels.totalCount > 100, {totalCount} of {j_discussion_res}")

has_gpt_label = False
labels_for_print=[]
for label in labels:
    if label["name"] == LABEL_NAME and label["id"] == LABEL_ID:
        has_gpt_label = True
    labels_for_print.append(f"{label['id']}({label['name']})")
print("")
print(f"===============ISSUE===============")
print(f"ID: {id}")
print(f"Url: {args.input}")
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
    query = '''
        mutation ($id: ID!, $title: String!, $body: String!) {
          updateDiscussion(
            input: {discussionId: $id, title: $title, body: $body}
          ) {
            discussion {
              number
            }
          }
        }
    '''
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
    }
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "id": id, "title": title_trans, "body": body_trans,
    }}, headers=headers)
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    print(f"Updated ok")

