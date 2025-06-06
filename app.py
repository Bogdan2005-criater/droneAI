from flask import Flask, render_template, request, jsonify
from drone_brain import DroneBrain

app = Flask(__name__)
drone_brain = DroneBrain(debug=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_command', methods=['POST'])
def process_command():
    user_input = request.json.get('input')
    response = drone_brain.generate_response(user_input)
    return jsonify({'response': response})

if __name__ == "__main__":
    app.run(debug=True)

