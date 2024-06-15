from flask import Flask, request, render_template,url_for,session,redirect,abort
import os
import pathlib
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
import requests
import sqlite3 as sql
from googlesearch import search
from fuzzywuzzy import fuzz
from together import Together

client = Together(api_key="24dee2c6a57f8afda4a21bf015bc22758aa228095d1ca542de9900727a9c469d")

app = Flask(__name__, template_folder='templates', static_folder='static')


app.secret_key = "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" # make sure this matches with that's in client_secret.json

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1" # to allow Http traffic for local dev

GOOGLE_CLIENT_ID = "852230166723-c4g60h42eqc29mf8ebp3u7331fdpvdrl.apps.googleusercontent.com"
# nlp = spacy.load('en_core_web_sm')
# gf = Gramformer(models=1, use_gpu=False) 
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")
flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri="http://127.0.0.1:5000/callback"
)


def login_is_required(function):
    def wrapper(*args, **kwargs):
        if "google_id" not in session:
            return abort(401)  # Authorization required
        else:
            return function()

    return wrapper
def search_google(query):
    search_results = []
    for url in search(query, num_results=3):
        search_results.append(url)
    return search_results
def check_plagiarism(input_text):
    search_results = search_google(input_text)
    results = []

    for url in search_results:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                content = response.text
                similarity = fuzz.token_set_ratio(input_text, content)
                results.append({'url': url, 'similarity': similarity})
        except requests.exceptions.RequestException as e:
            print("Error:", e)

    return results



@app.route("/login-google")
def loginGoogle():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)


@app.route("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session["state"] == request.args["state"]:
        abort(500)  # State does not match!

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    
    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )

    session["google_id"] = id_info.get("sub")
    session["name"] = id_info.get("name")
    return redirect("/home")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/protected_area")
@login_is_required
def protected_area():
    return f"Hello {session['name']}! <br/> <a href='/logout'><button>Logout</button></a>"
    

@app.route('/home', methods=['GET', 'POST'])
def homeTest():
    if request.method == 'POST':
        text = request.form['text']
        action = request.form['action']  
        if action == 'paraphrase':
                response = client.chat.completions.create(
                    model="meta-llama/Llama-3-8b-chat-hf",
                    messages=[{"role": "user", "content": f"Paraphrase the following sentence: {text}"}],
                )               
                res_text = response.choices[0].message.content
                addHistory('Paraphrasing',text,res_text)
                return render_template('home.html',ori_text=text, res_text=res_text)       
    return render_template('home.html')
@app.route('/grammar', methods=['GET', 'POST'])
def grammar():
    if request.method == 'POST':
        text = request.form['text']
        action = request.form['action']  

        if action == 'grammar_check':
                response = client.chat.completions.create(
                model="meta-llama/Llama-3-8b-chat-hf",
                messages=[{"role": "user", "content": f"Please correct any grammatical errors in the following text:\n{text}\n" }],
                )                
                res_text = response.choices[0].message.content
                # res_text = list(gf.correct(text))
                # corrected_text = res_text[0] if res_text else "No corrections needed."

                addHistory('Grammar Check',text,res_text)
                return render_template('grammar.html',ori_text=text, res_text=res_text)
    return render_template('grammar.html')

@app.route('/textcompletion', methods=['GET', 'POST'])
def completion():
    if request.method == 'POST':
        text = request.form['text']
        action = request.form['action'] 


        if action == 'textcompletion':

                response = client.chat.completions.create(
                model="meta-llama/Llama-3-8b-chat-hf",
                messages=[{"role": "user", "content": f"Please continue writing your words:\n{text}\n" }],
                )
                
                res_text = response.choices[0].message.content
                addHistory('Text Completion',text,res_text)
                return render_template('completion.html',ori_text=text, res_text=res_text)
        

    return render_template('completion.html')

@app.route('/plagiarism', methods=['GET', 'POST'])
def plagiarism():
    if request.method == 'POST':
        text = request.form['text']
        action = request.form['action'] 
        if action == 'plagiarism_check':
                result = check_plagiarism(text)
                res_text = ""
                for doc in result:
                    url = doc['url']
                    similarity = doc['similarity']
                    res_text += f"{url}\n {similarity} %\n"
                addHistory('Plagiarism',text,res_text)
                return render_template('plagiarism.html',ori_text=text, res_text=res_text)
        

    return render_template('plagiarism.html')


@app.route('/')
def login():
    return render_template('login.html')

def get_db_connection():
  conn = sql.connect('database.db')
  conn.row_factory = sql.Row
  return conn

def addHistory(funct,orinText,resText):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
      "INSERT INTO users (name,funt ,oriText, resText) VALUES (?, ?, ?, ?)",
      (session['name'], funct, orinText,resText))
    conn.commit()
    conn.close()




@app.route('/dashboard')
def list () :
    con =sql.connect('database.db')
    con.row_factory =sql.Row
    cur=con.cursor()
    nameUser =str(session['name'])
    query = "SELECT * FROM users WHERE name = ?"
    cur.execute(query, (nameUser,))
    rows =cur.fetchall()

    return render_template("dashboard.html",rows=rows)


if __name__ == '__main__':
    app.run(debug=True)

