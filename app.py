import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
import requests

# Initialize App
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fareflock-secret-key-production-2026')

# Database Configuration with PostgreSQL Fix for Render
db_url = os.environ.get('DATABASE_URL', 'sqlite:///fareflock.db')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# -------------------------------------------------------------------
# Travelpayouts API Service Helper
# -------------------------------------------------------------------
TRAVELPAYOUTS_API_TOKEN = os.environ.get("TRAVELPAYOUTS_API_TOKEN", "7d889940cd642d00d92c39e810828c95")
TRAVELPAYOUTS_MARKER = os.environ.get("TRAVELPAYOUTS_MARKER", "775557")

def fetch_cheap_flights(origin, destination, depart_date, return_date=None, currency="USD"):
    url = "https://api.travelpayouts.com/v1/prices/cheap"
    
    headers = {
        "X-Access-Token": TRAVELPAYOUTS_API_TOKEN,
        "Accept-Encoding": "gzip,deflate"
    }
    
    params = {
        "origin": origin.upper(),
        "destination": destination.upper(),
        "depart_date": depart_date,
        "currency": currency.lower()
    }
    
    if return_date:
        params["return_date"] = return_date

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        flights = []
        dest_data = data.get("data", {}).get(destination.upper(), {})
        
        for key, item in dest_data.items():
            flights.append({
                "flight_number": item.get("flight_number"),
                "airline": item.get("airline"),
                "price": item.get("price"),
                "departure_at": item.get("departure_at"),
                "return_at": item.get("return_at"),
                "transfers": item.get("transfers", 0),
                "redirect_url": f"/api/redirect?origin={origin}&destination={destination}&partner={item.get('airline')}&price={item.get('price')}"
            })
            
        return {"success": True, "data": flights}
        
    except requests.RequestException as e:
        return {"success": False, "error": str(e), "data": []}

# -------------------------------------------------------------------
# Database Models
# -------------------------------------------------------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Deal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    origin = db.Column(db.String(10), nullable=False)
    destination = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False, default='Flights')
    affiliate_link = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CategoryImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(50), unique=True, nullable=False)
    image_url = db.Column(db.String(500), nullable=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------------------------------------------------------
# Frontend & Core Routes
# -------------------------------------------------------------------
@app.route('/')
def index():
    featured_deals = Deal.query.order_by(Deal.created_at.desc()).limit(6).all()
    category_images = {c.category_name: c.image_url for c in CategoryImage.query.all()}
    return render_template('index.html', deals=featured_deals, category_images=category_images)

@app.route('/flights')
def flights():
    return render_template('flights.html')

@app.route('/hotels')
def hotels():
    return render_template('hotels.html')

@app.route('/explore')
def explore():
    deals = Deal.query.all()
    return render_template('explore.html', deals=deals)

@app.route('/about')
def about():
    return render_template('about.html')

# -------------------------------------------------------------------
# Travelpayouts Native API & Secure Bridge Endpoints
# -------------------------------------------------------------------
@app.route('/api/search-flights', methods=['POST'])
def search_flights():
    data = request.get_json() or {}
    
    origin = data.get('origin', '').strip()
    destination = data.get('destination', '').strip()
    depart_date = data.get('depart_date', '').strip()
    return_date = data.get('return_date', '').strip()
    
    if not origin or not destination or not depart_date:
        return jsonify({"success": False, "message": "Missing required parameters"}), 400
        
    results = fetch_cheap_flights(origin, destination, depart_date, return_date)
    return jsonify(results)

@app.route('/redirect')
def redirect_bridge():
    partner = request.args.get('partner', 'Verified Partner')
    origin = request.args.get('origin', 'NYC')
    destination = request.args.get('destination', 'PAR')
    price = request.args.get('price', '0')
    
    marker = os.environ.get("TRAVELPAYOUTS_MARKER", TRAVELPAYOUTS_MARKER)
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

# -------------------------------------------------------------------
# Authentication Routes
# -------------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('admin_dashboard'))
        else:
            flash('Login unsuccessful. Please check email and password.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

# -------------------------------------------------------------------
# Admin Panel Routes
# -------------------------------------------------------------------
@app.route('/admin')
@login_required
def admin_dashboard():
    total_deals = Deal.query.count()
    total_messages = Message.query.count()
    return render_template('admin/dashboard.html', total_deals=total_deals, total_messages=total_messages)

@app.route('/admin/category-images', methods=['GET', 'POST'])
@login_required
def admin_category_images():
    if request.method == 'POST':
        category_name = request.form.get('category_name')
        image_url = request.form.get('image_url')
        
        existing = CategoryImage.query.filter_by(category_name=category_name).first()
        if existing:
            existing.image_url = image_url
        else:
            new_cat = CategoryImage(category_name=category_name, image_url=image_url)
            db.session.add(new_cat)
            
        db.session.commit()
        flash('Category image updated successfully!', 'success')
        return redirect(url_for('admin_category_images'))
        
    images = CategoryImage.query.all()
    return render_template('admin/category_images.html', images=images)

# Initialize Database Schema
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)