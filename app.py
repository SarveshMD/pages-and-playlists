from flask import Flask, render_template, request, redirect, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import login_required

import sqlite3

conn = sqlite3.connect("books-legacy.db", check_same_thread=False)
cursor_ins = conn.cursor()
cursor_del = conn.cursor()
cursor_sel = conn.cursor()

app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


@app.route("/")
def index():
    try:
        books = cursor_sel.execute("SELECT id, title, url, author_id FROM books WHERE id NOT IN (SELECT book_id FROM reading_lists WHERE user_id = ?)", (session["user_id"], )).fetchall()
    except KeyError:
        books = cursor_sel.execute("SELECT id, title, url, author_id FROM books").fetchall()

    catalogue_books = []
    for book in books:
        author = cursor_sel.execute("SELECT name FROM authors WHERE id = (?)", (book[3],)).fetchone()[0]
        catalogue_books.append({"id": book[0], "title": book[1], "url": book[2], "author": author})

    return render_template("catalogue.html", books=catalogue_books)

@app.route("/reading-list")
@login_required
def reading_list():
    books = cursor_sel.execute("SELECT id, title, url, author_id FROM books WHERE id IN (SELECT book_id FROM reading_lists WHERE user_id = ?)", (session["user_id"], )).fetchall()
    reading_books = []
    for book in books:
        author = cursor_sel.execute("SELECT name FROM authors WHERE id = (?)", (book[3],)).fetchone()[0]
        reading_books.append({"id": book[0], "title": book[1], "url": book[2], "author": author})

    return render_template("reading.html", reading=reading_books)

@app.route("/book")
def book_page():
    book_id = int(request.args.get("id"))
    book_tuple = cursor_sel.execute("SELECT * FROM books WHERE id = (?)", (book_id,)).fetchone()
    if not book_tuple:
        return redirect("/")
    author = cursor_sel.execute("SELECT name FROM authors WHERE id = (?)", (book_tuple[3],)).fetchone()[0]
    try:
        in_reading_list = cursor_sel.execute("SELECT * FROM reading_lists WHERE user_id = ? AND book_id = ?", (session["user_id"], book_id )).fetchone()
    except KeyError:
        in_reading_list = False
    book_dict = {'id': book_tuple[0], 'title': book_tuple[1], 'url': book_tuple[2], 'author': author, 'year': book_tuple[4], 'description': book_tuple[5], 'in_reading_list': in_reading_list}

    reviews = cursor_sel.execute("SELECT * FROM reviews WHERE book_id = (?)", (book_id,)).fetchall()
    reviews_list = []
    for review in reviews:
        reviewer = cursor_sel.execute("SELECT username FROM users WHERE id = (?)", (review[0],)).fetchone()[0]
        reviews_list.append({"reviewer": reviewer, "content": review[2]})
    return render_template("book.html", book=book_dict, reviews=reviews_list)

@app.route("/add-to-reading-list", methods=["POST"])
@login_required
def add_to_reading_list():
    cursor_ins.execute("INSERT INTO reading_lists (user_id, book_id) VALUES (?, ?)", (session["user_id"], request.form.get("book_id")))
    conn.commit()
    return redirect(request.referrer)

@app.route("/remove-from-reading-list", methods=["POST"])
@login_required
def remove_from_reading_list():
    cursor_del.execute("DELETE FROM reading_lists WHERE user_id = ? AND book_id = ?", (session["user_id"], request.form.get("book_id")))
    conn.commit()
    return redirect(request.referrer)

@app.route("/post-review", methods=["POST"])
@login_required
def post_review():
    cursor_ins.execute("INSERT INTO reviews (user_id, book_id, content) VALUES (?, ?, ?)", (session["user_id"], request.form.get("book_id"), request.form.get("content")))
    conn.commit()
    return redirect(request.referrer)

@app.route("/add_book", methods=["GET", "POST"])
@login_required
def add_book():
    if request.method == "GET":
        return render_template("add_book.html")
    else:
        author_id = cursor_sel.execute("SELECT id FROM authors WHERE name = ?", (request.form.get("author"),)).fetchone()
        if not author_id:
            cursor_ins.execute("INSERT INTO authors (name) VALUES (?)", (request.form.get("author"), ))
            conn.commit()
            author_id = cursor_sel.execute("SELECT id FROM authors WHERE name = ?", (request.form.get("author"),)).fetchone()[0]
        else:
            author_id = author_id[0]
        cursor_ins.execute("INSERT INTO books (title, url, author_id, year, description) VALUES (?, ?, ?, ?, ?)", (request.form.get("title"), request.form.get("url"), author_id, request.form.get("year"), request.form.get("description")))
        conn.commit()
        return redirect("/")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        try:
            tmp = session["message"]
        except KeyError:
            session["message"] = ''
        return render_template("login.html", message=session["message"], prev=request.referrer)
    else:
        session.clear()
        username = request.form.get("username")
        password = request.form.get("password")
        rows = cursor_sel.execute("SELECT * FROM users WHERE username = (?)", (username,)).fetchall()
        if len(rows) == 0:
            session["message"] = "Username Doesn't Exist"
            return redirect("/login")
        elif not check_password_hash(rows[0][2], password):
            session["message"] = "Incorrect Password"
            return redirect("/login")
        session["user_id"] = rows[0][0]
        session["message"] = ''
        redirect_page = request.form.get("prev")
        if "register" in redirect_page or "None" in redirect_page or "login" in redirect_page:
            return redirect("/")
        else:
            return redirect(redirect_page)

@app.route("/register", methods=["GET", "POST"])
def register():
    try:
        tmp = session["message"]
    except:
        session["message"] = ''

    if request.method == "GET":
        return render_template("register.html", message=session["message"])
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        try:
            cursor_ins.execute("INSERT INTO users (username, hash) VALUES (?, ?)", (username, generate_password_hash(password)))
            conn.commit()
        except sqlite3.IntegrityError:
            session["message"] = "Account already exists with the given username"
            return redirect("/register")

        return redirect("/login")

@app.route("/register_del")
def register_del():
    session["message"] = ''
    return redirect("/register")

@app.route("/login_del")
def login_del():
    session["message"] = ''
    return redirect("/login")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    if "reading-list" in request.referrer:
        return redirect("/")
    else:
        return redirect(request.referrer)

if __name__ == '__main__':
    app.run()