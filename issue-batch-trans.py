import os, openai, argparse, subprocess, sys, tools

import dotenv
dotenv.load_dotenv(dotenv.find_dotenv())

parser = argparse.ArgumentParser(description="Translation")
parser.add_argument("--input", type=str, required=True, help="GitHub repository URL, for example, https://github.com/your-org/your-repository")
parser.add_argument("--token", type=str, required=False, help="GitHub access token, for example, github_pat_xxx_yyyyyy")
parser.add_argument("--proxy", type=str, required=False, help="OpenAI API proxy, for example, x.y.z")
parser.add_argument("--key", type=str, required=False, help="OpenAI API key, for example, xxxyyyzzz")
parser.add_argument("--count", type=int, default=10, required=False, help="The count of issues, for example, 10")

args = parser.parse_args()
tools.github_token_init(args.token)
tools.openai_init(args.key, args.proxy)

logs = []
logs.append(f"repository: {args.input}")
logs.append(f"token: {len(os.environ.get('GITHUB_TOKEN'))}B")
logs.append(f"proxy: {len(openai.api_base)}B")
logs.append(f"key: {len(openai.api_key)}B")
logs.append(f"count: {args.count}")
print(f"run with {', '.join(logs)}")

if args.count <= 0 or args.count > 100:
    raise Exception("count should be in [1, 100]")

repository = tools.parse_repository_url(args.input)
j_issues = tools.search_issues(
    repository["owner"],
    repository["name"],
    "sort:comments-desc",
    [f"-label:{tools.LABEL_TRANS_NAME}", f"-label:{tools.LABEL_ENGLISH_NATIVE}"],
    args.count,
)

comments = 0
for j_issue in j_issues:
    comments += j_issue["comments"]["totalCount"]
print(f"Start to translate {len(j_issues)} issues, {comments} comments.")

for index, j_issue in enumerate(j_issues):
    print("\n\n\n\n\n\n")
    print(f"===============Issue(#{index+1})===============")
    print(f"ID: {j_issue['id']}")
    print(f"Title: {j_issue['title']}")
    print(f"URL: {j_issue['url']}")

    command = ["bash", "srs/issue.sh", "--input", j_issue["url"]]
    subprocess.run(command, stdout=sys.stdout, stderr=sys.stderr, text=True, check=True)
