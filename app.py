import os
import re
import requests
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, abort, Response, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from sqlalchemy import text
from database import db, Admin, Post, Category, AffiliateLink, ClickLog, Tip, ChatMessage, CategoryImage, WhatsAppTracker

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-later')

db_url = os.environ.get('DATABASE_URL', 'sqlite:///fareflock.db')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

db.init_app(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

SITE_URL = os.environ.get('SITE_URL', 'https://fareflock.com')
WHATSAPP_NUMBER = os.environ.get('WHATSAPP_NUMBER', '+14155238886')
TRAVELPAYOUTS_TOKEN = os.environ.get('TRAVELPAYOUTS_TOKEN', '')
TRAVELPAYOUTS_MARKER = os.environ.get('TRAVELPAYOUTS_MARKER', '581331')

# Global Social Links dictionary to avoid Jinja UndefinedError in base.html
SOCIAL_LINKS = {
    'facebook': os.environ.get('FACEBOOK_URL', 'https://facebook.com/fareflock'),
    'twitter': os.environ.get('TWITTER_URL', 'https://x.com/fareflock'),
    'instagram': os.environ.get('INSTAGRAM_URL', 'https://instagram.com/fareflock')
}


@app.context_processor
def inject_global_vars():
    """Inject variables into all Jinja templates globally across all routes."""
    return dict(SOCIAL_LINKS=SOCIAL_LINKS)


CITY_TO_IATA = {
    'NAIROBI': 'NBO',
    'KENYA': 'NBO',
    'MOMBASA': 'MBA',
    'KISUMU': 'KIS',
    'DUBAI': 'DXB',
    'UAE': 'DXB',
    'UNITED KINGDOM': 'LHR',
    'UK': 'LHR',
    'LONDON': 'LHR',
    'LONDON HEATHROW': 'LHR',
    'LONDON GATWICK': 'LGW',
    'NEW YORK': 'JFK',
    'USA': 'JFK',
    'AMSTERDAM': 'AMS',
    'NETHERLANDS': 'AMS',
    'PARIS': 'CDG',
    'FRANCE': 'CDG',
    'DOHA': 'DOH',
    'QATAR': 'DOH',
    'JOHANNESBURG': 'JNB',
    'SOUTH AFRICA': 'JNB',
    'TORONTO': 'YYZ',
    'CANADA': 'YYZ',
    'MUMBAI': 'BOM',
    'INDIA': 'BOM',
    'DELHI': 'DEL',
    'BANGKOK': 'BKK',
    'THAILAND': 'BKK',
    'GUANGZHOU': 'CAN',
    'CHINA': 'CAN',
}

SERVICE_CATEGORIES = [
    {'slug': 'flights', 'name': 'Flights', 'icon': '✈️', 'placement': 'flights_page', 'route': 'flights'},
    {'slug': 'tours', 'name': 'Tours & Activities', 'icon': '🚶', 'placement': 'category_tours', 'route': None},
    {'slug': 'transfers', 'name': 'Transfers & Airport Services', 'icon': '🚕', 'placement': 'category_transfers', 'route': None},
    {'slug': 'car-rentals', 'name': 'Car & Bike Rentals', 'icon': '🚗', 'placement': 'category_car_rentals', 'route': None},
    {'slug': 'other', 'name': 'Other', 'icon': '🔘', 'placement': 'category_other', 'route': None},
    {'slug': 'sim-cards', 'name': 'SIM Cards', 'icon': '📶', 'placement': 'category_sim_cards', 'route': None},
]

BLOG_VISUALS = [
    {'match': 'flight', 'icon': '✈️', 'gradient': 'grad-blue'},
    {'match': 'hotel', 'icon': '🛏️', 'gradient': 'grad-purple'},
    {'match': 'tour', 'icon': '🚶', 'gradient': 'grad-teal'},
    {'match': 'guide', 'icon': '🧭', 'gradient': 'grad-blue'},
    {'match': 'review', 'icon': '⭐', 'gradient': 'grad-pink'},
    {'match': 'visa', 'icon': '🛂', 'gradient': 'grad-teal'},
]


def resolve_iata(input_str):
    cleaned = input_str.strip().upper()
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned
    return CITY_TO_IATA.get(cleaned, cleaned)


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


def get_widgets(placement):
    return AffiliateLink.query.filter_by(
        placement=placement, link_type='widget', active=True
    ).order_by(AffiliateLink.created_at.asc()).all()


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


# ---------- NATIVE TRAVELPAYOUTS API & REDIRECT GATEWAY ----------

@app.route('/api/search/flights', methods=['GET'])
def search_flights():
    raw_origin = request.args.get('origin', 'NBO')
    raw_destination = request.args.get('destination', 'DXB')
    currency = request.args.get('currency', 'USD').upper().strip()

    origin = resolve_iata(raw_origin)
    destination = resolve_iata(raw_destination)

    url = "https://api.travelpayouts.com/v2/prices/latest"
    params = {
        'origin': origin,
        'destination': destination,
        'currency': currency,
        'period_type': 'year',
        'page': 1,
        'limit': 10,
        'show_to_affiliates': 'true',
        'token': TRAVELPAYOUTS_TOKEN
    }

    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        
        raw_results = data.get('data', []) if data.get('success', False) else []
        
        if not raw_results:
            fallback_params = {
                'origin': origin,
                'currency': currency,
                'period_type': 'year',
                'page': 1,
                'limit': 10,
                'show_to_affiliates': 'true',
                'token': TRAVELPAYOUTS_TOKEN
            }
            res = requests.get(url, params=fallback_params, timeout=10)
            data = res.json()
            raw_results = data.get('data', []) if data.get('success', False) else []

        sanitized = []
        for flight in raw_results:
            orig = flight.get('origin')
            dest = flight.get('destination')
            depart = flight.get('depart_date')
            price = flight.get('value')
            gate = flight.get('gate', 'Travelpayouts Partner')
            raw_aff_url = f"https://aviasales.com/search/{orig}{depart}{dest}1?marker={TRAVELPAYOUTS_MARKER}"
            
            sanitized.append({
                'origin': orig,
                'destination': dest,
                'depart_date': depart,
                'return_date': flight.get('return_date', ''),
                'price': price,
                'currency': currency,
                'gate': gate,
                'transfers': flight.get('number_of_changes', 0),
                'booking_url': f"/api/redirect?target={requests.utils.quote(raw_aff_url)}&partner={requests.utils.quote(gate)}&origin={orig}&dest={dest}"
            })

        return jsonify({'ok': True, 'resolved_origin': origin, 'resolved_destination': destination, 'results': sanitized})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'results': []}), 500


@app.route('/api/redirect')
def api_redirect():
    target_url = request.args.get('target', 'https://fareflock.com')
    partner = request.args.get('partner', 'Verified Partner')
    origin = request.args.get('origin', 'N/A')
    dest = request.args.get('dest', 'N/A')

    link = AffiliateLink.query.filter_by(content=target_url).first()
    link_id = link.id if link else 0

    click = ClickLog(affiliate_link_id=link_id if link_id > 0 else 1, post_slug=f"search_{origin}_{dest}")
    db.session.add(click)
    db.session.commit()

    return redirect(target_url, code=302)


# ---------- WHATSAPP TRACKER ENGINE ----------

@app.route('/api/whatsapp/track', methods=['POST'])
def register_whatsapp_tracker():
    phone = request.form.get('phone', '').strip()
    origin = request.form.get('origin', '').strip().upper()
    destination = request.form.get('destination', '').strip().upper()
    target_price = request.form.get('target_price', 0, type=float)

    if not phone or not origin or not destination:
        return jsonify({'ok': False, 'error': 'Missing required flight parameters.'}), 400

    tracker = WhatsAppTracker(
        phone_number=phone,
        origin=origin,
        destination=destination,
        target_price=target_price
    )
    db.session.add(tracker)
    db.session.commit()

    return jsonify({
        'ok': True,
        'message': f'Tracking enabled for {origin} -> {destination}. Notifications will be sent to {phone} via WhatsApp.'
    })


@app.route('/api/whatsapp/webhook', methods=['POST'])
def whatsapp_webhook():
    incoming_msg = request.values.get('Body', '').lower().strip()
    from_number = request.values.get('From', '')

    response_text = "Welcome to Fareflock Concierge ✈️\n\nReply with your target route to start tracking (e.g., 'TRACK NBO DXB 500')."

    if 'track' in incoming_msg:
        parts = incoming_msg.split()
        if len(parts) >= 3:
            orig = parts[1].upper()
            dest = parts[2].upper()
            price = float(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0.0

            tracker = WhatsAppTracker(
                phone_number=from_number,
                origin=orig,
                destination=dest,
                target_price=price
            )
            db.session.add(tracker)
            db.session.commit()

            response_text = f"✅ Fareflock Price Watch Active!\nRoute: {orig} ✈️ {dest}\nWe'll text you on WhatsApp the second prices drop."

    xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Message>{response_text}</Message>
    </Response>"""
    return Response(xml_response, mimetype='text/xml')


# ---------- PUBLIC ROUTES ----------

@app.route('/')
def home():
    widgets = get_widgets('homepage')
    cat_images = get_category_images()
    return render_template(
        'index.html', widgets=widgets, cat_images=cat_images,
        meta_title='Fareflock — Premium Concierge & Deal Finder',
        meta_description='Flights, hotels, tours, insurance — real-time verified pricing cross-checked across 1,000+ providers.'
    )


@app.route('/flights')
def flights():
    widgets = get_widgets('flights_page')
    tips = get_tips('flights')
    return render_template(
        'flights.html', widgets=widgets, tips=tips,
        meta_title='Find Verified Cheap Flights — Fareflock',
        meta_description='Search real-time flight deals and track price drops instantly via Fareflock WhatsApp Concierge.'
    )


@app.route('/hotels')
def hotels():
    widgets = get_widgets('hotels_page')
    tips = get_tips('hotels')
    return render_template(
        'hotels.html', widgets=widgets, tips=tips,
        meta_title='Find Hotels — Fareflock',
        meta_description='Curated stays with 256-bit secure gateway links to official hotel providers.'
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

@app.route('/admin/category-images', methods=['GET', 'POST'])
@login_required
def admin_category_images():
    if request.method == 'POST':
        for cat in SERVICE_CATEGORIES:
            url_value = request.form.get(cat['slug'], '').strip()
            row = CategoryImage.query.filter_by(slug=cat['slug']).first()
            if row:
                row.image_url = url_value
            else:
                row = CategoryImage(slug=cat['slug'], image_url=url_value)
                db.session.add(row)
        db.session.commit()
        flash('Category images updated.')
        return redirect(url_for('admin_category_images'))

    current_images = get_category_images()
    return render_template('admin/category_images.html', categories=SERVICE_CATEGORIES, current_images=current_images)


# ---------- DATABASE SETUP ----------
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)