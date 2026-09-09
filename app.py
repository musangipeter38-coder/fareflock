import os
import re
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from database import db, Admin, Post, Category, AffiliateLink, ClickLog, Tip

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


def slugify(text_in):
    text_in = text_in.lower().strip()
    text_in = re.sub(r'[^a-z0-9]+', '-', text_in)
    return text_in.strip('-')


def get_widgets(placement):
    return AffiliateLink.query.filter_by(
        placement=placement, link_type='widget', active=True
    ).order_by(AffiliateLink.created_at.asc()).all()


def get_tips(page):
    return Tip.query.filter_by(page=page, active=True).order_by(Tip.created_at.asc()).all()


# ---------- PUBLIC ROUTES ----------

@app.route('/')
def home():
    latest_posts = Post.query.filter_by(published=True).order_by(Post.created_at.desc()).limit(3).all()
    widgets = get_widgets('homepage')
    return render_template('index.html', posts=latest_posts, widgets=widgets)


@app.route('/flights')
def flights():
    widgets = get_widgets('flights_page')
    tips = get_tips('flights')
    return render_template('flights.html', widgets=widgets, tips=tips)


@app.route('/hotels')
def hotels():
    widgets = get_widgets('hotels_page')
    tips = get_tips('hotels')
    return render_template('hotels.html', widgets=widgets, tips=tips)


@app.route('/tips')
def all_tips():
    tips = Tip.query.filter_by(active=True).order_by(Tip.created_at.desc()).all()
    return render_template('tips.html', tips=tips)


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


# ---------- CLICK TRACKING ----------

@app.route('/out/<int:link_id>')
def out(link_id):
    link = AffiliateLink.query.get_or_404(link_id)
    if link.link_type != 'url':
        abort(404)

    post_slug = request.args.get('post')
    click = ClickLog(affiliate_link_id=link.id, post_slug=post_slug)
    db.session.add(click)
    db.session.commit()

    return redirect(link.content)


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
            title=title, slug=slug, body=body,
            meta_description=meta_description,
            category_id=category_id, published=published
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


# ---------- ADMIN: AFFILIATE LINKS ----------

@app.route('/admin/links')
@login_required
def admin_links():
    links = AffiliateLink.query.order_by(AffiliateLink.created_at.desc()).all()
    click_counts = {}
    for link in links:
        click_counts[link.id] = ClickLog.query.filter_by(affiliate_link_id=link.id).count()
    return render_template('admin/links.html', links=links, click_counts=click_counts)


@app.route('/admin/links/new', methods=['GET', 'POST'])
@login_required
def new_link():
    if request.method == 'POST':
        link = AffiliateLink(
            name=request.form.get('name'),
            link_type=request.form.get('link_type'),
            placement=request.form.get('placement') or None,
            content=request.form.get('content'),
            description=request.form.get('description'),
            active=True if request.form.get('active') == 'on' else False
        )
        db.session.add(link)
        db.session.commit()
        flash('Affiliate link/widget created.')
        return redirect(url_for('admin_links'))
    return render_template('admin/link_form.html', link=None)


@app.route('/admin/links/edit/<int:link_id>', methods=['GET', 'POST'])
@login_required
def edit_link(link_id):
    link = AffiliateLink.query.get_or_404(link_id)
    if request.method == 'POST':
        link.name = request.form.get('name')
        link.link_type = request.form.get('link_type')
        link.placement = request.form.get('placement') or None
        link.content = request.form.get('content')
        link.description = request.form.get('description')
        link.active = True if request.form.get('active') == 'on' else False
        db.session.commit()
        flash('Updated.')
        return redirect(url_for('admin_links'))
    return render_template('admin/link_form.html', link=link)


@app.route('/admin/links/delete/<int:link_id>')
@login_required
def delete_link(link_id):
    link = AffiliateLink.query.get_or_404(link_id)
    db.session.delete(link)
    db.session.commit()
    flash('Deleted.')
    return redirect(url_for('admin_links'))


# ---------- ADMIN: TIPS ----------

@app.route('/admin/tips')
@login_required
def admin_tips():
    tips = Tip.query.order_by(Tip.created_at.desc()).all()
    return render_template('admin/tips.html', tips=tips)


@app.route('/admin/tips/new', methods=['GET', 'POST'])
@login_required
def new_tip():
    if request.method == 'POST':
        tip = Tip(
            title=request.form.get('title'),
            content=request.form.get('content'),
            page=request.form.get('page'),
            active=True if request.form.get('active') == 'on' else False
        )
        db.session.add(tip)
        db.session.commit()
        flash('Tip created.')
        return redirect(url_for('admin_tips'))
    return render_template('admin/tip_form.html', tip=None)


@app.route('/admin/tips/edit/<int:tip_id>', methods=['GET', 'POST'])
@login_required
def edit_tip(tip_id):
    tip = Tip.query.get_or_404(tip_id)
    if request.method == 'POST':
        tip.title = request.form.get('title')
        tip.content = request.form.get('content')
        tip.page = request.form.get('page')
        tip.active = True if request.form.get('active') == 'on' else False
        db.session.commit()
        flash('Updated.')
        return redirect(url_for('admin_tips'))
    return render_template('admin/tip_form.html', tip=tip)


@app.route('/admin/tips/delete/<int:tip_id>')
@login_required
def delete_tip(tip_id):
    tip = Tip.query.get_or_404(tip_id)
    db.session.delete(tip)
    db.session.commit()
    flash('Deleted.')
    return redirect(url_for('admin_tips'))


# ---------- DATABASE SETUP ----------
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)