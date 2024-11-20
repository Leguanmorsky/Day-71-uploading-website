from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, abort,request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from forms import CreatePostForm
import os
from forms import RegisterForm, LoginForm, CreatePostForm, CommentForm
import smtplib
from time import sleep
import requests
import os
from dotenv import load_dotenv
import gunicorn
import psycopg2
from urllib.parse import quote
# "C:\Users\jirka\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.10_qbz5n2kfra8p0\LocalCache\local-packages\Python310\Scripts\pipreqs.exe" ./ --force
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap5(app)

login_manager = LoginManager()
login_manager.init_app(app)

# Not sure how, but it is able to determine, whether you  are logged or not and holding you as a current user
@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

my_email=os.environ.get("MY_EMAIL")
my_password=os.environ.get("PASSWORD")

# CREATE DATABASE
class Base(DeclarativeBase):
    pass
db_path = os.path.join('C:/Users/jirka/Desktop/100 days challenge/Udemy/Day 69 Capstone part 4/instance/posts.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
# app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI",f'sqlite:///{db_path}')
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
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"),nullable=False)
    # parent from a class User
    author = relationship("User", back_populates="posts")
    # Children from a class Comment
    post_comments=relationship("Comment", back_populates="comment_of_post")

# Creates a table in sqalchemy. User is the object which is parent for all and Usermixin ensures, the login manager gets everything neccessary...
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    profile_url: Mapped[str] = mapped_column(String(250), nullable=False)
    # Children from  a class BlogPost
    posts = relationship("BlogPost", back_populates="author")
    # Children from a class Comment
    comments = relationship("Comment", back_populates="comment_author")

# Table in sqalchemy, that is either connected to the user and the blog..(specific user writes under specific blog)
class Comment(db.Model):
    __tablename__="comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"),nullable=False)
    # parent from a class User
    comment_author = relationship("User", back_populates="comments")
    # ....................................
    post_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("blog_posts.id"),nullable=False)
    # parent from a class BlogPost
    comment_of_post=relationship("BlogPost", back_populates="post_comments")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    
with app.app_context():
    db.create_all()

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        #If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        #Otherwise continue with the route function
        return f(*args, **kwargs)        
    return decorated_function

# def logged_only(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         # If user is not logged return abort with 403 error
#         if not current_user.is_authenticated:
#             return abort(403)
#         # Otherwise continue with routine function
#         return f(*args,**kwargs)
#     return decorated_function
    
@app.route('/register', methods=["GET", "POST"])
def register():
    # takes a fillout form from forms.py...waits for submit button and then check if the provided email isn't already in  the database.
    form = RegisterForm()
    if form.validate_on_submit():
        result=db.session.execute(db.select(User).where(User.email == form.email.data))
        user=result.scalar()
        if user:
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for("login"))
        
        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        # creates a new user to the database....
        new_user = User(
            email=form.email.data,
            name=form.name.data,
            password=hash_and_salted_password,
            profile_url=form.profile_url.data,
        )
        db.session.add(new_user)
        db.session.commit()
        
        # this below is giving information to the login_manager..
        login_user(new_user)
        return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=form, current_user=current_user)

@app.route('/login', methods=["GET", "POST"])
def login():
    # Again it takes all information provided by user from the forms.py
    form=LoginForm()
    if form.validate_on_submit():
        email=form.email.data
        password=form.password.data
        # It finds user in the database which has the same mail as the provided one....if, else...
        result=db.session.execute(db.select(User).where(User.email == email))
        user=result.scalar()
        if not user:
            flash("That email does not exist, please try again!")
            return redirect(url_for("login"))
        if not check_password_hash(user.password,password):
            flash("Password incorrect. Please try again!")
            return redirect(url_for("login"))
        else:
            login_user(user)
            return redirect(url_for("get_all_posts"))
    return render_template("login.html",form=form, current_user=current_user)

# this is controlled just by the login manager...
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))

@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts, current_user=current_user)

@app.route("/post/<int:post_id>", methods=["GET","POST"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    comment_form=CommentForm()
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))
        new_comment=Comment(
            text=comment_form.text.data,
            comment_author=current_user,
            comment_of_post=requested_post
        )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("post.html", post=requested_post, current_user=current_user, form=comment_form)

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
    return render_template("make-post.html", form=form, current_user=current_user)

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
    return render_template("make-post.html", form=edit_form, is_edit=True, current_user=current_user)

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
    return render_template("about.html", current_user=current_user)

@app.route("/contact")
def get_contact():
    return render_template("contact.html",current_user=current_user)

@app.route("/contact",methods=["GET","POST"])
def recieve_data():
    if request.method=="POST":
        if not current_user.is_authenticated:
            flash("You need to login or register to Write Messages.")
            return redirect(url_for("login"))
        else:
            name=request.form["name"]
            email=request.form["email"]
            phone=request.form["phone"]
            message=request.form["message"]
            sleep(2)
            return send_email(name,email,phone,message)
        
def send_email(name,email,phone,message):  
    with smtplib.SMTP("smtp.gmail.com",587) as connection:
        connection.starttls()
        connection.login(user=my_email,password=my_password)
        connection.sendmail(from_addr=my_email,
                            to_addrs=my_email,
                            msg=(f"Subject: Client Message\n\nName: {name}\nEmail: {email}\nPhone: {phone}\nMessage: \n{message}").encode(encoding='utf-8', errors='strict')
                            )
             
    return render_template("contact.html", msg_sent=True,current_user=current_user)

if __name__ == "__main__":
    app.run(debug=True, port=5002)
