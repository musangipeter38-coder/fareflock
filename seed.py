from app import app, bcrypt
from database import db, Admin, Category, Post

with app.app_context():
    db.create_all()

    if not Admin.query.filter_by(username='peter').first():
        hashed_pw = bcrypt.generate_password_hash('changeme123').decode('utf-8')
        admin = Admin(username='peter', password_hash=hashed_pw)
        db.session.add(admin)
        print("Admin account created: username='peter', password='changeme123'")

    if not Category.query.filter_by(slug='guides').first():
        cat = Category(name='Travel Guides', slug='guides')
        db.session.add(cat)
        db.session.commit()

        sample_post = Post(
            title='Welcome to Fareflock',
            slug='welcome-to-fareflock',
            body="<p>Fareflock is East Africa's honest guide to flights, hotels, and smarter travel. Real cost breakdowns in KES, visa guidance, and route-specific tips — starting now.</p>",
            meta_description='An introduction to Fareflock and what to expect.',
            category_id=cat.id,
            published=True
        )
        db.session.add(sample_post)

    db.session.commit()
    print("Seeding complete.")