import certifi
from flask import Flask, render_template, request, session, redirect, url_for
from pymongo import MongoClient

app = Flask(__name__)
app.secret_key = "super_secret_key"

# MongoDB Setup
uri = "mongodb+srv://akination67:Xkcd2025@akinator1.d2qvaia.mongodb.net/?appName=Akinator1"
client = MongoClient(uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=3000)
db = client["testDatabase"]
collection = db["testCollection"]

@app.route('/')
def index():
    # Reset game state
    session['current_node_id'] = 1
    session['last_id'] = None
    session['recent_choice'] = None
    
    start_node = collection.find_one({"id": 1})
    if not start_node:
        return "Error: Database not initialized. Please run your seed script."

    # Show the first question immediately
    return render_template('index.html', 
                           question=True, 
                           text=start_node['text'], 
                           message="Think of an object!")

@app.route('/ask', methods=['POST'])
def ask():
    ans = request.form.get('answer') # 'yes' or 'no'
    current_node = collection.find_one({"id": session['current_node_id']})
    
    if not current_node:
        return redirect(url_for('index'))

    # Store current state before moving to the next node
    session['last_id'] = current_node['id']
    session['recent_choice'] = ans
    
    next_node_id = current_node.get(ans)
    
    # If the path is empty, we need to learn
    if next_node_id is None:
        return render_template('index.html', learn=True, message="I'm stumped! Help me out.")
    
    next_node = collection.find_one({"id": next_node_id})
    session['current_node_id'] = next_node['id']
    
    if next_node['type'] == 'answer':
        return render_template('index.html', guess=True, text=next_node['text'])
    else:
        return render_template('index.html', question=True, text=next_node['text'])

@app.route('/learn', methods=['POST'])
def learn():
    obj_name = request.form.get('obj_name')
    new_q = request.form.get('new_question')
    is_yes = request.form.get('is_yes')

    # Safety Check: If we don't have a path, restart rather than crash
    if session.get('last_id') is None or session.get('recent_choice') is None:
        return redirect(url_for('index'))

    counter = collection.find_one({"id": "nodeCounter"})
    s = counter['count']

    # 1. Create new object node
    new_obj_id = s + 1
    collection.insert_one({"id": new_obj_id, "type": "answer", "text": obj_name})

    # 2. Create new question node
    new_q_id = s + 2
    old_node_id = session['current_node_id']
    
    # Logic to split the branch
    yes_target = new_obj_id if is_yes == 'yes' else old_node_id
    no_target = old_node_id if is_yes == 'yes' else new_obj_id
    
    collection.insert_one({
        "id": new_q_id,
        "type": "question",
        "text": new_q,
        "yes": yes_target,
        "no": no_target
    })

    # 3. Update parent with the NEW question ID
    collection.update_one(
        {"id": session['last_id']}, 
        {"$set": {session['recent_choice']: new_q_id}}
    )
    
    # 4. Increment counter
    collection.update_one({"id": "nodeCounter"}, {"$inc": {"count": 2}})

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)