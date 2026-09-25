# The Flask Fundamentals Cheatsheet

This document covers some of the core concepts that are used by the Blua Family API. It is not an exhaustive Flask tutorial, but rather a quick reference to help you understand the key parts of a Flask application.

### 1. Creating Your First Flask App

This is the "Hello, World!" of Flask. It's the absolute minimum you need to get a web server running.

**File: `app.py`**

```python
# 1. Import the Flask class
from flask import Flask

# 2. Create an instance of the Flask class
#    __name__ tells Flask where to look for resources like templates and static files.
app = Flask(__name__)

# 3. Define a "view function" for the root URL ("/")
@app.route('/')
def hello_world():
    return '<h1>Hello, World!</h1>'

# 4. A guard to run the app when the script is executed directly
if __name__ == '__main__':
    # debug=True enables the debugger and auto-reloader. Awesome for development!
    app.run(debug=True)
```

**To run it:**
Open your terminal and run `python app.py`. You'll see a message telling you the server is running at `http://127.0.0.1:5000`.

---

### 2. Routes and HTTP Methods (GET, POST, etc.)

A "route" maps a URL to a Python function. By default, routes only respond to `GET` requests. You can easily allow other methods like `POST` for handling form submissions or API calls.

```python
from flask import Flask, request

app = Flask(__name__)

# This route only accepts GET requests (the default)
@app.route('/profile')
def view_profile():
    return "This is a user's profile page."

# This route accepts both GET and POST requests
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Logic for handling the login form data
        username = request.form.get('username')
        return f"Welcome back, {username}!"
    else:
        # Logic for showing the login form
        return """
            <form method="post">
                Username: <input type="text" name="username">
                <input type="submit" value="Login">
            </form>
        """
```

**Key Points:**
*   `@app.route()` is a **decorator** that turns a regular Python function into a Flask view function.
*   The `methods` argument is a list of HTTP methods the route should respond to.
*   The `request` object (imported from `flask`) gives you access to all the data from the incoming request.

---

### 3. Accessing Request Data

The global `request` object holds all the information from the client. We've seen `request.method` and `request.form`. Here are two more you'll use constantly:

*   `request.args`: A dictionary-like object containing the **query string parameters** (the part of the URL after `?`).
*   `request.get_json()`: Parses incoming JSON request bodies (common for APIs).

```python
from flask import request, jsonify

# Example for request.args
# URL: /search?q=flask&page=2
@app.route('/search')
def search():
    query = request.args.get('q', 'default_search_term') # .get() is safe, returns None if not found
    page = request.args.get('page', 1, type=int) # You can even specify a type
    return f"<h1>Searching for: {query}</h1><p>You are on page: {page}</p>"

# Example for request.get_json()
# Client would send a POST request with Content-Type: application/json
# and a body like: {"name": "new item"}
@app.route('/api/items', methods=['POST'])
def create_item():
    # If the request isn't JSON or is malformed, this returns an error.
    data = request.get_json()
    new_item_name = data.get('name')
    # ... logic to save the new item ...
    return jsonify({'message': f'Item "{new_item_name}" created'}), 201
```

---

### 4. Variable URLs / Dynamic Routes

Often, you want a URL to capture a value, like a user's ID or a blog post's slug.

```python
from flask import Flask

app = Flask(__name__)

# The <username> part is a variable.
# Whatever is in that part of the URL is passed to the function.
@app.route('/user/<username>')
def show_user_profile(username):
    return f"Displaying profile for user: {username}"

# You can also specify a type! Flask will validate it for you.
# If you visit /post/abc, you'll get a 404 Not Found error.
@app.route('/post/<int:post_id>')
def show_post(post_id):
    # post_id will be an integer, not a string
    return f"Displaying blog post number: {post_id}"
```

**Common Converters:**
*   `string`: (Default) Accepts any text without a slash.
*   `int`: Accepts positive integers.
*   `float`: Accepts positive floating-point values.
*   `path`: Like `string`, but also accepts slashes.

---

### 5. Blueprints (Organising Your App)

As your app grows, putting all your routes in one file gets messy. **Blueprints** are Flask's way of letting you organise your app into reusable components. They are perfect for versioning an API.

Let's create a `v1` for our API.

**File: `api/v1_routes.py`**

```python
# A Blueprint is like a "mini-app"
from flask import Blueprint, jsonify

# 1. Create the Blueprint
#    'v1' is the name of the blueprint.
#    __name__ helps it locate resources.
#    url_prefix will be added to all routes in this blueprint.
v1 = Blueprint('v1', __name__, url_prefix='/api/v1')

# 2. Create routes on the blueprint, not the app
@v1.route('/users')
def get_users():
    users = [
        {'id': 1, 'name': 'Alice'},
        {'id': 2, 'name': 'Bob'}
    ]
    return jsonify(users)

@v1.route('/users/<int:user_id>')
def get_user(user_id):
    # In a real app, you'd look this up in a database
    return jsonify({'id': user_id, 'name': 'Sample User'})
```

**File: `app.py` (Main App)**

```python
from flask import Flask
# 3. Import your blueprint
from api.v1_routes import v1

app = Flask(__name__)

# 4. Register the blueprint with your main app
app.register_blueprint(v1)

@app.route('/')
def index():
    return "Go to /api/v1/users to see the API in action!"

if __name__ == '__main__':
    app.run(debug=True)
```

Now, your API routes are neatly contained, and you can access them at `http://.../api/v1/users`.

---

### 6. App & Request Contexts (The `g` Object)

Sometimes, you need to store temporary data for the duration of a *single request*. A classic example is the currently logged-in user. Using a global variable is dangerous in a web server.

Instead, Flask gives you the `g` object. Think of it as a **temporary notepad for each request**.

```python
from flask import Flask, g, request

app = Flask(__name__)

def get_current_user():
    # In a real app, you'd get this from a session cookie or auth header
    # For our example, we'll pretend user 'admin' is always logged in.
    return {'name': 'admin', 'role': 'editor'}

# This function runs BEFORE every request
@app.before_request
def load_user_into_g():
    # Store the user object on 'g' for this request
    g.user = get_current_user()

@app.route('/dashboard')
def dashboard():
    # Now, any view function can access g.user without re-calculating it
    if g.user:
        return f"Welcome to your dashboard, {g.user['name']}!"
    return "Welcome, guest!"

@app.route('/settings')
def settings():
    # The same g.user is available here, too!
    return f"Settings for user: {g.user['name']} ({g.user['role']})"
```
**Why `g`?**
*   **Request-Bound:** The data in `g` is unique to each request and is cleared automatically after the request is finished.
*   **Safe:** Prevents data from one user's request from leaking into another's.

---

### 7. Returning JSON with `jsonify`

When building an API, you need to return data in JSON format. While you *could* use Python's `json` library, Flask provides a helper that does it the *right* way.

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/health')
def api_health():
    # Data to be sent as JSON
    status_data = {
        'status': 'OK',
        'service': 'My Awesome API',
        'version': '1.0'
    }
    
    # Use jsonify() to convert the dict to a JSON response
    return jsonify(status_data)
```

**Why use `jsonify`?**
1.  **Correct MimeType:** It automatically sets the `Content-Type` header to `application/json`. This is crucial for clients to understand the response.
2.  **Proper Response Object:** It creates a Flask `Response` object, not just a plain string.
3.  **Security:** It helps protect against certain JSON-related security vulnerabilities.

**Rule of thumb: If you are building an API in Flask, always use `jsonify` to return your JSON data.**

### 8. The `Response` Object: Taking Full Control

So far, our view functions have just returned strings (HTML) or a `jsonify` result. But what's happening behind the scenes? Flask takes that return value and wraps it in a **`Response` object**.

Think of a `Response` like a complete package being mailed:
*   **The Body:** The actual content (the HTML string, the JSON data).
*   **The Status Code:** A number indicating the result (e.g., `200 OK`, `404 Not Found`, `500 Server Error`).
*   **The Headers:** Extra metadata for the browser (e.g., `Content-Type`, caching instructions).

Most of the time, Flask figures this out for you:
*   `return '<h1>Hi</h1>'` -> Flask creates a `Response` with your HTML, a `200 OK` status, and a `Content-Type: text/html` header.
*   `return jsonify(...)` -> Flask creates a `Response` with your JSON, a `200 OK` status, and a `Content-Type: application/json` header.

But what if you need to control these things yourself? That's when you create the `Response` object explicitly using the `make_response` helper.

```python
from flask import Flask, make_response

app = Flask(__name__)

# Example 1: Setting a custom status code and header
@app.route('/create-resource', methods=['POST'])
def create_resource():
    # Let's pretend we successfully created something in the database.
    # The standard status code for "Created" is 201.
    
    # Use make_response to create the initial response object
    response = make_response("Resource created successfully", 201)
    
    # You can now add custom headers
    response.headers['X-Resource-ID'] = '12345'
    
    return response

# Example 2: Returning a different content type, like XML
@app.route('/sitemap.xml')
def sitemap():
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>http://www.example.com/foo</loc>
  </url>
</urlset>"""
    
    # Create the response with our XML string
    response = make_response(xml_content)
    
    # IMPORTANT: Tell the browser this is XML, not HTML!
    response.headers['Content-Type'] = 'application/xml'
    
    return response
```

**Key Takeaway:**
When you need to set a specific **status code** or custom **HTTP headers**, import and use `make_response()` to build your response object manually. It gives you complete control over what your server sends back to the client.