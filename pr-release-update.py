import os, openai, argparse, subprocess, sys, tools

import dotenv
dotenv.load_dotenv(dotenv.find_dotenv())

parser = argparse.ArgumentParser(description="Translation")
parser.add_argument("--input", type=str, required=True, help="GitHub issue URL, for example, https://github.com/your-org/your-repository/pull/3699")
parser.add_argument("--token", type=str, required=False, help="GitHub access token, for example, github_pat_xxx_yyyyyy")
parser.add_argument("--proxy", type=str, required=False, help="OpenAI API proxy, for example, x.y.z")
parser.add_argument("--key", type=str, required=False, help="OpenAI API key, for example, xxxyyyzzz")
parser.add_argument("--v5", type=bool, required=False, help="Whether merge to v5 branch, True or False(default)")
parser.add_argument("--v6", type=bool, required=False, help="Whether merge to v6 branch, True or False(default)")
parser.add_argument("--v7", type=bool, required=False, help="Whether merge to v7 branch, True or False(default)")

args = parser.parse_args()
tools.github_token_init(args.token)
tools.openai_init(args.key, args.proxy)

if not args.v5 and not args.v6 and not args.v7:
    print(f"Error: --v5 or --v6 or --v7 must be specified")
    sys.exit(1)

logs = []
logs.append(f"issue: {args.input}")
logs.append(f"token: {len(os.environ.get('GITHUB_TOKEN'))}B")
logs.append(f"proxy: {len(openai.api_base)}B")
logs.append(f"key: {len(openai.api_key)}B")
logs.append(f"v5: {args.v5}")
logs.append(f"v6: {args.v6}")
logs.append(f"v7: {args.v7}")
print(f"run with {', '.join(logs)}")

pr = tools.parse_pullrequest_url(args.input)
j_pr = tools.query_pullrequest(pr["owner"], pr["name"], pr["number"])
pr_id = j_pr["id"]
pr_title = j_pr["title"]
pr_body = j_pr["body"]
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

print(f"===============Pull Request===============")
print(f"ID: {pr_id}")
print(f"Title: {pr_title}")
print(f"URL: {args.input}")
print(f"Author: {pr_author}")
print(f"Base Ref: {pr_base_ref_repo} {pr_base_ref_name}")
print(f"Head Ref: {pr_head_ref_repo} {pr_head_ref_name}")
print(f"CoAuthors: {pr_coauthors}")
print(f"Body:\n{pr_body}\n")

pr_title_refined = pr_title
if '. v' in pr_title:
    pr_title_refined = pr_title.split('. v')[0]

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

print(f"===============Switch to PR branch===============")
command = ["bash", "scripts/switch_pr_repo.sh", "--remote", pr_head_ref_repo, "--branch", pr_head_ref_name]
if args.v5:
    command.append("--v5")
if args.v6:
    command.append("--v6")
if args.v7:
    command.append("--v7")
subprocess.run(command, stdout=sys.stdout, stderr=sys.stderr, text=True, check=True)
print(f"Switch to PR branch done.\n")

print(f"===============Update Release===============")
command = ["bash", "scripts/update_version.sh", "--pr", str(pr["number"]), "--title", pr_title_refined.strip('.')]
if args.v5:
    command.append("--v5")
if args.v6:
    command.append("--v6")
if args.v7:
    command.append("--v7")
result = subprocess.run(command, stdout=sys.stdout, stderr=subprocess.PIPE, text=True, check=True)
release_message = result.stderr
print(f"Update release done. {release_message}\n")

if 'Update release to ' not in release_message:
    print(f"Error: {release_message}")
    sys.exit(1)
version_message = release_message.split('Update release to ')[1].strip()
pr_title_refined = f"{pr_title_refined.strip('.')}. {version_message}"

print(f"===============Update PR===============")
pr_body_refined = pr_body
for extra_metadata in extra_metadatas:
    pr_body_refined = f'{pr_body_refined}\n\n{tools.TRANS_DELIMETER_PR}\n\n{extra_metadata}'
if len(pr_coauthors) > 0:
    coauthors = "\n".join(pr_coauthors)
    pr_body_refined = f'{pr_body_refined}\n\n{tools.TRANS_DELIMETER_PR}\n\n{coauthors}'
if pr_title_refined == pr_title and pr_body_refined == pr_body:
    print("No need to update PR title and body.\n")
else:
    tools.update_pullrequest(pr_id, pr_title_refined, pr_body_refined)
    print(f"PR update done.\n")

print(f"===============Push PR===============")
command = ["bash", "scripts/push_pr.sh", "--remote", pr_head_ref_repo, "--branch", pr_head_ref_name]
subprocess.run(command, stdout=sys.stdout, stderr=sys.stderr, text=True, check=True)
print(f"Push PR done.\n")

print(f"===============Add label===============")
label_id = tools.query_label_id(pr["owner"], pr["name"], tools.LABEL_REFINED_NAME)
print(f"Query LABEL_REFINED_NAME={tools.LABEL_REFINED_NAME}, got LABEL_ID={label_id}")

tools.add_label(pr_id, label_id)
print(f"Add label ok, {label_id}({tools.LABEL_REFINED_NAME})\n")

print("\nOK\n")
