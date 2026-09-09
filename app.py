import os
import re
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from database import db, Admin, Post, Category

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-later')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///fareflock.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


# ---------- PUBLIC ROUTES ----------

@app.route('/')
def home():
    latest_posts = Post.query.filter_by(published=True).order_by(Post.created_at.desc()).limit(3).all()
    return render_template('index.html', posts=latest_posts)


@app.route('/flights')
def flights():
    return render_template('flights.html')


@app.route('/hotels')
def hotels():
    return render_template('hotels.html')


@app.route('/blog')
def blog():
    posts = Post.query.filter_by(published=True).order_by(Post.created_at.desc()).all()
    return render_template('blog.html', posts=posts)


@app.route('/blog/<slug>')
def post_detail(slug):
    post = Post.query.filter_by(slug=slug, published=True).first_or_404()
    post.view_count = (post.view_count or 0) + 1
    db.session.commit()
    related = Post.query.filter(
        Post.category_id == post.category_id,
        Post.id != post.id,
        Post.published == True
    ).limit(3).all()
    return render_template('post.html', post=post, related=related)


@app.route('/about')
def about():
    return render_template('about.html')


# ---------- ADMIN AUTH ----------

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username).first()
        if admin and bcrypt.check_password_hash(admin.password_hash, password):
            login_user(admin)
            return redirect(url_for('admin_dashboard'))
        flash('Invalid username or password.')
    return render_template('login.html')


@app.route('/admin/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ---------- ADMIN DASHBOARD ----------

@app.route('/admin')
@login_required
def admin_dashboard():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('admin/dashboard.html', posts=posts)


@app.route('/admin/post/new', methods=['GET', 'POST'])
@login_required
def new_post():
    categories = Category.query.all()
    if request.method == 'POST':
        title = request.form.get('title')
        body = request.form.get('body')
        meta_description = request.form.get('meta_description')
        category_id = request.form.get('category_id') or None
        published = True if request.form.get('published') == 'on' else False

        slug = slugify(title)
        if Post.query.filter_by(slug=slug).first():
            slug = f"{slug}-{int(datetime.utcnow().timestamp())}"

        post = Post(
            title=title,
            slug=slug,
            body=body,
            meta_description=meta_description,
            category_id=category_id,
            published=published
        )
        db.session.add(post)
        db.session.commit()
        flash('Post created.')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin/post_form.html', categories=categories, post=None)


@app.route('/admin/post/edit/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    categories = Category.query.all()
    if request.method == 'POST':
        post.title = request.form.get('title')
        post.body = request.form.get('body')
        post.meta_description = request.form.get('meta_description')
        post.category_id = request.form.get('category_id') or None
        post.published = True if request.form.get('published') == 'on' else False
        db.session.commit()
        flash('Post updated.')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin/post_form.html', categories=categories, post=post)


@app.route('/admin/post/delete/<int:post_id>')
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted.')
    return redirect(url_for('admin_dashboard'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)