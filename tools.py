import os, requests, openai, emoji
from urllib.parse import urlparse

PROMPT_TRANS="translate to english:"
PROMPT_SANDWICH="Make sure to maintain the markdown structure."
TRANS_MAGIC="TRANS_BY_GPT3"
LABEL_NAME="TransByAI"

def github_token_init(token):
    if token is not None:
        os.environ["GITHUB_TOKEN"] = token
    if os.environ.get("GITHUB_TOKEN") is None:
        raise Exception("GITHUB_TOKEN is not set")

def openai_init(key, proxy):
    if key is not None:
        openai.api_key = key
    elif os.environ.get("OPENAI_API_KEY") is not None:
        openai.api_key = os.environ.get("OPENAI_API_KEY")
    else:
        raise Exception("OPENAI_API_KEY is not set")

    if proxy is not None:
        openai.api_base = "http://" + proxy + "/v1/"
    elif os.environ.get("OPENAI_PROXY") is not None:
        openai.api_base = "http://" + os.environ.get("OPENAI_PROXY") + "/v1/"
    else:
        print("Warning: OPENAI_PROXY is not set")

def already_english(str):
    for c in str:
        if len(c) != len(c.encode('utf-8')) and emoji.emoji_count(c) == 0:
            return False
    return True

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

def wrap_magic(body):
    return body if TRANS_MAGIC in body else f"{body}\n\n`{TRANS_MAGIC}`"

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

def get_graphql_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
        "X-Github-Next-Global-ID": "1",
    }

def parse_repository_url(url):
    """
    :param url: GitHub repository URL, for example, https://github.com/ossrs/srs
    """
    return {
        'owner': urlparse(url).path.strip('/').split('/')[0],
        'name': urlparse(url).path.strip('/').split('/')[1]
    }

def parse_issue_url(url):
    """
    :param url: GitHub issue URL, for example, http://github.com/ossrs/srs/issues/1
    """
    return {
        'owner': urlparse(url).path.strip('/').split('/')[0],
        'name': urlparse(url).path.strip('/').split('/')[1],
        'number': int(urlparse(url).path.strip('/').split('/')[3])
    }

def parse_discussion_url(url):
    """
    :param url: GitHub issue URL, for example, http://github.com/ossrs/srs/discussions/1
    """
    return parse_issue_url(url)

def query_repository_id(owner, name):
    query = '''
        query ($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) {
            id
          }
        }
    '''
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "owner": owner, "name": name,
    }}, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    j_res = res.json()
    repository_id = j_res['data']['repository']['id']
    return repository_id

def create_issue(repository_id, title, body):
    query = '''
        mutation ($repositoryId: ID!, $title: String!, $body: String!) {
          createIssue(input: {repositoryId: $repositoryId, title: $title, body: $body}) {
            issue {
              id
              url
            }
          }
        }
    '''
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "repositoryId": repository_id, "title": title, "body": body,
    }}, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    j_res = res.json()
    issue_id = j_res['data']['createIssue']['issue']['id']
    issue_url = j_res['data']['createIssue']['issue']['url']
    return (issue_id, issue_url)

def create_discussion(repository_id, title, body, category_id):
    query = '''
        mutation ($repositoryId: ID!, $title: String!, $body: String!, $categoryId: ID!) {
          createDiscussion(input: {repositoryId: $repositoryId, title: $title, body: $body, categoryId: $categoryId}) {
            discussion {
              id
              url
            }
          }
        }
    '''
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "repositoryId": repository_id, "title": title, "body": body, "categoryId": category_id,
    }}, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    j_res = res.json()
    if 'errors' in j_res:
        raise Exception(f"create discussion failed, {j_res}")

    discussion_id = j_res['data']['createDiscussion']['discussion']['id']
    discussion_url = j_res['data']['createDiscussion']['discussion']['url']
    return (discussion_id, discussion_url)

def query_issue(owner, name, issue_number):
    query = '''
        query ($owner: String!, $name: String!, $number: Int!) {
          repository(name: $name, owner: $owner) {
            issue(number: $number) {
              id
              title
              body
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
                }
              }
            }
          }
        }
    '''
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "owner": owner, "name": name, "number": issue_number,
    }}, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    j_res = res.json()

    total_labels = j_res['data']['repository']['issue']['labels']['totalCount']
    if total_labels > 100:
        raise Exception(f"too many labels, count={total_labels} {j_res}")

    total_comments = j_res['data']['repository']['issue']['comments']['totalCount']
    if total_comments > 100:
        raise Exception(f"too many comments, count={total_comments} {j_res}")
    return {
        'id': j_res['data']['repository']['issue']['id'],
        'title': j_res['data']['repository']['issue']['title'],
        'body': j_res['data']['repository']['issue']['body'],
        'labels': j_res['data']['repository']['issue']['labels']['nodes'],
        "comments": j_res['data']['repository']['issue']['comments']['nodes'],
    }

def update_issue_comment(id, body):
    query = '''
        mutation ($id: ID!, $body:String!) {
          updateIssueComment(input: {id: $id, body: $body}) {
            issueComment {
              id
            }
          }
        }
    '''
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "id": id, "body": body,
    }}, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    j_res = res.json()

    if 'errors' in j_res:
        raise Exception(f"request failed, {j_res}")
    return j_res['data']['updateIssueComment']['issueComment']['id']

def update_issue(id, title, body):
    query = '''
        mutation ($id: ID!, $title:String!, $body: String!) {
          updateIssue(input: {id: $id, body: $body, title: $title}) {
            issue {
              id
            }
          }
        }
    '''
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "id": id, "title": title, "body": body,
    }}, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    j_res = res.json()

    if 'errors' in j_res:
        raise Exception(f"request failed, {j_res}")
    return j_res['data']['updateIssue']['issue']['id']

def query_label_id(owner, name, label):
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
        "name": name, "owner": owner, "label": label
    }}, headers=headers)
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    id = res.json()['data']['repository']['label']['id']
    return id

def query_catetory_id(owner, name, category_slug):
    query = '''
        query ($name:String!, $owner: String!, $slug: String!) {
          repository(name: $name, owner: $owner) {
            discussionCategory(slug:$slug) {
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
        "name": name, "owner": owner, "slug": category_slug
    }}, headers=headers)
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    id = res.json()['data']['repository']['discussionCategory']['id']
    return id

def add_label(owner_id, label_id):
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
        "id": owner_id, "labelIds": [label_id]
    }}, headers=headers)
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    j_res = res.json()
    return j_res['data']['addLabelsToLabelable']['labelable']['labels']['totalCount']

def query_discussion(owner, name, discussion_number):
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
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "name": name, "owner": owner, "number": discussion_number
    }}, headers=headers)
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    j_res = res.json()

    totalCount = j_res['data']['repository']['discussion']['comments']['totalCount']
    if totalCount > 100:
        raise Exception(f"comments.totalCount > 100, {totalCount} of {j_res}")

    totalCount = j_res['data']['repository']['discussion']["labels"]['totalCount']
    if totalCount > 100:
        raise Exception(f"labels.totalCount > 100, {totalCount} of {j_res}")

    j_nodes = j_res['data']['repository']['discussion']['comments']['nodes']
    for index, j_node in enumerate(j_nodes):
        totalCount = j_node["replies"]["totalCount"]
        if totalCount > 100:
            raise Exception(f"comments[{index}].replies.totalCount > 100, {totalCount} of {j_node}")
    return {
        "id": j_res['data']['repository']['discussion']['id'],
        "title": j_res['data']['repository']['discussion']['title'],
        "body": j_res['data']['repository']['discussion']['body'],
        "labels": j_res['data']['repository']['discussion']["labels"]["nodes"],
        "comments": j_res['data']['repository']['discussion']['comments']['nodes'],
    }

def update_discussion_comment(id, body):
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
        "id": id,
        'body': body,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
    }
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": variables}, headers=headers)
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    j_res = res.json()
    if 'errors' in res.json():
        raise Exception(f"request failed, {res.text}")
    return j_res['data']['updateDiscussionComment']['comment']['id']

def update_discussion(id, title, body):
    query = '''
        mutation ($id: ID!, $title: String!, $body: String!) {
          updateDiscussion(
            input: {discussionId: $id, title: $title, body: $body}
          ) {
            discussion {
              id
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
        "id": id,
        "title": title,
        'body': body,
    }}, headers=headers)
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")
    j_res = res.json()
    return j_res['data']['updateDiscussion']['discussion']['id']