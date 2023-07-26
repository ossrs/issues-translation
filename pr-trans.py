import os, openai, argparse
import tools

import dotenv
dotenv.load_dotenv(dotenv.find_dotenv())

parser = argparse.ArgumentParser(description="Translation")
parser.add_argument("--input", type=str, required=True, help="GitHub PR URL, for example, https://github.com/your-org/your-repository/pull/3699")
parser.add_argument("--token", type=str, required=False, help="GitHub access token, for example, github_pat_xxx_yyyyyy")
parser.add_argument("--proxy", type=str, required=False, help="OpenAI API proxy, for example, x.y.z")
parser.add_argument("--key", type=str, required=False, help="OpenAI API key, for example, xxxyyyzzz")

args = parser.parse_args()
tools.github_token_init(args.token)
tools.openai_init(args.key, args.proxy)

logs = []
logs.append(f"PR: {args.input}")
logs.append(f"token: {len(os.environ.get('GITHUB_TOKEN'))}B")
logs.append(f"proxy: {len(openai.api_base)}B")
logs.append(f"key: {len(openai.api_key)}B")
print(f"run with {', '.join(logs)}")

pr = tools.parse_pullrequest_url(args.input)
j_pr_res = tools.query_pullrequest_for_trans(pr["owner"], pr["name"], pr["number"])

comments = j_pr_res['comments']
comment_trans_by_gpt = False
for index, j_res_c in enumerate(comments):
    c_id = j_res_c["id"]
    c_url = j_res_c["url"]
    c_body = j_res_c["body"]
    print("")
    print(f"===============Comment(#{index+1})===============")
    print(f"ID: {c_id}")
    print(f"URL: {c_url}")
    print(f"Body:\n{c_body}\n")

    print(f"Updating......")
    (c_body_trans, comment_trans_by_gpt, real_translated) = tools.gpt_translate(c_body, comment_trans_by_gpt)
    if real_translated:
        print(f"Body:\n{c_body_trans}\n")
        try:
            tools.update_issue_comment(c_id, tools.wrap_magic(c_body_trans))
            print(f"Updated ok")
        except tools.GithubGraphQLException as e:
            if e.is_forbidden():
                print(f"Warning!!! Ignore update comment {c_id} failed, forbidden, {e.errors}")
            else:
                raise e

j_reviews_res = j_pr_res['reviews']
for index, j_res_c in enumerate(j_reviews_res):
    c_id = j_res_c["id"]
    c_comments = j_res_c["comments"]['totalCount']
    c_url = j_res_c["url"]
    c_body = j_res_c["body"]
    print("")
    print(f"===============Review(#{index+1})===============")
    print(f"ID: {c_id}")
    print(f"Comments: {c_comments}")
    print(f"URL: {c_url}")
    print(f"Body:\n{c_body}\n")

    print(f"Updating......")
    if tools.TRANS_MAGIC in c_body:
        comment_trans_by_gpt = True
        print(f"Already translated, skip")
    elif tools.already_english(c_body):
        print(f"Body is already english, skip")
    else:
        (c_body_trans, comment_trans_by_gpt, real_translated) = tools.gpt_translate(c_body, comment_trans_by_gpt)
        if real_translated:
            print(f"Body:\n{c_body_trans}\n")
            tools.update_pullrequest_review(c_id, tools.wrap_magic(c_body_trans))
            print(f"Updated ok")

    for position, j_res_c_reply in enumerate(j_res_c["comments"]["nodes"]):
        reply_id = j_res_c_reply["id"]
        reply_url = j_res_c_reply["url"]
        reply_body = j_res_c_reply["body"]
        print(f"---------------ReviewComment(#{position+1})---------------")
        print(f"ID: {reply_id}")
        print(f"URL: {reply_url}")
        print(f"Body:\n{reply_body}\n")

        print(f"Updating......")
        if tools.TRANS_MAGIC in reply_body:
            comment_trans_by_gpt = True
            print(f"Already translated, skip")
        elif tools.already_english(reply_body):
            print(f"Body is already english, skip")
        else:
            (reply_body_trans, comment_trans_by_gpt, real_translated) = tools.gpt_translate(reply_body, comment_trans_by_gpt)
            if real_translated:
                print(f"Body:\n{reply_body_trans}\n")
                tools.update_pullrequest_review_comment(reply_id, tools.wrap_magic(reply_body_trans))
                print(f"Updated ok")

id = j_pr_res["id"]
title = j_pr_res["title"]
body = j_pr_res["body"]

has_gpt_label = False
labels4print=[]
for label in j_pr_res["labels"]:
    if label["name"] == tools.LABEL_TRANS_NAME:
        has_gpt_label = True
    labels4print.append(f"{label['id']}({label['name']})")
print("")
print(f"===============PullRequest===============")
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
if tools.already_english(title):
    print(f"Title is already english, skip")
else:
    (title_trans, trans_by_gpt, real_translated) = tools.gpt_translate(title, issue_trans_by_gpt)
    if trans_by_gpt:
        issue_trans_by_gpt = True
    if real_translated:
        issue_changed = True
        print(f"Title: {title_trans}")

if tools.TRANS_MAGIC in body:
    issue_trans_by_gpt = True
    print(f"Body is already translated, skip")
elif tools.already_english(body):
    print(f"Body is already english, skip")
else:
    (body_trans, trans_by_gpt, real_translated) = tools.gpt_translate(body, issue_trans_by_gpt)
    if trans_by_gpt:
        issue_trans_by_gpt = True
    if real_translated:
        issue_changed = True
        print(f"Body:\n{body_trans}\n")

if not issue_changed:
    print(f"Nothing changed, skip")
else:
    tools.update_pullrequest(id, title_trans, tools.wrap_magic(body_trans))
    print(f"Updated ok")

any_by_gpt = comment_trans_by_gpt or issue_trans_by_gpt
if not any_by_gpt or has_gpt_label:
    print(f"Label is already set, skip")
else:
    print(f"Add label {tools.LABEL_TRANS_NAME}")
    label_id = tools.query_label_id(pr["owner"], pr["name"], tools.LABEL_TRANS_NAME)
    print(f"Query LABEL_TRANS_NAME={tools.LABEL_TRANS_NAME}, got LABEL_ID={label_id}")

    tools.add_label(id, label_id)
    print(f"Add label ok, {label_id}({tools.LABEL_TRANS_NAME})")

print("\nOK\n")
