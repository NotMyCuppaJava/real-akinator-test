import certifi
import os
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
    # Reset game state and show the Start button
    session['current_node_id'] = 1
    session['last_id'] = None
    session['recent_choice'] = None
    return render_template('index.html', start=True, message="Welcome! Think of an object and I will try to guess it.")

@app.route('/ask', methods=['POST'])
def ask():
    ans = request.form.get('answer')
    current_node = collection.find_one({"id": int(session['current_node_id'])})
    
    # FIX: If 'ans' is None, it means we just clicked "Begin".
    # We should just show the first question and STOP here.
    if ans is None:
        return render_template('index.html', 
                               mode='play',
                               is_question=(current_node['type'] == 'question'),
                               text=current_node['text'],
                               message="Let's begin!")

    # If we get here, it means the user actually clicked Yes or No.
    session['prev_node_text'] = current_node['text']
    
    if current_node['type'] == 'question':
        session['last_id'] = current_node['id']
        session['recent_choice'] = ans
        next_node_id = current_node.get(ans)
        
        if next_node_id is None:
            return render_template('index.html', 
                                   mode='simple', 
                                   prev_text=session['prev_node_text'],
                                   choice=ans,
                                   message="I'm stumped!")
    
    # ... (Rest of the logic for moving to the next node)
        
        # --- STATE: SIMPLE LEARN (Empty path) ---
        if next_node_id is None:
            print(f"Stumped at node {current_node['id']} on choice {ans}")
            return render_template('index.html', 
                                   mode='simple', 
                                   prev_text=session['prev_node_text'],
                                   choice=ans,
                                   message="I'm stumped! I don't know what happens here.")
        
        # Move to next node
        next_node = collection.find_one({"id": int(next_node_id)})
        session['current_node_id'] = next_node['id']
        
    else:
        # --- WE ARE AT AN ANSWER (A GUESS) ---
        if ans == 'no':
            print(f"Wrong guess: {current_node['text']}")
            return render_template('index.html', 
                                   mode='complex', 
                                   bot_guess=session['prev_node_text'],
                                   message="I was wrong - teach me please")
        else:
            return render_template('index.html', mode='start', message="I win! Want to play again?")

    # Standard Question/Guess display
    return render_template('index.html', 
                           mode='play',
                           is_question=(next_node['type'] == 'question'),
                           text=next_node['text'],
                           message="Keep thinking...")

from pymongo import ReturnDocument # Add this at the top of app.py

@app.route('/learn', methods=['POST'])
def learn():
    try:
        mode = request.form.get('mode')
        obj_name = request.form.get('obj_name')
        
        # 1. ATOMIC COUNTER FIX
        # upsert=True means if the counter doesn't exist, MongoDB creates it.
        # ReturnDocument.AFTER ensures we get the updated number back.
        counter_doc = collection.find_one_and_update(
            {"id": "nodeCounter"},
            {"$inc": {"count": 2}},
            upsert=True,
            return_document=ReturnDocument.AFTER
        )
        
        # If the document was just created, it might not have 'count' yet
        s = counter_doc.get('count', 2)

        # 2. SESSION SAFETY
        # We use .get() to avoid crashing if the session is empty
        last_id = session.get('last_id')
        recent_choice = session.get('recent_choice')
        current_node_id = session.get('current_node_id')

        if last_id is None or recent_choice is None:
            print("Session error: Missing parent info")
            return redirect(url_for('index'))

        # 3. EXECUTE UPDATES
        if mode == 'simple':
            new_obj_id = s
            collection.insert_one({"id": new_obj_id, "type": "answer", "text": obj_name})
            collection.update_one({"id": int(last_id)}, {"$set": {recent_choice: new_obj_id}})
        
        else:
            new_q = request.form.get('new_question')
            is_yes = request.form.get('is_yes')
            new_obj_id, new_q_id = s - 1, s
            
            # Insert the new leaf
            collection.insert_one({"id": new_obj_id, "type": "answer", "text": obj_name})
            
            # Insert the new branching question
            yes_target = new_obj_id if is_yes == 'yes' else int(current_node_id)
            no_target = int(current_node_id) if is_yes == 'yes' else new_obj_id
            
            collection.insert_one({
                "id": new_q_id, 
                "type": "question", 
                "text": new_q, 
                "yes": yes_target, 
                "no": no_target
            })
            
            # Update the original parent to point to this new question
            collection.update_one({"id": int(last_id)}, {"$set": {recent_choice: new_q_id}})

        return redirect(url_for('index'))

    except Exception as e:
        # This will print the EXACT error in your Render logs
        print(f"CRITICAL ERROR DURING LEARN: {e}")
        return f"An error occurred: {e}", 500

if __name__ == '__main__':
    app.run(debug=True)
