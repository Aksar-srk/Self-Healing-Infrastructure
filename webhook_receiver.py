from flask import Flask, request
import subprocess
import json

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        try:
            data = json.loads(request.data)
            print("Alert received!")
            print(json.dumps(data, indent=2))

            # Match your alert name and status
            if data['status'] == 'firing' and data['alerts'][0]['labels']['alertname'] == 'NginxDown':
                print("NginxDown alert firing. Triggering Ansible playbook...")

                # Full absolute paths
                playbook_path = '/home/ansible/ansible/restart_nginx.yml'
                inventory_path = '/home/ansible/ansible/inventory'
                private_key_path = '/home/ansible/.ssh/ansible_key'
                ansible_path = '/home/ansible/.local/bin/ansible-playbook'

                # Execute the playbook
                process = subprocess.Popen(
                    [ansible_path, '-i', inventory_path, '--private-key', private_key_path, playbook_path],
                    cwd='/home/ansible',
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = process.communicate()

                print("Playbook execution finished.")
                print("STDOUT:", stdout)
                print("STDERR:", stderr)
            else:
                print("Alert received, but not NginxDown or not firing.")

        except Exception as e:
            print("Error processing webhook:", str(e))

        return 'Webhook received!', 200

    return 'Method not allowed', 405


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
