from flask import Flask, jsonify, make_response
from flask_httpauth import HTTPBasicAuth

app = Flask(__name__)

tasks = [{"": ""}]

auth = HTTPBasicAuth()


@auth.get_password
def get_password(username):
    if username == 'smarttraffic':
        return '9TYsDh2f3_'
    return None


@auth.error_handler
def unauthorized():
    return make_response(jsonify({'error': 'Unauthorized access'}), 401)


@app.route('/todo/api/v1.0/tasks', methods=['GET'])
@auth.login_required
def get_tasks():
    return jsonify({'tasks': tasks})


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
