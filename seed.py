from app import app, bcrypt
from database import db, Admin, Category, Post

with app.app_context():
    db.create_all()

    admin = Admin.query.first()
    hashed_pw = bcrypt.generate_password_hash('Dallo@254').decode('utf-8')

    if admin:
        admin.username = 'PETER'
        admin.password_hash = hashed_pw
        print("Admin credentials updated.")
    else:
        admin = Admin(username='PETER', password_hash=hashed_pw)
        db.session.add(admin)
        print("Admin account created.")

    if not Category.query.filter_by(slug='guides').first():
        cat = Category(name='Travel Guides', slug='guides')
        db.session.add(cat)
        db.session.commit()

        sample_post = Post(
            title='Welcome to Fareflock',
            slug='welcome-to-fareflock',
            body="<p>Fareflock is a global travel deals and guides site. Real cost breakdowns, honest reviews, and specific advice — starting now.</p>",
            meta_description='An introduction to Fareflock and what to expect.',
            category_id=cat.id,
            published=True
        )
        db.session.add(sample_post)

    db.session.commit()
    print("Seeding complete.")