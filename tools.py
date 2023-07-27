import os, requests, openai, emoji
from urllib.parse import urlparse

PROMPT_TRANS_HEAD="Translate to english:"
PROMPT_TRANS_SANDWICH="Make sure to maintain the markdown structure."
PROMPT_REPHRASE_REFINE="Rephrase in a technical manner:"
TRANS_MAGIC="TRANS_BY_GPT3"
TRANS_DELIMETER = '\n\n'
TRANS_DELIMETER_PR = '---------'
LABEL_TRANS_NAME="TransByAI"
LABEL_REFINED_NAME="RefinedByAI"
LABEL_ENGLISH_NATIVE="EnglishNative"

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

def wrap_magic(body, extra_delimeter=''):
    if TRANS_MAGIC in body:
        return body

    magic = ''
    if extra_delimeter != '':
        magic = f"{TRANS_DELIMETER}{extra_delimeter}"
    magic = f"{magic}{TRANS_DELIMETER}`{TRANS_MAGIC}`"

    return f"{body}{magic}"

def gpt_translate(plaintext, trans_by_gpt):
    segments = split_segments(plaintext)
    final_trans = []
    real_translated = False
    messages = []
    for segment in segments:
        if TRANS_MAGIC in segment:
            trans_by_gpt = True
            print(f"Translate: Body segment is already translated, skip")
            final_trans.append(segment)
        elif already_english(segment):
            print(f"Translate: Body segment is already english, skip")
            final_trans.append(segment)
        else:
            real_translated = trans_by_gpt = True
            messages.append({"role": "user", "content": f"{PROMPT_TRANS_HEAD}\n'{segment}'\n{PROMPT_TRANS_SANDWICH}"})
            if len(messages) > 3:
                messages = messages[-3:]
            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.3,
            )
            segment_trans = completion.choices[0].message.content.strip('\'"')
            messages.append({"role": "assistant", "content": segment_trans})
            final_trans.append(segment_trans)
    plaintext_trans = "\n".join(final_trans).strip('\n')
    return (plaintext_trans, trans_by_gpt, real_translated)

def gpt_refine_pr(plaintext):
    messages = []
    messages.append({"role": "user", "content": f"{PROMPT_REPHRASE_REFINE}\n'{plaintext}'"})
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.3,
    )
    trans = completion.choices[0].message.content.strip('\'"')
    return trans

def get_graphql_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
        "X-Github-Next-Global-ID": "1",
    }

def parse_repository_url(url):
    """
    :param url: GitHub repository URL, for example, https://github.com/your-org/your-repository
    """
    return {
        'owner': urlparse(url).path.strip('/').split('/')[0],
        'name': urlparse(url).path.strip('/').split('/')[1]
    }

def parse_issue_url(url):
    """
    :param url: GitHub issue URL, for example, https://github.com/your-org/your-repository/issues/1235
    """
    return {
        'owner': urlparse(url).path.strip('/').split('/')[0],
        'name': urlparse(url).path.strip('/').split('/')[1],
        'number': int(urlparse(url).path.strip('/').split('/')[3])
    }

def parse_discussion_url(url):
    """
    :param url: GitHub issue URL, for example, https://github.com/your-org/your-repository/discussions/4421
    """
    return parse_issue_url(url)

def parse_pullrequest_url(url):
    """
    :param url: GitHub PullRequest URL, for example, https://github.com/your-org/your-repository/pull/3699
    """
    return parse_issue_url(url)

class GithubGraphQLException(Exception):
    def __init__(self, message, res):
        super().__init__(message)
        self.res = res
        self.text = res.text
        self.json = res.json()
        self.errors = None
        if 'errors' in self.json:
            self.errors = self.json['errors']
    def is_forbidden(self):
        if self.errors is not None and len(self.errors) > 0:
            for error in self.errors:
                if error['type'] == 'FORBIDDEN':
                    return True
        return False

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
    if 'errors' in j_res:
        raise GithubGraphQLException(f"request failed, {j_res}", res)

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
    if 'errors' in j_res:
        raise GithubGraphQLException(f"request failed, {j_res}", res)

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
        raise GithubGraphQLException(f"request failed, {j_res}", res)

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
    if 'errors' in j_res:
        raise GithubGraphQLException(f"request failed, {j_res}", res)

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
        raise GithubGraphQLException(f"request failed, {j_res}", res)

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
        raise GithubGraphQLException(f"request failed, {j_res}", res)

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
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "name": name, "owner": owner, "label": label
    }}, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")

    j_res = res.json()
    if 'errors' in j_res:
        raise GithubGraphQLException(f"request failed, {j_res}", res)

    id = j_res['data']['repository']['label']['id']
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
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "name": name, "owner": owner, "slug": category_slug
    }}, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")

    j_res = res.json()
    if 'errors' in j_res:
        raise GithubGraphQLException(f"request failed, {j_res}", res)

    id = j_res['data']['repository']['discussionCategory']['id']
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
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "id": owner_id, "labelIds": [label_id]
    }}, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")

    j_res = res.json()
    if 'errors' in j_res:
        raise GithubGraphQLException(f"request failed, {j_res}", res)

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
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "name": name, "owner": owner, "number": discussion_number
    }}, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")

    j_res = res.json()
    if 'errors' in j_res:
        raise GithubGraphQLException(f"request failed, {j_res}", res)

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
    res = requests.post('https://api.github.com/graphql', json={
        "query": query, "variables": variables
    }, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")

    j_res = res.json()
    if 'errors' in j_res:
        raise GithubGraphQLException(f"request failed, {j_res}", res)

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
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "id": id,
        "title": title,
        'body': body,
    }}, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")

    j_res = res.json()
    if 'errors' in j_res:
        raise GithubGraphQLException(f"request failed, {j_res}", res)

    return j_res['data']['updateDiscussion']['discussion']['id']

def search_issues(owner, name, sort, labels):
    '''
    Search GitHub issues, like https://github.com/your-org/your-repository/issues?q=is:issue+sort:comments-desc+-label:TransByAI+
    :param owner: For example, ossrs
    :param name: For example, srs
    :param sort: For example, sort:comments-desc
    :param label: For example, -label:TransByAI
    '''
    query = '''
        query ($query: String!) {
          search(
            query: $query
            type: ISSUE
            first: 10
          ) {
            nodes {
              ... on Issue {
                id
                title
                url
                comments {
                  totalCount
                }
              }
            }
          }
        }
    '''
    filter = f"repo:{owner}/{name} is:issue {sort} {' '.join(labels)}"
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "query": filter,
    }}, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")

    j_res = res.json()
    if 'errors' in j_res:
        raise GithubGraphQLException(f"request failed, {j_res}", res)

    return j_res['data']['search']['nodes']

def query_pullrequest(owner, name, pr_number):
    query = '''
        query ($name: String!, $owner: String!, $number: Int!) {
          repository(name: $name, owner: $owner) {
            pullRequest(number: $number) {
              id
              title
              body
              mergeable
              author {
                login
              }
              baseRef {
                name
                repository {
                  name
                  owner {
                    login
                  }
                }
              }
              headRef {
                name
                repository {
                  name
                  owner {
                    login
                  }
                }
              }
              participants(first: 100) {
                totalCount
                nodes {
                  login
                }
              }
              labels(first: 100) {
                totalCount
                nodes {
                  id
                  name
                }
              }
            }
          }
        }
    '''
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "name": name, "owner": owner, "number": pr_number
    }}, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")

    j_res = res.json()
    if 'errors' in j_res:
        raise GithubGraphQLException(f"request failed, {j_res}", res)

    total_labels = j_res['data']['repository']['pullRequest']['labels']['totalCount']
    if total_labels > 100:
        raise Exception(f"too many labels, count={total_labels} {j_res}")

    total_participants = j_res['data']['repository']['pullRequest']['participants']['totalCount']
    if total_participants > 100:
        raise Exception(f"too many participants, count={total_participants} {j_res}")

    return {
        "id": j_res['data']['repository']['pullRequest']['id'],
        "title": j_res['data']['repository']['pullRequest']['title'],
        "body": j_res['data']['repository']['pullRequest']['body'],
        "mergeable": j_res['data']['repository']['pullRequest']['mergeable'] == 'MERGEABLE',
        "author": j_res['data']['repository']['pullRequest']['author']['login'],
        "baseRef": j_res['data']['repository']['pullRequest']['baseRef'],
        "headRef": j_res['data']['repository']['pullRequest']['headRef'],
        "participants": j_res['data']['repository']['pullRequest']['participants']['nodes'],
        "labels": j_res['data']['repository']['pullRequest']["labels"]["nodes"],
    }

def query_pullrequest_for_trans(owner, name, pr_number):
    query = '''
        query ($name: String!, $owner: String!, $number: Int!) {
          repository(name: $name, owner: $owner) {
            pullRequest(number: $number) {
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
              reviews(first: 100) {
                totalCount
                nodes {
                  id
                  url
                  body
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
          }
        }
    '''
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "name": name, "owner": owner, "number": pr_number
    }}, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")

    j_res = res.json()
    if 'errors' in j_res:
        raise GithubGraphQLException(f"request failed, {j_res}", res)

    total_labels = j_res['data']['repository']['pullRequest']['labels']['totalCount']
    if total_labels > 100:
        raise Exception(f"too many labels, count={total_labels} {j_res}")

    total_comments = j_res['data']['repository']['pullRequest']['comments']['totalCount']
    if total_comments > 100:
        raise Exception(f"too many comments, count={total_comments} {j_res}")

    total_reviews = j_res['data']['repository']['pullRequest']['reviews']['totalCount']
    if total_reviews > 100:
        raise Exception(f"too many reviews, count={total_reviews} {j_res}")

    reviews = []
    for review in j_res['data']['repository']['pullRequest']['reviews']['nodes']:
        total_review_comments = review['comments']['totalCount']
        if total_review_comments > 100:
            raise Exception(f"too many review comments, count={total_review_comments} {j_res}")

    return {
        "id": j_res['data']['repository']['pullRequest']['id'],
        "title": j_res['data']['repository']['pullRequest']['title'],
        "body": j_res['data']['repository']['pullRequest']['body'],
        "labels": j_res['data']['repository']['pullRequest']["labels"]["nodes"],
        "comments": j_res['data']['repository']['pullRequest']["comments"]["nodes"],
        "reviews": j_res['data']['repository']['pullRequest']['reviews']['nodes'],
    }

def update_pullrequest(id, title, body):
    query = '''
        mutation ($id: ID!, $title: String!, $body: String!) {
          updatePullRequest(
            input: {pullRequestId: $id, title: $title, body: $body}
          ) {
            pullRequest {
              id
            }
          }
        }
    '''
    res = requests.post('https://api.github.com/graphql', json={"query": query, "variables": {
        "id": id, "title": title, "body": body
    }}, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")

    j_res = res.json()
    if 'errors' in j_res:
        raise GithubGraphQLException(f"request failed, {j_res}", res)

    return j_res['data']['updatePullRequest']['pullRequest']['id']

def update_pullrequest_review(id, body):
    query = '''
        mutation ($id: ID!, $body: String!) {
          updatePullRequestReview(
            input: {pullRequestReviewId: $id, body: $body}
          ) {
            pullRequestReview {
              id
            }
          }
        }
    '''
    variables = {
        "id": id,
        'body': body,
    }
    res = requests.post('https://api.github.com/graphql', json={
        "query": query, "variables": variables
    }, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")

    j_res = res.json()
    if 'errors' in j_res:
        raise GithubGraphQLException(f"request failed, {j_res}", res)

    return j_res['data']['updatePullRequestReview']['pullRequestReview']['id']

def update_pullrequest_review_comment(id, body):
    query = '''
        mutation ($id: ID!, $body: String!) {
          updatePullRequestReviewComment(
            input: {pullRequestReviewCommentId: $id, body: $body}
          ) {
            pullRequestReviewComment {
              id
            }
          }
        }
    '''
    variables = {
        "id": id,
        'body': body,
    }
    res = requests.post('https://api.github.com/graphql', json={
        "query": query, "variables": variables
    }, headers=get_graphql_headers())
    if res.status_code != 200:
        raise Exception(f"request failed, code={res.status_code}")

    j_res = res.json()
    if 'errors' in j_res:
        raise GithubGraphQLException(f"request failed, {j_res}", res)

    return j_res['data']['updatePullRequestReviewComment']['pullRequestReviewComment']['id']
