import os, openai, argparse, tools

import dotenv
dotenv.load_dotenv(dotenv.find_dotenv())

parser = argparse.ArgumentParser(description="Translation")
parser.add_argument("--input", type=str, required=True, help="GitHub issue URL, for example, https://github.com/your-org/your-repository/pull/3699")
parser.add_argument("--token", type=str, required=False, help="GitHub access token, for example, github_pat_xxx_yyyyyy")
parser.add_argument("--proxy", type=str, required=False, help="OpenAI API proxy, for example, x.y.z")
parser.add_argument("--key", type=str, required=False, help="OpenAI API key, for example, xxxyyyzzz")
parser.add_argument("--title", type=bool, default=False, required=False, help="Whether rephrase title, True or False(default)")
parser.add_argument("--body", type=bool, default=False, required=False, help="Whether rephrase body, True or False(default)")

args = parser.parse_args()
tools.github_token_init(args.token)
tools.openai_init(args.key, args.proxy)

if not args.title and not args.body:
    print(f"Error: --title or --body must be specified")
    exit(0)

logs = []
logs.append(f"issue: {args.input}")
logs.append(f"token: {len(os.environ.get('GITHUB_TOKEN'))}B")
logs.append(f"proxy: {len(openai.api_base)}B")
logs.append(f"key: {len(openai.api_key)}B")
logs.append(f"title: {args.title}")
logs.append(f"body: {args.body}")
print(f"run with {', '.join(logs)}")

pr = tools.parse_pullrequest_url(args.input)
j_pr = tools.query_pullrequest(pr["owner"], pr["name"], pr["number"])
pr_id = j_pr["id"]
pr_title = j_pr["title"]
pr_body = j_pr["body"]
pr_mergeable = j_pr["mergeable"]
pr_author = j_pr["author"]
pr_base_ref_repo = j_pr["baseRef"]["repository"]["owner"]["login"] + "/" + j_pr["baseRef"]["repository"]["name"]
pr_base_ref_name = j_pr["baseRef"]["name"]
pr_head_ref_repo = j_pr["headRef"]["repository"]["owner"]["login"] + "/" + j_pr["headRef"]["repository"]["name"]
pr_head_ref_name = j_pr["headRef"]["name"]
pr_coauthors = []
for node in j_pr["participants"]:
    login = node["login"]
    if login == 'ghost':
        continue

    login_env = f"USER_{login.lower().replace('-', '_')}"
    email = os.getenv(login_env)
    if login == pr_author:
        continue
    if email is None:
        print(f"Warning: {login_env} is not set, for example: \nUSER_xiaozhihong='john <hondaxiao@tencent.com>'")
        continue
    pr_coauthors.append(f"Co-authored-by: {email}")
print("")

has_gpt_label = False
labels4print=[]
for label in j_pr["labels"]:
    if label["name"] == tools.LABEL_REFINED_NAME:
        has_gpt_label = True
    labels4print.append(f"{label['id']}({label['name']})")

print(f"===============Pull Request===============")
print(f"ID: {pr_id}")
print(f"Title: {pr_title}")
print(f"URL: {args.input}")
print(f"Mergeable: {pr_mergeable}")
print(f"Author: {pr_author}")
print(f"Base Ref: {pr_base_ref_repo} {pr_base_ref_name}")
print(f"Head Ref: {pr_head_ref_repo} {pr_head_ref_name}")
print(f"Labels: {', '.join(labels4print)}")
print(f"CoAuthors: {pr_coauthors}")
print(f"Body:\n{pr_body}\n")

pr_title_suffix = None
if '. v' in pr_title:
    pr_title_suffix = pr_title.split('. v')[1]
    pr_title = pr_title.split('. v')[0]

extra_metadatas = []
if tools.TRANS_DELIMETER_PR in pr_body:
    print(f"===============Remove CoAuthors in body===============")
    segments = pr_body.split(tools.TRANS_DELIMETER_PR)
    text_segments = []
    for segment in segments:
        if tools.TRANS_MAGIC in segment:
            extra_metadatas.append(segment.strip())
        elif 'Co-authored-by' in segment:
            continue
        else:
            text_segments.append(segment)
    pr_body = tools.TRANS_DELIMETER_PR.join(text_segments)
    print(f"Body:\n{pr_body}\n")

print(f"===============Refine PR Title===============")
pr_title_refined = pr_title
if not args.title:
    print(f"Keep title: {pr_title_refined}\n")
else:
    pr_title_refined = tools.gpt_refine_pr(pr_title)
    if pr_title_suffix is not None:
        pr_title_refined = f'{pr_title_refined.strip(".")}. v{pr_title_suffix}'
    print(f"Refined: {pr_title_refined}\n")

print(f"===============Refine PR Body===============")
pr_body_refined = pr_body
if not args.body:
    print(f"Keep body: {pr_body_refined}\n")
else:
    pr_body_refined = tools.gpt_refine_pr(pr_body)
    for extra_metadata in extra_metadatas:
        pr_body_refined = f'{pr_body_refined}\n\n{tools.TRANS_DELIMETER_PR}\n\n{extra_metadata}'
    if len(pr_coauthors) > 0:
        coauthors = "\n".join(pr_coauthors)
        pr_body_refined = f'{pr_body_refined}\n\n{tools.TRANS_DELIMETER_PR}\n\n{coauthors}'
    print(f"Refined: {pr_body_refined}\n")

print(f"===============Update PR===============")
tools.update_pullrequest(pr_id, pr_title_refined, pr_body_refined)
print(f"PR update done.\n")

print(f"===============Add label===============")
label_id = tools.query_label_id(pr["owner"], pr["name"], tools.LABEL_REFINED_NAME)
print(f"Query LABEL_REFINED_NAME={tools.LABEL_REFINED_NAME}, got LABEL_ID={label_id}")

tools.add_label(pr_id, label_id)
print(f"Add label ok, {label_id}({tools.LABEL_REFINED_NAME})\n")

print("\nOK\n")
