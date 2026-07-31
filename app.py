from flask import jsonify
from flask import Flask, render_template, request, redirect, session, url_for
import mysql.connector
import os
import uuid
import re
from werkzeug.utils import secure_filename
import pandas as pd
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from recommendation import get_recommendations, build_fitur_cbf
from authlib.integrations.flask_client import OAuth
from urllib.parse import quote
from dotenv import load_dotenv
import os
load_dotenv()

app = Flask(__name__)
app.secret_key = "coffee_secret"
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/coffeeshop_project'
# production
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:root123@mysql-aset:3306/coffeeshop_project'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Konfigurasi upload gambar menu
app.config['UPLOAD_FOLDER_MENU'] = 'static/images/menu'
app.config['UPLOAD_FOLDER_CAFE'] = 'static/images/coffeeshops'
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 MB per request
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
db = SQLAlchemy(app)

# ==========================
# GOOGLE OAUTH CONFIG
# ==========================
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# ==========================
# MODEL
# ==========================

class CoffeeShop(db.Model):
    __tablename__ = 'coffeeshops'
    id            = db.Column(db.Integer, primary_key=True)
    nama          = db.Column(db.String(255))
    rating        = db.Column(db.Float)
    alamat        = db.Column(db.Text)
    fasilitas     = db.Column(db.Text)
    area          = db.Column(db.String(255))
    fitur_cbf     = db.Column(db.Text)
    maps_link     = db.Column(db.Text)
    instagram     = db.Column(db.Text)
    website       = db.Column(db.Text)
    kisaran_harga = db.Column(db.String(100))
    image_url     = db.Column(db.Text)

class User(db.Model):
    __tablename__ = 'users'
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    email    = db.Column(db.String(100))
    password = db.Column(db.String(255), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    profile_picture = db.Column(db.String(255), nullable=True)

class Bookmark(db.Model):
    __tablename__ = 'bookmarks'
    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('users.id'))
    coffee_id = db.Column(db.Integer, db.ForeignKey('coffeeshops.id'))

class MenuImage(db.Model):
    __tablename__ = 'menu_images'
    id          = db.Column(db.Integer, primary_key=True)
    coffee_id   = db.Column(db.Integer, db.ForeignKey('coffeeshops.id'))
    filename    = db.Column(db.String(255))
    uploaded_at = db.Column(db.DateTime)

# ==========================
# HELPER
# ==========================

def has_own_website(website_value):
    if not website_value:
        return False
    return website_value.strip() != ''

def is_admin():
    if 'user_id' not in session:
        return False
    user = User.query.get(session['user_id'])
    return user is not None and user.is_admin

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==========================
# HELPER: VALIDASI PASSWORD
# ==========================

def is_strong_password(password):
    has_length = len(password) >= 8
    has_upper  = bool(re.search(r'[A-Z]', password))
    has_lower  = bool(re.search(r'[a-z]', password))
    has_number = bool(re.search(r'[0-9]', password))
    has_symbol = bool(re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\/~`;]', password))

    if has_length and has_upper and has_lower and has_number and has_symbol:
        return True, ""

    return False, "Password minimal 8 karakter dan mengandung huruf besar, huruf kecil, angka, dan simbol."

# ==========================
# HOME
# ==========================

@app.route('/')
def home():
    coffees = CoffeeShop.query.all()
    area_dict = {}
    for coffee in coffees:
        if coffee.area not in area_dict:
            area_dict[coffee.area] = coffee
        else:
            if coffee.rating > area_dict[coffee.area].rating:
                area_dict[coffee.area] = coffee

    top_area_coffee = sorted(
        list(area_dict.values()),
        key=lambda x: x.rating,
        reverse=True
    )[:5]

    bookmarked_ids = []
    if 'user_id' in session:
        bookmarks = Bookmark.query.filter_by(user_id=session['user_id']).all()
        bookmarked_ids = [b.coffee_id for b in bookmarks]

    login_error = request.args.get('login_error')
    reg_error   = request.args.get('reg_error')
    success     = request.args.get('success')

    return render_template(
        'index.html',
        coffeeshops=top_area_coffee,
        all_coffeeshops=coffees,
        bookmarked_ids=bookmarked_ids,
        login_error=login_error,
        reg_error=reg_error,
        success=success,
        is_admin=is_admin()
    )

# ==========================
# REKOMENDASI
# ==========================

@app.route('/rekomendasi', methods=['GET', 'POST'])
def rekomendasi():
    if 'user_id' not in session:
        return redirect('/?login_error=Silakan+login+terlebih+dahulu#modalLogin')

    hasil_rekomendasi = None

    if request.method == 'POST':
        rating    = request.form.get('rating', '')
        area      = request.form.get('area', 'Semua')
        harga     = request.form.get('harga', '')
        fasilitas = request.form.getlist('fasilitas')
        fasilitas_text = " ".join(fasilitas)

        hasil_rekomendasi = get_recommendations(rating, area, harga, fasilitas_text)

    bookmarked_ids = []
    if 'user_id' in session:
        bookmarks = Bookmark.query.filter_by(user_id=session['user_id']).all()
        bookmarked_ids = [b.coffee_id for b in bookmarks]

    return render_template('rekomendasi.html',
        hasil_rekomendasi=hasil_rekomendasi,
        bookmarked_ids=bookmarked_ids,
        is_admin=is_admin()
    )
# ==========================
# MAPPING LABEL FORM → KEY FASILITAS_TOKEN
# ==========================
FASILITAS_LABEL_TO_KEY = {
    'WiFi':         'wifi',
    'Indoor/AC':    'ac',
    'Outdoor':      'outdoor',
    'Semi-Outdoor': 'semi_outdoor',
    'Mushola':      'mushola',
    'Live Music':   'live_music',
}

def _map_fasilitas_to_keys(fasilitas_list):
    keys = []
    for label in fasilitas_list:
        key = FASILITAS_LABEL_TO_KEY.get(label)
        if key:
            keys.append(key)
        else:
            fallback = label.strip().lower().replace(' ', '_').replace('/', '_')
            keys.append(fallback)
            print(f"[WARNING] Label fasilitas '{label}' tidak ada di FASILITAS_LABEL_TO_KEY. "
                  f"Dipakai fallback '{fallback}'.")
    return keys

# =========================
# DAFTAR COFFEESHOP
# =========================

@app.route('/daftar-coffeeshop')
def daftar_coffeeshop():
    if 'user_id' not in session:
        return redirect('/?login_error=Silakan+login+terlebih+dahulu#modalLogin')

    area     = request.args.get('area', 'Semua')
    sort     = request.args.get('sort', 'rating')
    q        = request.args.get('q', '').strip()
    page     = request.args.get('page', 1, type=int)
    per_page = 12
    query    = CoffeeShop.query

    if area != 'Semua':
        query = query.filter(CoffeeShop.area == area)
    if q:
        query = query.filter(CoffeeShop.nama.ilike(f'%{q}%'))
    if sort == 'rating':
        query = query.order_by(CoffeeShop.rating.desc())
    elif sort == 'nama':
        query = query.order_by(CoffeeShop.nama.asc())

    total        = query.count()
    coffeeshops  = query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages  = (total + per_page - 1) // per_page

    bookmarked_ids = []
    if 'user_id' in session:
        bookmarks = Bookmark.query.filter_by(user_id=session['user_id']).all()
        bookmarked_ids = [b.coffee_id for b in bookmarks]

    return render_template(
        'daftar_coffeeshop.html',
        coffeeshops=coffeeshops,
        bookmarked_ids=bookmarked_ids,
        current_area=area,
        current_sort=sort,
        current_q=q,
        current_page=page,
        total_pages=total_pages,
        total=total,
        is_admin=is_admin()
    )

# ==========================
# REGISTER
# ==========================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email    = request.form['email'].strip()
        password_raw = request.form['password']

        valid, msg = is_strong_password(password_raw)
        if not valid:
            return redirect(f'/?reg_error={quote(msg)}#modalRegister')

        password = generate_password_hash(password_raw)

        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            return redirect('/?reg_error=Email+sudah+terdaftar#modalRegister')

        existing_username = User.query.filter_by(username=username).first()
        if existing_username:
            return redirect('/?reg_error=Username+sudah+digunakan#modalRegister')

        user = User(username=username, email=email, password=password)
        db.session.add(user)
        db.session.commit()
        return redirect('/?success=Registrasi+berhasil,+silakan+login#modalLogin')

    return redirect('/')

# ==========================
# LOGIN (EMAIL ATAU USERNAME)
# ==========================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password   = request.form.get('password', '')

        if not identifier or not password:
            return redirect('/?login_error=Email/Username+dan+password+wajib+diisi#modalLogin')

        if '@' in identifier:
            user = User.query.filter_by(email=identifier).first()
        else:
            user = User.query.filter_by(username=identifier).first()

        if user and user.password and check_password_hash(user.password, password):
            session['user_id']  = user.id
            session['username'] = user.username
            return redirect('/')

        return redirect('/?login_error=Email/Username+atau+password+salah#modalLogin')

    return redirect('/')

# ==========================
# LOGIN GOOGLE
# ==========================

@app.route('/login/google')
def login_google():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/login/google/callback')
def google_callback():
    token     = google.authorize_access_token()
    user_info = token.get('userinfo')

    if not user_info:
        return redirect('/login')

    email = user_info['email']
    name  = user_info.get('name', email.split('@')[0])

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(username=name, email=email, password=None)
        db.session.add(user)
        db.session.commit()

    session['user_id']  = user.id
    session['username'] = user.username
    return redirect('/')

# ==========================
# LOGOUT
# ==========================

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ==========================
# BOOKMARK
# ==========================

@app.route('/bookmark/ajax/<int:coffee_id>', methods=['POST'])
def bookmark_ajax(coffee_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error'}), 401
    user_id  = session['user_id']
    existing = Bookmark.query.filter_by(user_id=user_id, coffee_id=coffee_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'status': 'removed'})
    else:
        new_bookmark = Bookmark(user_id=user_id, coffee_id=coffee_id)
        db.session.add(new_bookmark)
        db.session.commit()
        return jsonify({'status': 'added'}
    )

@app.route('/my-bookmark')
def my_bookmark():
    if 'user_id' not in session:
        return redirect('/login')
    user_id    = session['user_id']
    bookmarks  = Bookmark.query.filter_by(user_id=user_id).all()
    coffee_ids = [bookmark.coffee_id for bookmark in bookmarks]
    coffeeshops = CoffeeShop.query.filter(CoffeeShop.id.in_(coffee_ids)).all()
    return render_template(
    'bookmark.html',
    coffeeshops=coffeeshops,
    is_admin=is_admin()
    )

# ==========================
# DETAIL / PROFIL CAFE
# ==========================

@app.route('/coffee/<int:coffee_id>')
def coffee_detail(coffee_id):
    coffee = CoffeeShop.query.get_or_404(coffee_id)

    if has_own_website(coffee.website):
        return redirect(coffee.website)

    is_bookmarked = False
    if 'user_id' in session:
        existing = Bookmark.query.filter_by(
            user_id=session['user_id'], coffee_id=coffee_id
        ).first()
        is_bookmarked = existing is not None

    menu_images = MenuImage.query.filter_by(coffee_id=coffee_id)\
        .order_by(MenuImage.uploaded_at.asc()).all()

    return render_template(
        'detail.html',
        coffee=coffee,
        is_bookmarked=is_bookmarked,
        menu_images=menu_images,
        is_admin=is_admin()
    )

# ==========================
# SET PASSWORD
# ==========================

@app.route('/set-password', methods=['GET', 'POST'])
def set_password():
    if 'user_id' not in session:
        return redirect('/?login_error=Silakan+login+terlebih+dahulu#modalLogin')

    user = User.query.get(session['user_id'])

    # Kalau sudah punya password, tidak perlu set lagi
    if user.password is not None:
        return redirect('/')

    error = None
    sukses = None

    if request.method == 'POST':
        password_raw = request.form.get('password', '')
        konfirmasi   = request.form.get('konfirmasi', '')

        if password_raw != konfirmasi:
            error = "Password dan konfirmasi tidak cocok."
        else:
            valid, msg = is_strong_password(password_raw)
            if not valid:
                error = msg
            else:
                user.password = generate_password_hash(password_raw)
                db.session.commit()
                sukses = "Password berhasil ditambahkan! Sekarang kamu bisa login manual."

    return render_template('set_password.html', error=error, sukses=sukses, user=user)

# ==========================
# ADMIN
# ==========================

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect('/?login_error=Silakan+login+terlebih+dahulu#modalLogin')
    if not is_admin():
        return "Akses ditolak: hanya admin yang bisa mengakses halaman ini.", 403

    coffeeshops = CoffeeShop.query.order_by(CoffeeShop.nama.asc()).all()
    total_cafe  = len(coffeeshops)
    total_user  = User.query.count()

    return render_template(
        'admin_dashboard.html',
        coffeeshops=coffeeshops,
        total_cafe=total_cafe,
        total_user=total_user
    )

# ==========================
# KELOLA MENU
# ==========================

@app.route('/admin/cafe/<int:coffee_id>/menu')
def admin_kelola_menu(coffee_id):
    if 'user_id' not in session:
        return redirect('/?login_error=Silakan+login+terlebih+dahulu#modalLogin')
    if not is_admin():
        return "Akses ditolak: hanya admin yang bisa mengakses halaman ini.", 403

    coffee = CoffeeShop.query.get_or_404(coffee_id)
    menu_images = MenuImage.query.filter_by(coffee_id=coffee_id).order_by(MenuImage.uploaded_at.desc()).all()

    return render_template(
        'kelola_menu.html',
        coffee=coffee,
        menu_images=menu_images
    )

# ==========================
# UPLOAD GAMBAR
# ==========================

@app.route('/admin/cafe/<int:coffee_id>/menu/upload', methods=['POST'])
def admin_upload_menu(coffee_id):
    if 'user_id' not in session:
        return redirect('/?login_error=Silakan+login+terlebih+dahulu#modalLogin')
    if not is_admin():
        return "Akses ditolak: hanya admin yang bisa mengakses halaman ini.", 403

    coffee = CoffeeShop.query.get_or_404(coffee_id)
    files = request.files.getlist('menu_photos')

    if not files or files[0].filename == '':
        return redirect(f'/admin/cafe/{coffee_id}/menu')

    upload_folder = app.config['UPLOAD_FOLDER_MENU']
    os.makedirs(upload_folder, exist_ok=True)

    MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB per file

    berhasil = 0
    gagal    = 0

    for file in files:
        if not (file and allowed_file(file.filename)):
            gagal += 1
            continue

        # --- cek ukuran file ---
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # reset pointer supaya file.save() tidak kosong

        if file_size > MAX_FILE_SIZE:
            gagal += 1
            continue

        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_name = f"{coffee_id}_{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(upload_folder, secure_filename(unique_name))

        file.save(filepath)

        new_image = MenuImage(
            coffee_id=coffee_id,
            filename=secure_filename(unique_name),
            uploaded_at=db.func.now()
        )
        db.session.add(new_image)
        berhasil += 1

    db.session.commit()

    return redirect(f'/admin/cafe/{coffee_id}/menu?berhasil={berhasil}&gagal={gagal}')

# ==========================
# HAPUS GAMBAR MENU
# ==========================

@app.route('/admin/menu/<int:image_id>/hapus', methods=['POST'])
def admin_hapus_menu(image_id):
    if 'user_id' not in session:
        return redirect('/?login_error=Silakan+login+terlebih+dahulu#modalLogin')
    if not is_admin():
        return "Akses ditolak: hanya admin yang bisa mengakses halaman ini.", 403

    image = MenuImage.query.get_or_404(image_id)
    coffee_id = image.coffee_id

    filepath = os.path.join(app.config['UPLOAD_FOLDER_MENU'], image.filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    db.session.delete(image)
    db.session.commit()

    return redirect(f'/admin/cafe/{coffee_id}/menu')

# ==========================
# TAMBAH CAFE
# ==========================

@app.route('/admin/cafe/tambah', methods=['GET', 'POST'])
def admin_tambah_cafe():
    if 'user_id' not in session:
        return redirect('/?login_error=Silakan+login+terlebih+dahulu#modalLogin')
    if not is_admin():
        return "Akses ditolak: hanya admin yang bisa mengakses halaman ini.", 403

    if request.method == 'POST':
        nama          = request.form.get('nama', '').strip()
        area          = request.form.get('area', '').strip()
        alamat        = request.form.get('alamat', '').strip()
        rating        = request.form.get('rating', '').strip()
        fasilitas_list = request.form.getlist('fasilitas')
        fasilitas      = ', '.join(fasilitas_list)
        fasilitas_keys = _map_fasilitas_to_keys(fasilitas_list)
        kisaran_harga = request.form.get('kisaran_harga', '').strip()
        maps_link     = request.form.get('maps_link', '').strip()
        instagram     = request.form.get('instagram', '').strip()
        website       = request.form.get('website', '').strip()
        foto          = request.files.get('foto')

        if not all([nama, area, alamat, rating, fasilitas, kisaran_harga, maps_link, instagram, website]):
            return render_template('tambah_cafe.html', error="Semua field wajib diisi.")

        if not foto or foto.filename == '':
            return render_template('tambah_cafe.html', error="Foto cafe wajib diupload.")

        if not allowed_file(foto.filename):
            return render_template('tambah_cafe.html', error="Format foto harus JPG/PNG.")

        try:
            rating_val = float(rating)
        except ValueError:
            return render_template('tambah_cafe.html', error="Rating harus berupa angka.")

        upload_folder = app.config['UPLOAD_FOLDER_CAFE']
        os.makedirs(upload_folder, exist_ok=True)
        ext = foto.filename.rsplit('.', 1)[1].lower()
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(upload_folder, secure_filename(unique_name))
        foto.save(filepath)
        image_url = f"/static/images/coffeeshops/{secure_filename(unique_name)}"

        new_cafe = CoffeeShop(
            nama=nama,
            area=area,
            alamat=alamat,
            rating=rating_val,
            fasilitas=fasilitas,
            kisaran_harga=kisaran_harga,
            maps_link=maps_link,
            instagram=instagram,
            website=website if website.lower() != 'tidak ada' else None,
            image_url=image_url,
            fitur_cbf=build_fitur_cbf(rating_val, kisaran_harga, area, fasilitas_keys)
        )
        db.session.add(new_cafe)
        db.session.commit()

        return redirect('/admin?tambah=sukses')

    return render_template('tambah_cafe.html')

# ==========================
# EDIT CAFE
# ==========================

@app.route('/admin/cafe/<int:coffee_id>/edit', methods=['GET', 'POST'])
def admin_edit_cafe(coffee_id):
    if 'user_id' not in session:
        return redirect('/?login_error=Silakan+login+terlebih+dahulu#modalLogin')
    if not is_admin():
        return "Akses ditolak: hanya admin yang bisa mengakses halaman ini.", 403

    coffee = CoffeeShop.query.get_or_404(coffee_id)

    if request.method == 'POST':
        nama          = request.form.get('nama', '').strip()
        area          = request.form.get('area', '').strip()
        alamat        = request.form.get('alamat', '').strip()
        rating         = request.form.get('rating', '').strip()
        kisaran_harga  = request.form.get('kisaran_harga', '').strip()
        maps_link      = request.form.get('maps_link', '').strip()
        instagram      = request.form.get('instagram', '').strip()
        website        = request.form.get('website', '').strip()
        fasilitas_list = request.form.getlist('fasilitas')
        fasilitas      = ', '.join(fasilitas_list)
        fasilitas_keys = _map_fasilitas_to_keys(fasilitas_list)
        foto           = request.files.get('foto')

        if not all([nama, area, alamat, rating, fasilitas, kisaran_harga, maps_link, instagram, website]):
            return render_template('edit_cafe.html', coffee=coffee, error="Semua field wajib diisi.")

        try:
            rating_val = float(rating)
        except ValueError:
            return render_template('edit_cafe.html', coffee=coffee, error="Rating harus berupa angka.")

        if foto and foto.filename != '':
            if not allowed_file(foto.filename):
                return render_template('edit_cafe.html', coffee=coffee, error="Format foto harus JPG/PNG.")

            upload_folder = app.config['UPLOAD_FOLDER_CAFE']
            os.makedirs(upload_folder, exist_ok=True)
            ext = foto.filename.rsplit('.', 1)[1].lower()
            unique_name = f"{uuid.uuid4().hex}.{ext}"
            filepath = os.path.join(upload_folder, secure_filename(unique_name))
            foto.save(filepath)

            if coffee.image_url and coffee.image_url.startswith('/static/images/coffeeshops/'):
                old_path = coffee.image_url.lstrip('/')
                if os.path.exists(old_path):
                    os.remove(old_path)

            coffee.image_url = f"/static/images/coffeeshops/{secure_filename(unique_name)}"

        coffee.nama          = nama
        coffee.area          = area
        coffee.alamat        = alamat
        coffee.rating        = rating_val
        coffee.fasilitas     = fasilitas
        coffee.kisaran_harga = kisaran_harga
        coffee.maps_link     = maps_link
        coffee.instagram     = instagram
        coffee.website       = website if website.lower() != 'tidak ada' else None
        coffee.fitur_cbf     = build_fitur_cbf(rating_val, kisaran_harga, area, fasilitas_keys)

        db.session.commit()

        return redirect('/admin?edit=sukses')

    return render_template('edit_cafe.html', coffee=coffee)

# ==========================
# HAPUS CAFE
# ==========================

@app.route('/admin/cafe/<int:coffee_id>/hapus', methods=['POST'])
def admin_hapus_cafe(coffee_id):
    if 'user_id' not in session:
        return redirect('/?login_error=Silakan+login+terlebih+dahulu#modalLogin')
    if not is_admin():
        return "Akses ditolak: hanya admin yang bisa mengakses halaman ini.", 403

    coffee = CoffeeShop.query.get_or_404(coffee_id)

    # Hapus bookmark yang terkait dengan cafe ini
    Bookmark.query.filter_by(coffee_id=coffee_id).delete()

    # Hapus semua foto menu (file fisik + record)
    menu_images = MenuImage.query.filter_by(coffee_id=coffee_id).all()
    for img in menu_images:
        filepath = os.path.join(app.config['UPLOAD_FOLDER_MENU'], img.filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    MenuImage.query.filter_by(coffee_id=coffee_id).delete()

    # Hapus foto utama cafe
    if coffee.image_url and coffee.image_url.startswith('/static/images/coffeeshops/'):
        old_path = coffee.image_url.lstrip('/')
        if os.path.exists(old_path):
            os.remove(old_path)

    db.session.delete(coffee)
    db.session.commit()

    return redirect('/admin?hapus=sukses')
    
# ==========================
# KELOLA USER
# ==========================

@app.route('/admin/users')
def admin_kelola_user():
    if 'user_id' not in session:
        return redirect('/?login_error=Silakan+login+terlebih+dahulu#modalLogin')
    if not is_admin():
        return "Akses ditolak: hanya admin yang bisa mengakses halaman ini.", 403

    users = User.query.order_by(User.username.asc()).all()
    return render_template('kelola_user.html', users=users, current_user_id=session['user_id'])

# ==========================
# HAPUS USER
# ==========================

@app.route('/admin/users/<int:user_id>/hapus', methods=['POST'])
def admin_hapus_user(user_id):
    if 'user_id' not in session:
        return redirect('/?login_error=Silakan+login+terlebih+dahulu#modalLogin')
    if not is_admin():
        return "Akses ditolak: hanya admin yang bisa mengakses halaman ini.", 403

    if user_id == session['user_id']:
        return redirect('/admin/users?error=Tidak+bisa+menghapus+akun+sendiri')

    target_user = User.query.get_or_404(user_id)

    Bookmark.query.filter_by(user_id=user_id).delete()

    db.session.delete(target_user)
    db.session.commit()

    return redirect('/admin/users')

# ==========================
# TOGGLE ADMIN
# ==========================

@app.route('/admin/users/<int:user_id>/toggle-admin', methods=['POST'])
def admin_toggle_admin(user_id):
    if 'user_id' not in session:
        return redirect('/?login_error=Silakan+login+terlebih+dahulu#modalLogin')
    if not is_admin():
        return "Akses ditolak: hanya admin yang bisa mengakses halaman ini.", 403

    # Tidak boleh mengubah status admin diri sendiri
    if user_id == session['user_id']:
        return redirect('/admin/users?error=Tidak+bisa+mengubah+status+admin+diri+sendiri')

    target_user = User.query.get_or_404(user_id)
    target_user.is_admin = not target_user.is_admin
    db.session.commit()

    return redirect('/admin/users')

# ==========================
# PROFIL ADMIN
# ==========================

@app.route('/admin/profil', methods=['GET', 'POST'])
def admin_profil():
    if 'user_id' not in session:
        return redirect('/?login_error=Silakan+login+terlebih+dahulu#modalLogin')
    if not is_admin():
        return "Akses ditolak: hanya admin yang bisa mengakses halaman ini.", 403

    admin = User.query.get_or_404(session['user_id'])
    error = None
    sukses = None

    if request.method == 'POST':
        pesan_sukses = []

        username_baru = request.form.get('username', '').strip()
        if username_baru and username_baru != admin.username:
            if User.query.filter(User.username == username_baru, User.id != admin.id).first():
                error = "Username sudah digunakan."
            else:
                admin.username = username_baru
                session['username'] = username_baru
                pesan_sukses.append("username")

        if not error and admin.password is not None:
            pw_lama  = request.form.get('pw_lama', '')
            pw_baru  = request.form.get('pw_baru', '')
            pw_ulang = request.form.get('pw_ulang', '')
            if pw_lama or pw_baru or pw_ulang:
                if not check_password_hash(admin.password, pw_lama):
                    error = "Password lama tidak sesuai."
                else:
                    valid, msg = is_strong_password(pw_baru)
                    if not valid:
                        error = msg
                    elif pw_baru != pw_ulang:
                        error = "Konfirmasi password tidak cocok."
                    else:
                        admin.password = generate_password_hash(pw_baru)
                        pesan_sukses.append("password")

        if not error:
                    foto = request.files.get('foto_profil')
                    if foto and foto.filename != '':
                        if not allowed_file(foto.filename):
                            error = "Format foto harus JPG/PNG."
                        else:
                            # --- cek ukuran file ---
                            foto.seek(0, os.SEEK_END)
                            foto_size = foto.tell()
                            foto.seek(0)  # reset pointer

                            MAX_FOTO_SIZE = 2 * 1024 * 1024  # 2MB

                            if foto_size > MAX_FOTO_SIZE:
                                error = "Ukuran foto maksimal 2MB."
                            else:
                                upload_folder = 'static/images/profil'
                                os.makedirs(upload_folder, exist_ok=True)
                                ext = foto.filename.rsplit('.', 1)[1].lower()
                                unique_name = f"admin_{admin.id}_{uuid.uuid4().hex[:8]}.{ext}"
                                filepath = os.path.join(upload_folder, secure_filename(unique_name))
                                foto.save(filepath)

                                if admin.profile_picture and admin.profile_picture.startswith('/static/images/profil/'):
                                    old_path = admin.profile_picture.lstrip('/')
                                    if os.path.exists(old_path):
                                        os.remove(old_path)

                                admin.profile_picture = f"/static/images/profil/{secure_filename(unique_name)}"
                                pesan_sukses.append("foto profil")

        if not error:
            if pesan_sukses:
                db.session.commit()
                sukses = "Berhasil memperbarui " + ", ".join(pesan_sukses) + "."
            else:
                sukses = "Tidak ada perubahan untuk disimpan."
        else:
            db.session.rollback()

    return render_template('profil_admin.html', admin=admin, error=error, sukses=sukses)

# if __name__ == '__main__':
#     app.run(debug=True, use_reloader=False)
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )