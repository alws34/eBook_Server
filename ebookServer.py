from flask import Flask, request, redirect, url_for, send_from_directory, render_template_string, flash, session, send_file, jsonify
import os
import json
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import fitz  # PyMuPDF, used for extracting cover from PDFs
import ebooklib
from ebooklib import epub
from PIL import Image
import io

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Directory where books are stored
BOOKS_DIR = os.environ.get('BOOKS_DIR', '/ebooks') 
# The root directory containing book collections (subdirectories)
ALLOWED_EXTENSIONS = {'.pdf', '.epub'}
USER_DATA_FILE = 'users.json'

# Ensure the user data file exists
if not os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, 'w') as file:
        json.dump({}, file)


def allowed_file(filename):
    return '.' in filename and Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def get_directory_structure(directory: str):
    directories = []
    files = []
    for entry in Path(directory).iterdir():
        if entry.is_dir():
            directories.append(entry.name)
        elif entry.is_file() and allowed_file(entry.name):
            files.append(entry.name)
    return directories, files


def load_users():
    with open(USER_DATA_FILE, 'r') as file:
        return json.load(file)


def save_users(users):
    with open(USER_DATA_FILE, 'w') as file:
        json.dump(users, file, indent=4)


def is_authenticated():
    if 'user' not in session:
        flash('You need to be logged in to access the book collection.')
        return False
    return True


def extract_cover_image(filepath):
    extension = Path(filepath).suffix.lower()
    if extension == '.pdf':
        doc = fitz.open(filepath)
        page = doc.load_page(0)
        pix = page.get_pixmap()
        img_data = pix.tobytes('png')
        return io.BytesIO(img_data)
    elif extension == '.epub':
        book = epub.read_epub(filepath)
        cover = None
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_COVER:
                cover = item.get_content()
                break
        if cover:
            return io.BytesIO(cover)
    return None  # No cover found


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']

        users = load_users()

        if email in users:
            flash('Email is already registered.')
            return redirect(url_for('signup'))

        users[email] = {
            'username': username,
            'password': generate_password_hash(password)
        }
        save_users(users)
        flash('Signup successful. Please log in.')
        return redirect(url_for('login'))

    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Signup</title>
        <style>
            body {
                background-color: #2C2C2C;
                color: #E5E5E5;
                font-family: Arial, sans-serif;
            }
            input[type="text"], input[type="email"], input[type="password"] {
                width: 100%;
                padding: 8px;
                margin: 8px 0;
                box-sizing: border-box;
                background-color: #444;
                color: white;
                border: none;
            }
            button, input[type="submit"] {
                background-color: #444;
                color: #E5E5E5;
                border: none;
                padding: 8px 16px;
                cursor: pointer;
            }
            button:hover, input[type="submit"]:hover {
                background-color: #555;
            }
        </style>
    </head>
    <body>
        <h2>Signup</h2>
        <form method="post">
            <label for="email">Email:</label><br>
            <input type="email" id="email" name="email" required><br>
            <label for="username">Username:</label><br>
            <input type="text" id="username" name="username" required><br>
            <label for="password">Password:</label><br>
            <input type="password" id="password" name="password" required><br><br>
            <input type="submit" value="Signup">
        </form>
        <p>Already have an account? <a href="{{ url_for('login') }}" style="color:#00ffcc;">Login here</a>.</p>
    </body>
    </html>
    ''')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_or_username = request.form['email_or_username']
        password = request.form['password']

        users = load_users()

        user = next((u for e, u in users.items() if e ==
                    email_or_username or u['username'] == email_or_username), None)

        if user and check_password_hash(user['password'], password):
            session['user'] = user['username']
            flash('Login successful!')
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials. Please try again.')
            return redirect(url_for('login'))

    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Login</title>
        <style>
            body {
                background-color: #2C2C2C;
                color: #E5E5E5;
                font-family: Arial, sans-serif;
            }
            input[type="text"], input[type="password"] {
                width: 100%;
                padding: 8px;
                margin: 8px 0;
                box-sizing: border-box;
                background-color: #444;
                color: white;
                border: none;
            }
            button, input[type="submit"] {
                background-color: #444;
                color: #E5E5E5;
                border: none;
                padding: 8px 16px;
                cursor: pointer;
            }
            button:hover, input[type="submit"]:hover {
                background-color: #555;
            }
        </style>
    </head>
    <body>
        <h2>Login</h2>
        <form method="post">
            <label for="email_or_username">Email or Username:</label><br>
            <input type="text" id="email_or_username" name="email_or_username" required><br>
            <label for="password">Password:</label><br>
            <input type="password" id="password" name="password" required><br><br>
            <input type="submit" value="Login">
        </form>
        <p>Don't have an account? <a href="{{ url_for('signup') }}" style="color:#00ffcc;">Sign up here</a>.</p>
    </body>
    </html>
    ''')


@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out.')
    return redirect(url_for('login'))


@app.route('/')
@app.route('/<path:subpath>')
def index(subpath=""):
    if not is_authenticated():
        return redirect(url_for('login'))

    current_dir = os.path.join(BOOKS_DIR, subpath)
    directories, files = get_directory_structure(current_dir)

    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Ebook Collection</title>
        <style>
            body {
                background-color: #2C2C2C;
                color: #E5E5E5;
                font-family: Arial, sans-serif;
            }
            a {
                color: #E5E5E5;
            }
            button, input[type="submit"] {
                background-color: #444;
                color: #E5E5E5;
                border: none;
                padding: 8px 16px;
                cursor: pointer;
            }
            button:hover, input[type="submit"]:hover {
                background-color: #555;
            }
            h1 {
                display: inline-block;
            }
            ul {
                list-style-type: none;
                padding: 0;
            }
            li {
                display: inline-block;
                margin: 10px;
            }
            img {
                max-width: 200px;
                transition: transform 0.2s;
                cursor: pointer;
            }
            img:hover {
                transform: scale(1.1);
            }
            .modal {
                display: none;
                position: fixed;
                z-index: 1000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.9);
            }
            .modal img {
                margin: auto;
                display: block;
                width: 80%;
                max-width: 700px;
            }
        </style>
    </head>
    <body>
        <h1>Ebook Collection</h1>

        <!-- Display the current path -->
        <div style="font-size: 18px; margin-top: 10px;">
            Current Path: 
            <span style="font-weight: bold;">{{ '/' if not subpath else '/' + subpath }}</span>
        </div>

        <!-- Book counter -->
        <div style="font-size: 16px; margin-top: 5px;">
            Books Count: {{ files | length }}
        </div>

        <!-- Upload form -->
        <form method="post" action="/upload/{{ subpath }}" enctype="multipart/form-data" style="margin-bottom: 20px; clear: both;">
            <input type="file" name="file[]" multiple>
            <input type="submit" value="Upload">
        </form>

        <!-- Download all button -->
        <div style="margin-bottom: 20px;">
            <button id="download-all-btn" style="background-color: #444; color: #E5E5E5; padding: 8px 16px; border: none; cursor: pointer;">
                Download All Files
            </button>
        </div>

        <!-- Navigation pane as buttons -->
        <div style="background-color: #333; padding: 10px; margin-bottom: 20px;">
            <ul style="list-style-type: none; padding: 0; display: flex; flex-wrap: wrap;">
                {% if subpath %}
                <li style="margin-right: 10px;">
                    <a href="{{ url_for('index', subpath='/'.join(subpath.split('/')[:-1])) }}">
                        <button style="background-color: #444; color: #E5E5E5; padding: 8px 16px; border: none; cursor: pointer;">
                            .. (Go Up)
                        </button>
                    </a>
                </li>
                {% endif %}
                {% for directory in directories %}
                <li style="margin-right: 10px;">
                    <a href="{{ url_for('index', subpath=subpath + '/' + directory) }}">
                        <button style="background-color: #444; color: #E5E5E5; padding: 8px 16px; border: none; cursor: pointer;">
                            {{ directory }}/
                        </button>
                    </a>
                </li>
                {% endfor %}
            </ul>
        </div>

        <!-- Book covers -->
        <ul>
            {% for file in files %}
            <li style="display: inline-block; margin: 10px;">
                <div style="text-align: center; padding: 10px; border: 2px solid transparent;">
                    <img src="{{ url_for('serve_cover', subpath=subpath, filename=file) }}" 
                        alt="{{ file }}" 
                        style="width: 150px; height: 250px; object-fit: cover; transition: transform 0.2s; cursor: pointer;" 
                        onclick="openModal('{{ url_for('serve_cover', subpath=subpath, filename=file) }}')">
                    <br>
                    <span>{{ file }}</span>
                    <br>
                    <a href="{{ url_for('serve_book', subpath=subpath, filename=file) }}">
                        <button type="button">Download</button>
                    </a>
                </div>
            </li>
            {% endfor %}
        </ul>

        <!-- Modal for displaying book covers in full screen -->
        <div id="imageModal" class="modal">
            <span onclick="closeModal()" style="position: absolute; top: 20px; right: 35px; color: #f1f1f1; font-size: 40px; font-weight: bold; cursor: pointer;">&times;</span>
            <img id="modalImage" style="margin: auto; display: block; width: 80%; max-width: 700px;">
        </div>

        <script>
            function openModal(imageSrc) {
                var modal = document.getElementById('imageModal');
                var modalImg = document.getElementById('modalImage');
                modal.style.display = "block";
                modalImg.src = imageSrc;
            }

            function closeModal() {
                var modal = document.getElementById('imageModal');
                modal.style.display = "none";
            }

            // Download all books
            document.getElementById('download-all-btn').addEventListener('click', function() {
                // Fetch the links from the server for downloading all files
                fetch('{{ url_for("download_directory", subpath=subpath) }}')
                .then(response => response.json())
                .then(data => {
                    data.links.forEach(function(link) {
                        // Create an anchor element for each link and click it to download
                        var a = document.createElement('a');
                        a.href = link;
                        a.setAttribute('download', '');  // Ensures the browser downloads the file
                        document.body.appendChild(a);
                        a.click();  // Trigger the download
                        document.body.removeChild(a);
                    });
                });
            });
        </script>
    </body>
    </html>
    ''', directories=directories, files=files, subpath=subpath)


@app.route('/upload/<path:subpath>', methods=['POST'])
def upload_file(subpath):
    if not is_authenticated():
        return redirect(url_for('login'))

    current_dir = os.path.join(BOOKS_DIR, subpath)

    if 'file[]' not in request.files:
        flash('No file part')
        return redirect(request.url)

    files = request.files.getlist('file[]')
    for file in files:
        if file and allowed_file(file.filename):
            filename = file.filename
            file.save(os.path.join(current_dir, filename))

    flash('Upload successful!')
    return redirect(url_for('index', subpath=subpath))


@app.route('/books/<path:subpath>/<filename>')
def serve_book(subpath, filename):
    if not is_authenticated():
        return redirect(url_for('login'))

    book_path = os.path.join(BOOKS_DIR, subpath)
    return send_from_directory(book_path, filename, as_attachment=True)


@app.route('/cover/<path:subpath>/<filename>')
def serve_cover(subpath, filename):
    if not is_authenticated():
        return redirect(url_for('login'))

    book_path = os.path.join(BOOKS_DIR, subpath, filename)
    cover = extract_cover_image(book_path)

    if cover:
        return send_file(cover, mimetype='image/png')
    else:
        return send_from_directory('static', 'no_cover.png')


@app.route('/download_dir/<path:subpath>')
def download_directory(subpath):
    if not is_authenticated():
        return redirect(url_for('login'))

    directory_path = os.path.join(BOOKS_DIR, subpath)
    _, files = get_directory_structure(directory_path)

    # Create a list of download links for all files
    download_links = [
        url_for('serve_book', subpath=subpath, filename=file) for file in files]
    return jsonify({"links": download_links})

class DirectoryWatcher(FileSystemEventHandler):
    def __init__(self, directory, callback):
        self.directory = directory
        self.callback = callback

    def on_modified(self, event):
        if event.is_directory:
            self.callback()

def watch_directory(directory, callback):
    event_handler = DirectoryWatcher(directory, callback)
    observer = Observer()
    observer.schedule(event_handler, directory, recursive=True)
    observer.start()
    return observer

def reload_ui():
    print('Directory changed, reloading UI...')

if __name__ == '__main__':
    observer = watch_directory(BOOKS_DIR, reload_ui)

    try:
        app.run(debug=False, port=8085, host='0.0.0.0')
    finally:
        observer.stop()
        observer.join()