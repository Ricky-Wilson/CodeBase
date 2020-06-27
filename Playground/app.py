

from flask import Flask
from flask import send_from_directory
from flask import make_response

app = Flask(__name__)


@app.route('/logs/<path:filename>')
def test(filename):
    data = send_from_directory('/var/log/', filename)
    response = make_response(data)
    help(data)
    response.headers['content-type'] = 'text/plain'
    return response


app.run(port=8000, debug=1, load_dotenv=1)
