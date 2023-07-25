import os, argparse
import tools

parser = argparse.ArgumentParser(description="Translation")
parser.add_argument("--input", type=str, required=True, help="GitHub repository URL, for example, https://github.com/ossrs/srs")
parser.add_argument("--token", type=str, required=False, help="GitHub access token, for example, github_pat_xxx_yyyyyy")
parser.add_argument("--title", type=str, required=True, help="Discussion title.")
parser.add_argument("--body", type=str, required=True, help="Discussion body.")

args = parser.parse_args()

if args.token is not None:
    os.environ["GITHUB_TOKEN"] = args.token
if os.environ.get("GITHUB_TOKEN") is None:
    raise Exception("GITHUB_TOKEN is not set")

logs = []
logs.append(f"repository: {args.input}")
logs.append(f"token: {len(os.environ.get('GITHUB_TOKEN'))}B")
logs.append(f"title: {args.title}")
logs.append(f"body: {args.body}")
print(f"run with {', '.join(logs)}")

repository = tools.parse_repository_url(args.input)
repository_id = tools.query_repository_id(repository["owner"], repository["name"])
category_id = tools.query_catetory_id(repository["owner"], repository["name"], "general")
print(f"query repository id: {repository_id}, category id: {category_id}")

(discussion_id, discussion_url) = tools.create_discussion(repository_id, args.title, args.body, category_id)
print(f"Create discussion OK, id={discussion_id}, url={discussion_url}")
