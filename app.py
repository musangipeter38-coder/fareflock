import os
import re
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, abort, Response
from flask_login import LoginManager, login_user, logout_user, login_required
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from sqlalchemy import text
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

SITE_URL = os.environ.get('SITE_URL', 'https://fareflock.onrender.com')

SERVICE_CATEGORIES = [
    {'slug': 'flights', 'name': 'Flights', 'icon': '✈️', 'placement': 'flights_page', 'route': 'flights'},
    {'slug': 'hotels', 'name': 'Hotels & Accommodations', 'icon': '🛏️', 'placement': 'hotels_page', 'route': 'hotels'},
    {'slug': 'tours', 'name': 'Tours & Activities', 'icon': '🚶', 'placement': 'category_tours', 'route': None},
    {'slug': 'insurance', 'name': 'Insurance', 'icon': '🛡️', 'placement': 'category_insurance', 'route': None},
    {'slug': 'transfers', 'name': 'Transfers & Airport Services', 'icon': '🚕', 'placement': 'category_transfers', 'route': None},
    {'slug': 'trains-buses', 'name': 'Trains & Buses', 'icon': '🚆', 'placement': 'category_trains_buses', 'route': None},
    {'slug': 'car-rentals', 'name': 'Car & Bike Rentals', 'icon': '🚗', 'placement': 'category_car_rentals', 'route': None},
    {'slug': 'package-tours', 'name': 'Package Tours', 'icon': '🏝️', 'placement': 'category_package_tours', 'route': None},
    {'slug': 'other', 'name': 'Other', 'icon': '🔘', 'placement': 'category_other', 'route': None},
    {'slug': 'sim-cards', 'name': 'SIM Cards', 'icon': '📶', 'placement': 'category_sim_cards', 'route': None},
]


def get_category(slug):
    for cat in SERVICE_CATEGORIES:
        if cat['slug'] == slug:
            return cat
    return None


def category_url(cat):
    if cat['route']:
        return url_for(cat['route'])
    return url_for('category_page', slug=cat['slug'])


app.jinja_env.globals['SERVICE_CATEGORIES'] = SERVICE_CATEGORIES
app.jinja_env.globals['category_url'] = category_url


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


def widget_srcdoc(content):
    """
    Wraps a stored affiliate widget snippet in a minimal HTML document for
    the iframe's srcdoc. Includes a small script that continuously measures
    the widget's real rendered height and reports it to the parent page via
    postMessage, so the page can auto-resize the iframe to fit the widget
    exactly (no more clipped/scrolling widgets, no more manually guessed
    pixel heights in admin).
    """
    return (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<style>html,body{margin:0;padding:0;font-family:sans-serif;}"
        "img{max-width:100%;}</style>"
        "</head><body>" + content +
        "<script>"
        "(function(){"
        "function report(){"
        "var h=Math.max(document.documentElement.scrollHeight,document.body.scrollHeight);"
        "window.parent.postMessage({fareflockWidgetHeight:h},'*');"
        "}"
        "window.addEventListener('load',report);"
        "if(window.ResizeObserver){new ResizeObserver(report).observe(document.body);}"
        "setInterval(report,1000);"
        "})();"
        "</script>"
        "</body></html>"
    )


app.jinja_env.filters['widget_srcdoc'] = widget_srcdoc


# ---------- PUBLIC ROUTES ----------

@app.route('/')
def home():
    widgets = get_widgets('homepage')
    return render_template(
        'index.html', widgets=widgets,
        meta_title='Fareflock — Explore All Travel Services',
        meta_description='Flights, hotels, tours, insurance, and more — real deals and honest guides, all in one place.'
    )


@app.route('/explore')
def explore():
    return redirect(url_for('home'), code=301)


@app.route('/flights')
def flights():
    widgets = get_widgets('flights_page')
    tips = get_tips('flights')
    return render_template(
        'flights.html', widgets=widgets, tips=tips,
        meta_title='Find Cheap Flights — Fareflock',
        meta_description='Search real-time flight deals and read honest booking tips, curated by Fareflock.'
    )


@app.route('/hotels')
def hotels():
    widgets = get_widgets('hotels_page')
    tips = get_tips('hotels')
    return render_template(
        'hotels.html', widgets=widgets, tips=tips,
        meta_title='Find Hotels — Fareflock',
        meta_description='Hotel deals worldwide, curated for real budgets, plus honest guides on picking the right stay.'
    )


@app.route('/category/<slug>')
def category_page(slug):
    cat = get_category(slug)
    if not cat or cat['route']:
        abort(404)
    widgets = get_widgets(cat['placement'])
    return render_template(
        'category.html', category=cat, widgets=widgets,
        meta_title=f"{cat['name']} — Fareflock",
        meta_description=f"{cat['name']} deals and options, curated by Fareflock."
    )


@app.route('/tips')
def all_tips():
    tips = Tip.query.filter_by(active=True).order_by(Tip.created_at.desc()).all()
    return render_template(
        'tips.html', tips=tips,
        meta_title='Travel Tips & Guides — Fareflock',
        meta_description='Every travel guide and booking tip Fareflock has shared, all in one place.'
    )


@app.route('/blog')
def blog():
    posts = Post.query.filter_by(published=True).order_by(Post.created_at.desc()).all()
    return render_template(
        'blog.html', posts=posts,
        meta_title='Blog — Fareflock',
        meta_description='Guides, deals, and honest travel advice from Fareflock.'
    )


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
    return render_template(
        'post.html', post=post, related=related,
        meta_title=f'{post.title} — Fareflock',
        meta_description=post.meta_description or 'Read this travel guide on Fareflock.'
    )


@app.route('/about')
def about():
    return render_template(
        'about.html',
        meta_title='About — Fareflock',
        meta_description='Fareflock is a global travel deals and guides site, built with real depth instead of recycled listicles.'
    )


# ---------- SEO: SITEMAP & ROBOTS ----------

@app.route('/sitemap.xml')
def sitemap():
    posts = Post.query.filter_by(published=True).all()
    static_pages = ['/', '/flights', '/hotels', '/blog', '/tips', '/about']
    for cat in SERVICE_CATEGORIES:
        if not cat['route']:
            static_pages.append(f"/category/{cat['slug']}")

    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for page in static_pages:
        xml_parts.append(f'<url><loc>{SITE_URL}{page}</loc></url>')

    for post in posts:
        xml_parts.append(f'<url><loc>{SITE_URL}/blog/{post.slug}</loc></url>')

    xml_parts.append('</urlset>')
    xml_content = ''.join(xml_parts)

    return Response(xml_content, mimetype='application/xml')


@app.route('/robots.txt')
def robots():
    content = f"User-agent: *\nAllow: /\nDisallow: /admin/\nSitemap: {SITE_URL}/sitemap.xml\n"
    return Response(content, mimetype='text/plain')


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
            active=True if request.form.get('active') == 'on' else False,
            height=int(request.form.get('height') or 500)
        )
        db.session.add(link)
        db.session.commit()
        flash('Affiliate link/widget created.')
        return redirect(url_for('admin_links'))
    return render_template('admin/link_form.html', link=None, categories=SERVICE_CATEGORIES)


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
        link.height = int(request.form.get('height') or 500)
        db.session.commit()
        flash('Updated.')
        return redirect(url_for('admin_links'))
    return render_template('admin/link_form.html', link=link, categories=SERVICE_CATEGORIES)


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
    try:
        db.session.execute(text('ALTER TABLE affiliate_link ADD COLUMN IF NOT EXISTS height INTEGER DEFAULT 500'))
        db.session.commit()
    except Exception:
        db.session.rollback()

if __name__ == '__main__':
    app.run(debug=True)