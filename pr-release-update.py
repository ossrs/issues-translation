import os, openai, argparse, subprocess, sys
import tools

import dotenv
dotenv.load_dotenv(dotenv.find_dotenv())

parser = argparse.ArgumentParser(description="Translation")
parser.add_argument("--input", type=str, required=True, help="GitHub issue URL, for example, https://github.com/your-org/your-repository/pull/3699")
parser.add_argument("--token", type=str, required=False, help="GitHub access token, for example, github_pat_xxx_yyyyyy")
parser.add_argument("--proxy", type=str, required=False, help="OpenAI API proxy, for example, x.y.z")
parser.add_argument("--key", type=str, required=False, help="OpenAI API key, for example, xxxyyyzzz")
parser.add_argument("--v5", type=bool, required=False, help="Whether merge to v5 branch")
parser.add_argument("--v6", type=bool, required=False, help="Whether merge to v6 branch")

args = parser.parse_args()
tools.github_token_init(args.token)
tools.openai_init(args.key, args.proxy)

if not args.v5 and not args.v6:
    print(f"Error: --v5 or --v6 must be specified")
    sys.exit(1)

logs = []
logs.append(f"issue: {args.input}")
logs.append(f"token: {len(os.environ.get('GITHUB_TOKEN'))}B")
logs.append(f"proxy: {len(openai.api_base)}B")
logs.append(f"key: {len(openai.api_key)}B")
logs.append(f"v5: {args.v5}")
logs.append(f"v6: {args.v6}")
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
print("")

has_gpt_label = False

print(f"===============Pull Request===============")
print(f"ID: {pr_id}")
print(f"Title: {pr_title}")
print(f"URL: {args.input}")
print(f"Author: {pr_author}")
print(f"Base Ref: {pr_base_ref_repo} {pr_base_ref_name}")
print(f"Head Ref: {pr_head_ref_repo} {pr_head_ref_name}")
print(f"Body:\n{pr_body}\n")

if '. v' in pr_title:
    pr_title = pr_title.split('. v')[0]

print(f"===============Refine PR Title===============")
pr_title_refined = tools.gpt_refine_pr(pr_title)
print(f"Refined: {pr_title_refined}\n")

print(f"===============Switch to PR branch===============")
command = ["bash", "auto/switch_pr_repo.sh", "--remote", pr_head_ref_repo, "--branch", pr_head_ref_name]
subprocess.run(command, stdout=sys.stdout, stderr=sys.stderr, text=True, check=True)
print(f"Switch to PR branch done.\n")

print(f"===============Update Release===============")
command = ["bash", "auto/update_version.sh", "--pr", str(pr["number"]), "--title", pr_title_refined]
if args.v5:
    command.append("--v5")
if args.v6:
    command.append("--v6")
result = subprocess.run(command, stdout=sys.stdout, stderr=subprocess.PIPE, text=True, check=True)
release_message = result.stderr
print(f"Update release done. {release_message}\n")

if 'Update release to ' not in release_message:
    print(f"Error: {release_message}")
    sys.exit(1)
version_message = release_message.split('Update release to ')[1].strip()
pr_title_refined = f"{pr_title_refined.strip('.')}. {version_message}"

print(f"===============Update PR===============")
tools.update_pullrequest(pr_id, pr_title_refined, pr_body)
print(f"PR update done.\n")

print(f"===============Push PR===============")
command = ["bash", "auto/push_pr.sh", "--remote", pr_head_ref_repo, "--branch", pr_head_ref_name]
subprocess.run(command, stdout=sys.stdout, stderr=sys.stderr, text=True, check=True)
print(f"Push PR done.\n")

print(f"===============Add label===============")
label_id = tools.query_label_id(pr["owner"], pr["name"], tools.LABEL_REFINED_NAME)
print(f"Query LABEL_REFINED_NAME={tools.LABEL_REFINED_NAME}, got LABEL_ID={label_id}")

tools.add_label(pr_id, label_id)
print(f"Add label ok, {label_id}({tools.LABEL_REFINED_NAME})\n")

print("\nOK\n")
