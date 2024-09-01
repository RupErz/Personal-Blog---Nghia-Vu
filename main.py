from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
import os


'''
Make sure the required packages are installed: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''

app = Flask(__name__)
# app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)

# TODO: Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

# Decorator function to handle "admin role" for create/delete/edit a post.
def admin_only(f):
    @wraps(f)
    @login_required # prevent -> AttributeError: 'AnonymousUserMixin' object has no attribute 'id'
    def decorated_function(*args, **kwargs):
        # If no one logged in - cant access to creat / edit /delete
        if current_user is None:
            return abort(403);
        else: #They do logged in but whether they are admin or not ?
            if current_user.id == 1:
                return f(*args, **kwargs)
            else:
                return abort(403)
    return decorated_function


# CREATE DATABASE
class Base(DeclarativeBase):
    pass
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", "sqlite:///posts.db")

db = SQLAlchemy(model_class=Base)
db.init_app(app)


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author = relationship("User", back_populates= "posts")
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    author_id : Mapped[int] = mapped_column(Integer, ForeignKey("user.id") )
    comments = relationship("Comment", back_populates="parent_post")


# TODO: Create a User table for all your registered users. 
class User(UserMixin ,db.Model):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(250))
    password: Mapped[str] = mapped_column(String(250))
    name: Mapped[str] = mapped_column(String(250))
    posts = relationship("BlogPost", back_populates= "author")
    comments = relationship("Comment", back_populates= "comment_author")

# Table for storing user comments :
class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author_id :Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    comment_author = relationship("User", back_populates="comments")
    post_id :Mapped[int] = mapped_column(Integer, ForeignKey("blog_posts.id") )
    parent_post = relationship("BlogPost", back_populates="comments")


with app.app_context():
    db.create_all()

# Create pic for comment for Gravatar
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods = ["GET", "POST"])
def register():
    register_form = RegisterForm()
    if register_form.validate_on_submit():
        user_name = register_form.name.data
        user_password = register_form.password.data
        user_password_hashed = generate_password_hash(user_password,"pbkdf2:sha256", 8)
        user_email = register_form.email.data
        new_user = User(email= user_email, password= user_password_hashed, name= user_name)
        existed_email = db.session.execute(db.select(User).where(User.email == user_email))
        existed_email_result = existed_email.scalar()

        # Checking if there is already an account or not
        if existed_email_result:
            flash("Account already exist, please log in instead!")
            return redirect(url_for("login"))
        else:
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for("get_all_posts"))

    return render_template("register.html", form= register_form, logged_in = current_user.is_authenticated)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods = ["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user_email = form.email.data
        user_password = form.password.data
        hash_password = db.session.execute(db.select(User).where(User.email == user_email))
        result = hash_password.scalar()
        # If there is a same email in the database => already registered
        if result:
            if check_password_hash(result.password, user_password) :
                login_user(result)
                return redirect(url_for("get_all_posts"))
            else :
                print(user_password)
                print(result.password)
                flash("Password not matched!")
                return redirect(url_for("login"))
        # else not : have not registered yet
        else:
            flash("Email does not exist! Pleased registered one!")
            return redirect(url_for("login"))
    return render_template("login.html", form= form, logged_in = current_user.is_authenticated)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))

@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts, logged_in = current_user.is_authenticated)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods = ["GET", "POST"])
def show_post(post_id):
    form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    if form.validate_on_submit():
        if not current_user.is_authenticated :
            flash("You need to log in or register to comment!")
            return redirect(url_for("login"))
        else:
            text = form.comment.data
            comment_author = current_user
            parent_post = requested_post
            new_comment = Comment(text= text, comment_author = comment_author, parent_post = parent_post)
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("get_all_posts"))
    return render_template("post.html", post=requested_post, logged_in = current_user.is_authenticated
                           , form= form, gravatar = gravatar)


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, logged_in = current_user.is_authenticated)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, logged_in = current_user.is_authenticated
                           , current_user =current_user)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html", logged_in = current_user.is_authenticated)


@app.route("/contact")
@login_required
def contact():
    return render_template("contact.html", logged_in = current_user.is_authenticated)


if __name__ == "__main__":
    app.run(debug=False, port=5002)
