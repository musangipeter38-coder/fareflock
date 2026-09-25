import os
import requests
from datetime import datetime
from flask import Flask, render_template, redirect, request, jsonify
from dotenv import load_dotenv
from database import db, AffiliateLink, ClickLog, WhatsAppTracker

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fareflock-prod-key-2026')

db_url = os.environ.get('DATABASE_URL', 'sqlite:///fareflock.db')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

TRAVELPAYOUTS_TOKEN = os.environ.get('TRAVELPAYOUTS_API_TOKEN', '')
TRAVELPAYOUTS_MARKER = os.environ.get('TRAVELPAYOUTS_MARKER', '775557')

SOCIAL_LINKS = {
    'facebook': os.environ.get('FACEBOOK_URL', 'https://facebook.com/fareflock'),
    'twitter': os.environ.get('TWITTER_URL', 'https://x.com/fareflock'),
    'instagram': os.environ.get('INSTAGRAM_URL', 'https://instagram.com/fareflock')
}

CITY_TO_IATA = {
    'NAIROBI': 'NBO', 'KENYA': 'NBO', 'MOMBASA': 'MBA', 'KISUMU': 'KIS',
    'DUBAI': 'DXB', 'UAE': 'DXB', 'LONDON': 'LHR', 'UK': 'LHR',
    'NEW YORK': 'JFK', 'AMSTERDAM': 'AMS', 'PARIS': 'CDG', 'DOHA': 'DOH'
}

def resolve_iata(input_str):
    cleaned = input_str.strip().upper()
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned
    return CITY_TO_IATA.get(cleaned, cleaned)

@app.context_processor
def inject_globals():
    return dict(SOCIAL_LINKS=SOCIAL_LINKS)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/flights')
def flights():
    return render_template('flights.html')

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
        'limit': 12,
        'show_to_affiliates': 'true',
        'token': TRAVELPAYOUTS_TOKEN
    }

    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        raw_results = data.get('data', []) if (data and data.get('success', False)) else []

        sanitized = []
        for flight in raw_results:
            orig = flight.get('origin')
            dest = flight.get('destination')
            depart = flight.get('depart_date')
            price = flight.get('value')
            gate = flight.get('gate', 'Travelpayouts Partner')
            
            depart_clean = depart.replace('-', '') if depart else ''
            raw_aff_url = f"https://aviasales.com/search/{orig}{depart_clean}{dest}1?marker={TRAVELPAYOUTS_MARKER}"
            
            sanitized.append({
                'origin': orig,
                'destination': dest,
                'depart_date': depart,
                'price': price,
                'currency': currency,
                'gate': gate,
                'transfers': flight.get('number_of_changes', 0),
                'booking_url': f"/api/redirect?target={requests.utils.quote(raw_aff_url)}&partner={requests.utils.quote(gate)}&origin={orig}&dest={dest}"
            })

        return jsonify({'ok': True, 'results': sanitized})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'results': []}), 500

@app.route('/api/redirect')
def api_redirect():
    target_url = request.args.get('target', 'https://fareflock.com')
    origin = request.args.get('origin', 'N/A')
    dest = request.args.get('dest', 'N/A')
    target_url = requests.utils.unquote(target_url)

    try:
        link = AffiliateLink.query.filter_by(content=target_url).first() or AffiliateLink.query.first()
        if link:
            click = ClickLog(affiliate_link_id=link.id, post_slug=f"search_{origin}_{dest}")
            db.session.add(click)
            db.session.commit()
    except Exception:
        db.session.rollback()

    return redirect(target_url, code=302)

@app.route('/api/whatsapp/track', methods=['POST'])
def register_whatsapp():
    phone = request.form.get('phone', '').strip()
    origin = request.form.get('origin', '').strip().upper()
    destination = request.form.get('destination', '').strip().upper()
    
    if phone and origin and destination:
        tracker = WhatsAppTracker(phone_number=phone, origin=origin, destination=destination)
        db.session.add(tracker)
        db.session.commit()
        return jsonify({'ok': True, 'message': 'WhatsApp alert registered!'})
    return jsonify({'ok': False, 'error': 'Missing parameters'}), 400

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)