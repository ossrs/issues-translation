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

args = parser.parse_args()
tools.github_token_init(args.token)
tools.openai_init(args.key, args.proxy)

logs = []
logs.append(f"listen: {args.listen}")
logs.append(f"token: {len(os.environ.get('GITHUB_TOKEN'))}B")
logs.append(f"proxy: {len(openai.api_base)}B")
logs.append(f"key: {len(openai.api_key)}B")
logs.append(f"forward: {args.forward}")
print(f"run with {', '.join(logs)}")

def handle_request(j_req, event, delivery, headers):
    print(f"Thread: {delivery}: Got a {event} event, {j_req}")

    do_forward = False
    if event == 'ping':
        print(f"Thread: {delivery}: Got a test ping")
    elif event == 'issues':
        do_forward = True
        title = j_req['issue']['title']
        number = j_req['issue']['number']
        url = j_req['issue']['html_url']
        print(f"{delivery}: Got an issue #{number} {url} {title}")
        command = ["bash", "srs/issue.sh", "--input", url]
        subprocess.run(command, stdout=sys.stdout, stderr=sys.stderr, text=True, check=True)
        # Get the translated issue.
        issue = tools.parse_issue_url(url)
        trans = tools.query_issue(issue['owner'], issue['name'], issue['number'])
        j_req['issue']['title'] = trans['title']
        j_req['issue']['body'] = trans['body']

    if do_forward:
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
            self.send_error(404, 'Not Found')
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'HelloWorld')
    def do_POST(self):
        if self.path != '/api/v1/hooks':
            self.send_error(404, 'Not Found')
        # Read the message and convert it to a JSON object.
        content_length = int(self.headers.get('Content-Length'))
        req_body = self.rfile.read(content_length)
        j_req = json.loads(req_body.decode('utf-8'))
        hook = None
        if 'hook' in j_req and 'config' in j_req['hook'] and 'url' in j_req['hook']['config']:
            hook = j_req['hook']['config']['url']
        event = self.headers.get('X-GitHub-Event')
        delivery = self.headers.get('X-GitHub-Delivery')
        print(f"{delivery}: Get POST body {len(req_body)}B, event={event}, hook={hook}, headers={self.headers}")

        if hook is not None:
            j_req['hook']['config']['url'] = args.forward
        headers = {}
        for key in self.headers.keys():
            headers[key] = self.headers.get(key)

        if event == 'ping':
            print(f"{delivery}: Got a test ping")
        elif event == 'issues':
            title = j_req['issue']['title']
            number = j_req['issue']['number']
            url = j_req['issue']['html_url']
            print(f"{delivery}: Got an issue #{number} {url} {title}")

        thread = threading.Thread(target=handle_request, args=(j_req, event, delivery, headers))
        thread.start()

        self.send_response(204)
        self.end_headers()
        print(f"{delivery}: Done")

httpd = Server(("", args.listen), Handler)
print(f"Serving on port {args.listen}")
httpd.serve_forever()

