import http.server, socket, json, os, openai, argparse, requests, threading, subprocess, sys
import tools

import dotenv
dotenv.load_dotenv(dotenv.find_dotenv())

parser = argparse.ArgumentParser(description="Translation")
parser.add_argument("--listen", type=int, required=True, help="Listen port, for example, 2023")
parser.add_argument("--forward", type=str, required=True, help="Forward message to, for example, https://discord.com/x/y/z/xxx/github")
parser.add_argument("--token", type=str, required=False, help="GitHub access token, for example, github_pat_xxx_yyyyyy")
parser.add_argument("--proxy", type=str, required=False, help="OpenAI API proxy, for example, x.y.z")
parser.add_argument("--key", type=str, required=False, help="OpenAI API key, for example, xxxyyyzzz")
parser.add_argument("--secret", type=str, required=False, help="The secret in url, for example, xxxxxx")
parser.add_argument("--open-collective", type=str, required=False, help="Callback for the OpenCollective event.")

args = parser.parse_args()
tools.github_token_init(args.token)
tools.openai_init(args.key, args.proxy)

IGNORE_LOGIN='dependabot'

logs = []
logs.append(f"listen: {args.listen}")
logs.append(f"token: {len(os.environ.get('GITHUB_TOKEN'))}B")
logs.append(f"proxy: {len(openai.api_base)}B")
logs.append(f"key: {len(openai.api_key)}B")
logs.append(f"forward: {args.forward}")
if args.secret is not None:
    logs.append(f"secret: {len(args.secret)}B")
if args.open_collective is not None:
    logs.append(f"open_collective: {args.open_collective}")
print(f"run with {', '.join(logs)}")

def handle_oc_request(j_req, event, delivery, headers):
    do_forward = True

    if do_forward and args.open_collective is not None:
        # Without any Host set.
        if 'Host' in headers:
            del headers['Host']
        # Reset the Content-Type to application/json.
        if 'Content-Type' in headers:
            del headers['Content-Type']
        if 'content-type' in headers:
            del headers['content-type']
        headers['Content-Type'] = 'application/json'
        res = requests.post(args.open_collective, json=j_req, headers=headers)
        print(f"Thread: {delivery}: Response {res.status_code} {res.reason} {len(res.text)}B {res.headers}")

    print(f"Thread: {delivery}: Done")

def handle_github_request(j_req, event, delivery, headers):
    action = j_req['action'] if 'action' in j_req else None
    print(f"Thread: {delivery}: Got a event {event} {action}, {headers}")

    if 'sender' in j_req and 'login' in j_req['sender']:
        sender = j_req['sender']['login']
        if IGNORE_LOGIN in sender:
            print(f"Thread: {delivery}: Ignore sender {sender}")
            return

    do_forward = False
    if event == 'ping':
        print(f"Thread: {delivery}: Got a test ping")
    elif event == 'issues':
        if action != 'opened':
            print(f"Thread: {delivery}: Ignore action {action}")
        else:
            do_forward = True
            title = j_req['issue']['title']
            number = j_req['issue']['number']
            html_url = j_req['issue']['html_url']
            print(f"Thread: {delivery}: Got an issue #{number} {html_url} {title}")
            command = ["bash", "srs/issue.sh", "--input", html_url]
            subprocess.run(command, stdout=sys.stdout, stderr=sys.stderr, text=True, check=True)
            parsed = tools.parse_issue_url(html_url)
            trans = tools.query_issue(parsed['owner'], parsed['name'], parsed['number'])
            j_req['issue']['title'] = trans['title']
            j_req['issue']['body'] = trans['body']
    elif event == 'issue_comment':
        if action != 'created':
            print(f"Thread: {delivery}: Ignore action {action}")
        else:
            do_forward = True
            html_url = j_req['comment']['html_url']
            issue_url = j_req['issue']['html_url']
            node_id = j_req['comment']['node_id']
            body = j_req['comment']['body']
            print(f"Thread: {delivery}: Got a comment {html_url} of {issue_url} {node_id} {body}")
            (body_trans, body_trans_by_gpt, real_translated) = tools.gpt_translate(body, False)
            if real_translated:
                print(f"Thread: {delivery}: Body:\n{body_trans}\n")
                try:
                    tools.update_issue_comment(node_id, tools.wrap_magic(body_trans))
                    print(f"Thread: {delivery}: Updated ok")
                except tools.GithubGraphQLException as e:
                    if e.is_forbidden():
                        print(f"Thread: {delivery}: Warning!!! Ignore update comment {node_id} failed, forbidden, {e.errors}")
                    else:
                        raise e
            j_req['comment']['body'] = body_trans
    elif event == 'discussion':
        if action != 'created':
            print(f"Thread: {delivery}: Ignore action {action}")
        else:
            do_forward = True
            html_url = j_req['discussion']['html_url']
            number = j_req['discussion']['number']
            title = j_req['discussion']['title']
            print(f"Thread: {delivery}: Got a discussion #{number} {html_url} {title}")
            command = ["bash", "srs/discussion.sh", "--input", html_url]
            subprocess.run(command, stdout=sys.stdout, stderr=sys.stderr, text=True, check=True)
            parsed = tools.parse_discussion_url(html_url)
            trans = tools.query_discussion(parsed['owner'], parsed['name'], parsed['number'])
            j_req['discussion']['title'] = trans['title']
            j_req['discussion']['body'] = trans['body']
    elif event == 'discussion_comment':
        if action != 'created':
            print(f"Thread: {delivery}: Ignore action {action}")
        else:
            do_forward = True
            html_url = j_req['comment']['html_url']
            discussion_url = j_req['discussion']['html_url']
            node_id = j_req['comment']['node_id']
            body = j_req['comment']['body']
            print(f"Thread: {delivery}: Got a comment {html_url} of {discussion_url} {node_id} {body}")
            (body_trans, body_trans_by_gpt, real_translated) = tools.gpt_translate(body, False)
            if real_translated:
                print(f"Thread: {delivery}: Body:\n{body_trans}\n")
                try:
                    tools.update_discussion_comment(node_id, tools.wrap_magic(body_trans))
                    print(f"Thread: {delivery}: Updated ok")
                except tools.GithubGraphQLException as e:
                    if e.is_forbidden():
                        print(f"Thread: {delivery}: Warning!!! Ignore update comment {node_id} failed, forbidden, {e.errors}")
                    else:
                        raise e
            j_req['comment']['body'] = body_trans
    elif event == 'pull_request':
        if action != 'opened':
            print(f"Thread: {delivery}: Ignore action {action}")
        else:
            do_forward = True
            html_url = j_req['pull_request']['html_url']
            number = j_req['pull_request']['number']
            title = j_req['pull_request']['title']
            print(f"Thread: {delivery}: Got a pull request #{number} {html_url} {title}")
            command = ["python", "pr-trans.py", "--input", html_url]
            subprocess.run(command, stdout=sys.stdout, stderr=sys.stderr, text=True, check=True)
            parsed = tools.parse_pullrequest_url(html_url)
            trans = tools.query_pullrequest(parsed['owner'], parsed['name'], parsed['number'])
            j_req['pull_request']['title'] = trans['title']
            j_req['pull_request']['body'] = trans['body']
    elif event == 'pull_request_review':
        if action != 'submitted':
            print(f"Thread: {delivery}: Ignore action {action}")
        else:
            do_forward = True
            html_url = j_req['review']['html_url']
            pull_request_url = j_req['pull_request']['html_url']
            node_id = j_req['review']['node_id']
            body = j_req['review']['body']
            print(f"Thread: {delivery}: Got a PR review {html_url} of {pull_request_url} {node_id} {body}")
            (body_trans, body_trans_by_gpt, real_translated) = tools.gpt_translate(body, False)
            if real_translated:
                print(f"Thread: {delivery}: Body:\n{body_trans}\n")
                try:
                    tools.update_pullrequest_review(node_id, tools.wrap_magic(body_trans))
                    print(f"Thread: {delivery}: Updated ok")
                except tools.GithubGraphQLException as e:
                    if e.is_forbidden():
                        print(f"Thread: {delivery}: Warning!!! Ignore update PR review {node_id} failed, forbidden, {e.errors}")
                    else:
                        raise e
            j_req['review']['body'] = body_trans
    elif event == 'pull_request_review_comment':
        if action != 'created':
            print(f"Thread: {delivery}: Ignore action {action}")
        else:
            do_forward = True
            html_url = j_req['comment']['html_url']
            pull_request_url = j_req['pull_request']['html_url']
            node_id = j_req['comment']['node_id']
            body = j_req['comment']['body']
            print(f"Thread: {delivery}: Got a PR Review comment {html_url} of {pull_request_url} {node_id} {body}")
            (body_trans, body_trans_by_gpt, real_translated) = tools.gpt_translate(body, False)
            if real_translated:
                print(f"Thread: {delivery}: Body:\n{body_trans}\n")
                try:
                    tools.update_pullrequest_review_comment(node_id, tools.wrap_magic(body_trans))
                    print(f"Thread: {delivery}: Updated ok")
                except tools.GithubGraphQLException as e:
                    if e.is_forbidden():
                        print(f"Thread: {delivery}: Warning!!! Ignore update PR Review comment {node_id} failed, forbidden, {e.errors}")
                    else:
                        raise e
            j_req['comment']['body'] = body_trans

    if do_forward and args.forward is not None:
        # Without any Host set.
        if 'Host' in headers:
            del headers['Host']
        # Reset the Content-Type to application/json.
        if 'Content-Type' in headers:
            del headers['Content-Type']
        if 'content-type' in headers:
            del headers['content-type']
        headers['Content-Type'] = 'application/json'
        headers['User-Agent'] = 'GitHub-Hookshot/4689486'
        res = requests.post(args.forward, json=j_req, headers=headers)
        print(f"Thread: {delivery}: Response {res.status_code} {res.reason} {len(res.text)}B {res.headers}")

    print(f"Thread: {delivery}: Done")

class Server(http.server.HTTPServer):
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/api/v1/echo':
            return self.send_error(404, 'Not Found')
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'HelloWorld')
    def do_POST(self):
        if '/api/v1/hooks' not in self.path:
            return self.send_error(404, 'Not Found')
        if args.secret is not None and args.secret not in self.path:
            return self.send_error(403, 'Forbidden')
        # Read the message and convert it to a JSON object.
        content_length = int(self.headers.get('Content-Length'))
        req_body = self.rfile.read(content_length)
        j_req = json.loads(req_body.decode('utf-8'))
        print(f"Got a request {self.path} {len(req_body)}B {self.headers}")

        headers = {}
        for key in self.headers.keys():
            headers[key] = self.headers.get(key)

        # For OpenCollective.
        if 'type' in j_req and 'CollectiveId' in j_req:
            event = j_req['type']
            delivery = j_req['CollectiveId']

            # Deliver to thread.
            print(f"{delivery}: Start a thread to handle {event}")
            thread = threading.Thread(target=handle_oc_request, args=(j_req, event, delivery, headers))
            thread.start()
        # For GitHub.
        else:
            event = self.headers.get('X-GitHub-Event')
            delivery = self.headers.get('X-GitHub-Delivery')
            hook = None
            if 'hook' in j_req and 'config' in j_req['hook'] and 'url' in j_req['hook']['config']:
                hook = j_req['hook']['config']['url']
            if hook is not None:
                j_req['hook']['config']['url'] = args.forward
            print(f"{delivery}: Get POST body {len(req_body)}B, event={event}, hook={hook}, headers={self.headers}")

            # Deliver to thread.
            print(f"{delivery}: Start a thread to handle {event}")
            thread = threading.Thread(target=handle_github_request, args=(j_req, event, delivery, headers))
            thread.start()

        self.send_response(204)
        self.end_headers()
        print(f"{delivery}: Done")

httpd = Server(("", args.listen), Handler)
print(f"Serving on port {args.listen}")
httpd.serve_forever()

