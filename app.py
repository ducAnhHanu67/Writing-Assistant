from flask import Flask, request, render_template,url_for,session,redirect,abort
import openai
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


response = client.chat.completions.create(
    model="meta-llama/Llama-3-8b-chat-hf",
    messages=[{"role": "user", "content": "who is presedent in US"}],
)
print(response.choices[0].message.content)


openai.organization = "org-qx0rscpLNsWzVxBULOKAyuRW"
app = Flask(__name__, template_folder='templates', static_folder='static')

openai.api_key = "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"


app.secret_key = "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" # make sure this matches with that's in client_secret.json

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1" # to allow Http traffic for local dev

GOOGLE_CLIENT_ID = "852230166723-c4g60h42eqc29mf8ebp3u7331fdpvdrl.apps.googleusercontent.com"
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
def ducanhtest():
    if request.method == 'POST':
        text = request.form['text']
        action = request.form['action']  

        if action == 'grammar_check':

                # response = openai.Completion.create(
                # engine="text-davinci-003",
                # prompt=(f"Please correct any grammatical errors in the following text:\n{text}\n"),
                # max_tokens=1024,
                # n=1,
                # stop=None,
                # temperature=0.7,
                # )
                response = client.chat.completions.create(
                model="meta-llama/Llama-3-8b-chat-hf",
                messages=[{"role": "user", "content": f"Please correct any grammatical errors in the following text:\n{text}\n" }],
                )
                
                res_text = response.choices[0].message.content
                addHistory('Grammar Check',text,res_text)
                return render_template('home.html',ori_text=text, res_text=res_text)
        
        elif action == 'paraphrase':
                # response = openai.Completion.create(
                # engine="text-davinci-003",
                # prompt=f"Paraphrase the following sentence: {text}",
                # max_tokens=500,
                # n=10,
                # stop=None,
                # temperature=0.5
                # )
                # res_text= response.choices[0].text.strip()
                response = client.chat.completions.create(
                    model="meta-llama/Llama-3-8b-chat-hf",
                    messages=[{"role": "user", "content": f"Paraphrase the following sentence: {text}"}],
                )
                
                res_text = response.choices[0].message.content

                addHistory('Paraphrasing',text,res_text)
                return render_template('home.html',ori_text=text, res_text=res_text)
        
        elif action == 'textCompletion':
            prompt = f"The following is a conversation with an AI assistant. The assistant is helpful, creative, clever, and very friendly.\n\nHuman:\n{text}\n\nResult:"
            response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=1024,
            n=1,
            stop=None,
            temperature=0.5,
            )
            res_text= response.choices[0].text.strip()
            addHistory('Text Completion',text,res_text)
            return render_template('home.html',ori_text=text, res_text=res_text)
        elif action=='Plagiarism':
            result = check_plagiarism(text)
            res_text = ""
            for doc in result:
                url = doc['url']
                similarity = doc['similarity']
                res_text += f"{url}\n {similarity} %\n"

            addHistory('Plagiarism',text,res_text)
            return render_template('home.html',ori_text=text, res_text=res_text)



    return render_template('home.html')


@app.route('/')
def login():
    return render_template('login.html')


# @app.route('/login')
# def login():
#     return render_template('login.html')

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
    # cur.execute("select * from users where name='Duc Anh Tran' ")
    cur.execute(query, (nameUser,))
    rows =cur.fetchall()

    return render_template("dashboard.html",rows=rows)


if __name__ == '__main__':
    app.run(debug=True)

