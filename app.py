import os
import requests

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
import datetime
import urllib.request
from werkzeug.utils import secure_filename

from helpers import apology, login_required

# Configure application
app = Flask(__name__)


# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
app.secret_key = "secret key"
app.config['UPLOAD_FOLDER'] = 'static/images/input'
# Configure CS50 Library to use SQLite databasetr
db = SQL("sqlite:///split.db")

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# performs database query to obtain authorized patient info and files and display them.
@app.route("/", methods=["GET"])
@login_required
def index():
    loggedinuser = db.execute("SELECT username FROM users WHERE users.id == ?", session["user_id"])
    debts = db.execute("SELECT creditor, amount, date FROM debts WHERE paidBack == 'No' AND debtor == ?", (loggedinuser[0]).get('username'))
    print(debts)
    return render_template("index.html", debts=debts, user=(loggedinuser[0]).get('username'))

@app.route("/yourCreds", methods=["GET"])
@login_required
def creds():
    loggedinuser = db.execute("SELECT username FROM users WHERE users.id == ?", session["user_id"])
    creds = db.execute("SELECT debtor, amount, date FROM debts WHERE creditor == ? AND paidBack = 'No'", (loggedinuser[0]).get('username'))
    return render_template("yourCreds.html", creds=creds, user=(loggedinuser[0]).get('username'))

@app.route("/split", methods=["GET", "POST"])
@login_required
def split():
    if request.method == "POST":

        if request.form.get("debtorsString") == '':
            flash('friend names are required')
            return redirect(request.url)

        else:
            #saves form inputs to database entry
            debtorsString = request.form.get("debtorsString")
            debtorList = debtorsString.split(",")


            amountPerPerson = round(float(request.form.get("amount")) / (len(debtorList) + 1), 2)

            loggedinuser = db.execute("SELECT username FROM users WHERE users.id == ?", session["user_id"])

            for i in range(len(debtorList)):
                db.execute("INSERT INTO debts (creditor, debtor, amount, date) VALUES (?, ?, ?, ?)", (loggedinuser[0]).get('username'), debtorList[i], amountPerPerson, datetime.datetime.now())

            flash('Split recorded!')
            return render_template('split.html')

    else:
        loggedinuser = db.execute("SELECT username FROM users WHERE users.id == ?", session["user_id"])
        return render_template("/split.html", user=(loggedinuser[0]).get('username'))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():

    # obtain form inputs
    if (request.method == "POST"):
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirmation = request.form.get('confirmation')

        # ensures all fields filled completely and correctly
        if not username:
            return apology('Username is a required field.')
        elif not password:
            return apology('Password is a required field.')
        if password != confirmation:
            return apology('Passwords do not match.')

        # Password security requirements below. Length and number requirement.
        if len(password) < 6:
            return apology('password must be longer than 6 characters')

        if not any(char.isdigit() for char in password):
            return apology('your password must contain at least 1 number')

        hashedpass = generate_password_hash(password)

        if len(db.execute("SELECT username FROM users WHERE username == ?", username)) == 0:
            db.execute("INSERT INTO users (username, hash, email) VALUES (?, ?, ?)", username, hashedpass, email)
            return redirect("/")
        else:
            return apology('This username already exists; please enter another username.')

    else:
        return render_template("register.html")


# deletes database entries
@app.route("/pay", methods=["GET", "POST"])
@login_required
def pay():
    if request.method == "POST":
        loggedinuser = db.execute("SELECT username FROM users WHERE users.id == ?", session["user_id"])
        creditor = request.form.get('payee')
        email = db.execute("SELECT email FROM users WHERE username == ?", creditor)
        print(email)
        amount = float(request.form.get('amount'))
        db.execute("UPDATE debts SET paidBack='yes' WHERE creditor == ? AND debtor == ? AND amount == ?", creditor, (loggedinuser[0]).get('username'), amount)

        url = "https://sandbox.checkbook.io/v3/check/digital"

        payload = {
            "recipient": email[0].get('email'),
            "name": creditor,
            "amount": amount,
            "description": "Split Payment"
        }
        print(payload)
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": "b52c802d3d3db6a613dda0122505a8db:c6420ea5de005d67c89fdc6674ba64d7"
        }
        response = requests.post(url, json=payload, headers=headers)

        print(response.text)

        return redirect("/")
    else:
        loggedinuser = db.execute("SELECT username FROM users WHERE users.id == ?", session["user_id"])
        creditors = db.execute("SELECT DISTINCT creditor FROM debts WHERE debtor == ? AND paidBack == 'No'", (loggedinuser[0]).get('username'))
        amounts = db.execute("SELECT DISTINCT amount FROM debts WHERE debtor == ? AND paidBack == 'No'", (loggedinuser[0]).get('username'))
        return render_template("/pay.html", creditors=creditors, amounts=amounts, user=(loggedinuser[0]).get('username'))

@app.route("/history", methods=["GET"])
@login_required
def history():
    loggedinuser = db.execute("SELECT username FROM users WHERE users.id == ?", session["user_id"])
    debts = db.execute("SELECT * FROM debts WHERE Debtor == ? OR Creditor == ?", (loggedinuser[0]).get('username'), (loggedinuser[0]).get('username'))
    return render_template("/history.html", debts=debts, user=(loggedinuser[0]).get('username'))