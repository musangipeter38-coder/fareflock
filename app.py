import os
import re
import base64
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, abort, Response, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from sqlalchemy import text
from database import db, Admin, Post, Category, AffiliateLink, ClickLog, Tip, ChatMessage, CategoryImage, DealBanner

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-later')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///fareflock.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

db.init_app(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

SITE_URL = os.environ.get('SITE_URL', 'https://fareflock.com')
WHATSAPP_NUMBER = os.environ.get('WHATSAPP_NUMBER', '')

SOCIAL_LINKS = {
    'facebook': 'https://facebook.com/fareflock',
    'instagram': 'https://instagram.com/fareflock_01',
    'youtube': 'https://youtube.com/@fareflock',
    'tiktok': 'https://tiktok.com/@fareflock.com',
}

SERVICE_CATEGORIES = [
    {'slug': 'flights', 'name': 'Flights', 'icon': '✈️', 'placement': 'flights_page', 'route': 'flights'},
    {'slug': 'tours', 'name': 'Tours & Activities', 'icon': '🚶', 'placement': 'category_tours', 'route': None},
    {'slug': 'transfers', 'name': 'Transfers & Airport Services', 'icon': '🚕', 'placement': 'category_transfers', 'route': None},
    {'slug': 'car-rentals', 'name': 'Car & Bike Rentals', 'icon': '🚗', 'placement': 'category_car_rentals', 'route': None},
    {'slug': 'other', 'name': 'Other', 'icon': '🔘', 'placement': 'category_other', 'route': None},
    {'slug': 'sim-cards', 'name': 'SIM Cards', 'icon': '📶', 'placement': 'category_sim_cards', 'route': None},
]

# Every placement key available for widgets to be assigned to, with a readable label.
PLACEMENT_OPTIONS = [{'key': 'homepage', 'label': 'Homepage'}] + [
    {'key': cat['placement'], 'label': f"{cat['icon']} {cat['name']}"} for cat in SERVICE_CATEGORIES
]

BLOG_VISUALS = [
    {'match': 'flight', 'icon': '✈️', 'gradient': 'grad-blue'},
    {'match': 'hotel', 'icon': '🛏️', 'gradient': 'grad-purple'},
    {'match': 'tour', 'icon': '🚶', 'gradient': 'grad-teal'},
    {'match': 'guide', 'icon': '🧭', 'gradient': 'grad-blue'},
    {'match': 'review', 'icon': '⭐', 'gradient': 'grad-pink'},
    {'match': 'visa', 'icon': '🛂', 'gradient': 'grad-teal'},
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


def get_category_images():
    rows = CategoryImage.query.all()
    return {r.slug: r.image_url for r in rows if r.image_url}


def get_active_deal():
    return DealBanner.query.filter_by(active=True).order_by(DealBanner.updated_at.desc()).first()


def asset_version(filename):
    try:
        path = os.path.join(app.root_path, 'static', filename)
        return str(int(os.path.getmtime(path)))
    except OSError:
        return '1'


def post_visual(post):
    name = (post.category.name.lower() if post.category else '')
    for v in BLOG_VISUALS:
        if v['match'] in name:
            return v
    return {'icon': '📝', 'gradient': 'grad-blue'}


def reading_time(body):
    text_only = re.sub(r'<[^>]+>', ' ', body or '')
    words = len(text_only.split())
    minutes = max(1, round(words / 200))
    return minutes


app.jinja_env.globals['SERVICE_CATEGORIES'] = SERVICE_CATEGORIES
app.jinja_env.globals['SOCIAL_LINKS'] = SOCIAL_LINKS
app.jinja_env.globals['category_url'] = category_url
app.jinja_env.globals['asset_version'] = asset_version
app.jinja_env.globals['WHATSAPP_NUMBER'] = WHATSAPP_NUMBER
app.jinja_env.globals['post_visual'] = post_visual
app.jinja_env.globals['reading_time'] = reading_time
app.jinja_env.globals['SITE_URL'] = SITE_URL


@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))


def slugify(text_in):
    text_in = text_in.lower().strip()
    text_in = re.sub(r'[^a-z0-9]+', '-', text_in)
    return text_in.strip('-')


def get_widgets(placement_key):
    """Return active widgets whose placement list includes placement_key."""
    all_widgets = AffiliateLink.query.filter_by(
        link_type='widget', active=True
    ).order_by(AffiliateLink.created_at.asc()).all()
    result = []
    for w in all_widgets:
        keys = [p.strip() for p in (w.placement or '').split(',') if p.strip()]
        if placement_key in keys:
            result.append(w)
    return result


def get_tips(page):
    return Tip.query.filter_by(page=page, active=True).order_by(Tip.created_at.asc()).all()


def widget_srcdoc(content):
    resize_script = """
    <script>
    (function() {
        var tries = 0;
        function sendHeight() {
            var h = document.body ? document.body.scrollHeight : 0;
            parent.postMessage({ fareflockWidgetHeight: h }, '*');
        }
        window.addEventListener('load', sendHeight);
        var interval = setInterval(function() {
            sendHeight();
            tries++;
            if (tries > 20) { clearInterval(interval); }
        }, 500);
    })();
    </script>
    """
    return (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
        "<style>body{margin:0;padding:0;font-family:sans-serif;}</style>"
        "</head><body>" + content + resize_script + "</body></html>"
    )


app.jinja_env.filters['widget_srcdoc'] = widget_srcdoc


@app.after_request
def add_cache_headers(response):
    if response.status_code == 200 and not request.path.startswith('/admin'):
        if response.content_type and 'text/html' in response.content_type:
            response.headers['Cache-Control'] = 'private, max-age=60'
    return response


# ---------- PUBLIC ROUTES ----------

@app.route('/')
def home():
    widgets = get_widgets('homepage')
    cat_images = get_category_images()
    deal = get_active_deal()
    return render_template(
        'index.html', widgets=widgets, cat_images=cat_images, deal=deal,
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
    featured = posts[0] if posts else None
    rest = posts[1:] if len(posts) > 1 else []
    return render_template(
        'blog.html', featured=featured, posts=rest, total_count=len(posts),
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


# ---------- CHAT / CONTACT ----------

@app.route('/api/contact', methods=['POST'])
def submit_contact():
    name = request.form.get('name', '').strip()
    contact = request.form.get('contact', '').strip()
    message = request.form.get('message', '').strip()

    if not message:
        return jsonify({'ok': False, 'error': 'Message cannot be empty.'}), 400

    chat_msg = ChatMessage(name=name or 'Anonymous', contact=contact, message=message)
    db.session.add(chat_msg)
    db.session.commit()

    return jsonify({'ok': True})


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

    # Instead of an instant, jarring redirect, show a short branded bridge
    # page first — reassures the visitor the transition is intentional and
    # secure, rather than looking like they got bounced off-site randomly.
    return render_template('redirect_bridge.html', link=link)


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
        placements = request.form.getlist('placements')
        link = AffiliateLink(
            name=request.form.get('name'),
            link_type=request.form.get('link_type'),
            placement=','.join(placements),
            content=request.form.get('content'),
            description=request.form.get('description'),
            active=True if request.form.get('active') == 'on' else False,
            height=int(request.form.get('height') or 500)
        )
        db.session.add(link)
        db.session.commit()
        flash('Affiliate link/widget created.')
        return redirect(url_for('admin_links'))
    return render_template('admin/link_form.html', link=None, placement_options=PLACEMENT_OPTIONS)


@app.route('/admin/links/edit/<int:link_id>', methods=['GET', 'POST'])
@login_required
def edit_link(link_id):
    link = AffiliateLink.query.get_or_404(link_id)
    if request.method == 'POST':
        placements = request.form.getlist('placements')
        link.name = request.form.get('name')
        link.link_type = request.form.get('link_type')
        link.placement = ','.join(placements)
        link.content = request.form.get('content')
        link.description = request.form.get('description')
        link.active = True if request.form.get('active') == 'on' else False
        link.height = int(request.form.get('height') or 500)
        db.session.commit()
        flash('Updated.')
        return redirect(url_for('admin_links'))

    selected = [p.strip() for p in (link.placement or '').split(',') if p.strip()]
    return render_template('admin/link_form.html', link=link, placement_options=PLACEMENT_OPTIONS, selected_placements=selected)


@app.route('/admin/links/delete/<int:link_id>')
@login_required
def delete_link(link_id):
    link = AffiliateLink.query.get(link_id)
    if link:
        db.session.delete(link)
        db.session.commit()
        flash('Deleted.')
    else:
        flash('That link was already deleted.')
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


# ---------- ADMIN: MESSAGES ----------

@app.route('/admin/messages')
@login_required
def admin_messages():
    messages = ChatMessage.query.order_by(ChatMessage.created_at.desc()).all()
    return render_template('admin/messages.html', messages=messages)


@app.route('/admin/messages/reply/<int:msg_id>', methods=['POST'])
@login_required
def reply_message(msg_id):
    msg = ChatMessage.query.get_or_404(msg_id)
    msg.reply = request.form.get('reply')
    msg.replied = True
    db.session.commit()
    flash('Reply saved.')
    return redirect(url_for('admin_messages'))


@app.route('/admin/messages/delete/<int:msg_id>')
@login_required
def delete_message(msg_id):
    msg = ChatMessage.query.get_or_404(msg_id)
    db.session.delete(msg)
    db.session.commit()
    flash('Deleted.')
    return redirect(url_for('admin_messages'))


# ---------- ADMIN: CATEGORY BACKGROUND IMAGES ----------

ALLOWED_IMAGE_TYPES = {'image/png', 'image/jpeg', 'image/webp', 'image/gif'}
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # INCREASED LIMIT TO 10MB

@app.route('/admin/category-images', methods=['GET', 'POST'])
@login_required
def admin_category_images():
    if request.method == 'POST':
        for cat in SERVICE_CATEGORIES:
            file = request.files.get(cat['slug'])
            if not file or not file.filename:
                continue

            if file.mimetype not in ALLOWED_IMAGE_TYPES:
                flash(f"Skipped {cat['name']}: unsupported file type.")
                continue

            data = file.read()
            if len(data) > MAX_IMAGE_BYTES:
                flash(f"Skipped {cat['name']}: image too large (max 10MB).")
                continue

            encoded = base64.b64encode(data).decode('utf-8')
            data_uri = f"data:{file.mimetype};base64,{encoded}"

            row = CategoryImage.query.filter_by(slug=cat['slug']).first()
            if row:
                row.image_url = data_uri
            else:
                row = CategoryImage(slug=cat['slug'], image_url=data_uri)
                db.session.add(row)

        db.session.commit()
        flash('Category images updated.')
        return redirect(url_for('admin_category_images'))

    current_images = get_category_images()
    return render_template('admin/category_images.html', categories=SERVICE_CATEGORIES, current_images=current_images)


# ---------- ADMIN: DEAL OF THE DAY ----------

@app.route('/admin/deal', methods=['GET', 'POST'])
@login_required
def admin_deal():
    deal = DealBanner.query.first()
    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        link_url = request.form.get('link_url', '').strip()
        active = True if request.form.get('active') == 'on' else False

        if deal:
            deal.message = message
            deal.link_url = link_url
            deal.active = active
        else:
            deal = DealBanner(message=message, link_url=link_url, active=active)
            db.session.add(deal)
        db.session.commit()
        flash('Deal banner updated.')
        return redirect(url_for('admin_deal'))

    return render_template('admin/deal_form.html', deal=deal)


# ---------- DATABASE SETUP ----------
with app.app_context():
    db.create_all()
    try:
        db.session.execute(text('ALTER TABLE affiliate_link ADD COLUMN IF NOT EXISTS height INTEGER DEFAULT 500'))
        db.session.commit()
    except Exception:
        db.session.rollback()
    try:
        db.session.execute(text('ALTER TABLE affiliate_link ALTER COLUMN placement TYPE TEXT'))
        db.session.commit()
    except Exception:
        db.session.rollback()
    try:
        db.session.execute(text('ALTER TABLE category_image ALTER COLUMN image_url TYPE TEXT'))
        db.session.commit()
    except Exception:
        db.session.rollback()

if __name__ == '__main__':
    app.run(debug=True)
    from services.travelpayouts import fetch_cheap_flights

@app.route('/api/search-flights', methods=['POST'])
def search_flights():
    data = request.get_json() or {}
    
    origin = data.get('origin', '').strip()
    destination = data.get('destination', '').strip()
    depart_date = data.get('depart_date', '').strip()
    return_date = data.get('return_date', '').strip()
    
    if not origin or not destination or not depart_date:
        return jsonify({"success": False, "message": "Missing required fields"}), 400
        
    results = fetch_cheap_flights(origin, destination, depart_date, return_date)
    return jsonify(results)


@app.route('/redirect')
def redirect_bridge():
    partner = request.args.get('partner', 'Verified Partner')
    origin = request.args.get('origin', 'NYC')
    destination = request.args.get('destination', 'PAR')
    price = request.args.get('price', '0')
    
    marker = os.environ.get("TRAVELPAYOUTS_MARKER", "775557")
    
    final_affiliate_url = f"https://wayaway.io/search/{origin}{destination}?marker={marker}&cls=Y"
    
    return render_template(
        'redirect.html', 
        partner=partner, 
        origin=origin, 
        destination=destination, 
        price=price, 
        target_url=final_affiliate_url
    )


@app.route('/api/redirect')
def api_redirect():
    partner = request.args.get('partner', 'Partner')
    origin = request.args.get('origin', '')
    destination = request.args.get('destination', '')
    price = request.args.get('price', '0')
    
    return redirect(f"/redirect?partner={partner}&origin={origin}&destination={destination}&price={price}")