import os
import json
from datetime import datetime, date, timezone, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Client, Plan, ClientStat, System

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'smartpost-hub-secret-key-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///hub.db')
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def init_app():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', email='admin@smartpost.com', role='superadmin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
        if not Plan.query.first():
            for p in [
                {'name': 'Básico', 'price': 10, 'max_users': 3, 'max_products': 200, 'features': 'POS, inventario, escáner QR'},
                {'name': 'Profesional', 'price': 25, 'max_users': 10, 'max_products': 1000, 'features': 'Todo Básico + múltiples sucursales, backups, reportes'},
                {'name': 'Empresarial', 'price': 50, 'max_users': 0, 'max_products': 0, 'features': 'Todo ilimitado + soporte prioritario, API'},
            ]:
                db.session.add(Plan(**p))
            db.session.commit()
        if not System.query.first():
            for s in [
                {'name': 'SmartPost POS', 'tagline': 'Sistema de ventas inteligente', 'description': 'Punto de venta completo con inventario, MP, membresías, multi-sucursal.', 'logo_url': 'https://cdn-icons-png.flaticon.com/512/1055/1055685.png', 'price': 'Desde $10/mes', 'category': 'comercial', 'features': 'Punto de venta rápido|Escáner EAN/QR|Gestión de inventario|Membresía MP|Reportes|Multi-sucursal', 'videos': '[{"title":"Demo","url":"https://www.youtube.com/embed/dQw4w9WgXcQ"}]', 'sort_order': 1},
                {'name': 'SmartPost Restó', 'tagline': 'Gestión para restaurantes', 'description': 'Sistema gastronómico con mesas, comanda digital, productos por peso.', 'logo_url': 'https://cdn-icons-png.flaticon.com/512/3075/3075977.png', 'price': 'Desde $15/mes', 'category': 'gastronomico', 'features': 'Gestión de mesas|Comanda digital|Productos por peso|Impresión cocina|MP integrado', 'videos': '[{"title":"Demo","url":"https://www.youtube.com/embed/dQw4w9WgXcQ"}]', 'sort_order': 2},
            ]:
                db.session.add(System(**s))
            db.session.commit()


# ── Landing pública ──
@app.route('/')
def landing():
    systems = System.query.filter_by(is_active=True).order_by(System.sort_order).all()
    plans = Plan.query.filter_by(is_active=True).order_by(Plan.sort_order).all()
    return render_template('landing.html', systems=systems, plans=plans)


# ── Auth ──
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']) and user.is_active:
            login_user(user, remember=True)
            return redirect(url_for('dashboard'))
        flash('Usuario o contraseña incorrectos', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('landing'))


# ── Dashboard ──
@app.route('/dashboard')
@login_required
def dashboard():
    total_clients = Client.query.count()
    active_clients = Client.query.filter_by(status='active').count()
    total_revenue = db.session.query(db.func.sum(ClientStat.total_revenue)).scalar() or 0
    total_sales = db.session.query(db.func.sum(ClientStat.total_sales)).scalar() or 0
    recent_clients = Client.query.order_by(Client.created_at.desc()).limit(5).all()
    stats_by_month = db.session.query(
        db.func.strftime('%Y-%m', ClientStat.date).label('month'),
        db.func.sum(ClientStat.total_sales).label('sales'),
        db.func.sum(ClientStat.total_revenue).label('revenue'),
    ).group_by('month').order_by('month').all()
    return render_template('dashboard.html', total_clients=total_clients,
                           active_clients=active_clients, total_revenue=total_revenue,
                           total_sales=total_sales, recent_clients=recent_clients,
                           stats_by_month=stats_by_month)


# ── Clients CRUD ──
@app.route('/clients')
@login_required
def clients():
    all_clients = Client.query.order_by(Client.created_at.desc()).all()
    plans = Plan.query.filter_by(is_active=True).all()
    return render_template('clients.html', clients=all_clients, plans=plans)


@app.route('/clients/new', methods=['POST'])
@login_required
def client_new():
    name = request.form.get('name', '').strip()
    subdomain = request.form.get('subdomain', '').strip()
    if not name or not subdomain:
        flash('Nombre y subdominio requeridos', 'error')
        return redirect(url_for('clients'))
    client = Client(
        name=name,
        subdomain=subdomain,
        plan_id=request.form.get('plan_id', type=int),
        max_users=request.form.get('max_users', 5, type=int),
        notes=request.form.get('notes', ''),
        status='active',
    )
    db.session.add(client)
    db.session.commit()
    flash(f'Cliente "{name}" creado', 'success')
    return redirect(url_for('clients'))


@app.route('/clients/<int:id>/edit', methods=['POST'])
@login_required
def client_edit(id):
    client = Client.query.get_or_404(id)
    client.name = request.form.get('name', client.name).strip()
    client.subdomain = request.form.get('subdomain', client.subdomain).strip()
    client.instance_url = request.form.get('instance_url', client.instance_url)
    client.plan_id = request.form.get('plan_id', type=int) or client.plan_id
    client.status = request.form.get('status', client.status)
    client.max_users = request.form.get('max_users', client.max_users, type=int)
    client.notes = request.form.get('notes', client.notes)
    db.session.commit()
    flash('Cliente actualizado', 'success')
    return redirect(url_for('clients'))


@app.route('/clients/<int:id>/delete', methods=['POST'])
@login_required
def client_delete(id):
    client = Client.query.get_or_404(id)
    ClientStat.query.filter_by(client_id=id).delete()
    db.session.delete(client)
    db.session.commit()
    flash('Cliente eliminado', 'success')
    return redirect(url_for('clients'))


@app.route('/clients/<int:id>')
@login_required
def client_detail(id):
    client = Client.query.get_or_404(id)
    stats = client.stats.order_by(ClientStat.date.desc()).limit(30).all()
    return render_template('client_detail.html', client=client, stats=stats)


# ── Plans CRUD ──
@app.route('/plans')
@login_required
def plans():
    all_plans = Plan.query.order_by(Plan.sort_order).all()
    return render_template('plans.html', plans=all_plans)


@app.route('/plans/new', methods=['POST'])
@login_required
def plan_new():
    p = Plan(
        name=request.form['name'],
        price=request.form.get('price', 0, type=float),
        max_users=request.form.get('max_users', 5, type=int),
        max_products=request.form.get('max_products', 500, type=int),
        features=request.form.get('features', ''),
        sort_order=request.form.get('sort_order', 0, type=int),
    )
    db.session.add(p)
    db.session.commit()
    flash('Plan creado', 'success')
    return redirect(url_for('plans'))


@app.route('/plans/<int:id>/edit', methods=['POST'])
@login_required
def plan_edit(id):
    p = Plan.query.get_or_404(id)
    p.name = request.form.get('name', p.name)
    p.price = request.form.get('price', p.price, type=float)
    p.max_users = request.form.get('max_users', p.max_users, type=int)
    p.max_products = request.form.get('max_products', p.max_products, type=int)
    p.features = request.form.get('features', p.features)
    p.is_active = request.form.get('is_active', '1') == '1'
    p.sort_order = request.form.get('sort_order', p.sort_order, type=int)
    db.session.commit()
    flash('Plan actualizado', 'success')
    return redirect(url_for('plans'))


@app.route('/plans/<int:id>/delete', methods=['POST'])
@login_required
def plan_delete(id):
    p = Plan.query.get_or_404(id)
    Client.query.filter_by(plan_id=id).update({Client.plan_id: None})
    db.session.delete(p)
    db.session.commit()
    flash('Plan eliminado', 'success')
    return redirect(url_for('plans'))


# ── Systems CRUD (landing admin) ──
@app.route('/systems')
@login_required
def systems():
    all_systems = System.query.order_by(System.sort_order).all()
    return render_template('systems.html', systems=all_systems)


@app.route('/systems/new', methods=['POST'])
@login_required
def system_new():
    s = System(
        name=request.form['name'],
        tagline=request.form.get('tagline', ''),
        description=request.form.get('description', ''),
        logo_url=request.form.get('logo_url', ''),
        price=request.form.get('price', ''),
        category=request.form.get('category', ''),
        demo_url=request.form.get('demo_url', ''),
        features=request.form.get('features', ''),
        videos=request.form.get('videos', '[]'),
        sort_order=request.form.get('sort_order', 0, type=int),
    )
    db.session.add(s)
    db.session.commit()
    flash('Sistema creado', 'success')
    return redirect(url_for('systems'))


@app.route('/systems/<int:id>/edit', methods=['POST'])
@login_required
def system_edit(id):
    s = System.query.get_or_404(id)
    s.name = request.form.get('name', s.name)
    s.tagline = request.form.get('tagline', s.tagline)
    s.description = request.form.get('description', s.description)
    s.logo_url = request.form.get('logo_url', s.logo_url)
    s.price = request.form.get('price', s.price)
    s.category = request.form.get('category', s.category)
    s.demo_url = request.form.get('demo_url', s.demo_url)
    s.features = request.form.get('features', s.features)
    s.videos = request.form.get('videos', s.videos)
    s.is_active = request.form.get('is_active', '1') == '1'
    s.sort_order = request.form.get('sort_order', s.sort_order, type=int)
    db.session.commit()
    flash('Sistema actualizado', 'success')
    return redirect(url_for('systems'))


@app.route('/systems/<int:id>/delete', methods=['POST'])
@login_required
def system_delete(id):
    s = System.query.get_or_404(id)
    db.session.delete(s)
    db.session.commit()
    flash('Sistema eliminado', 'success')
    return redirect(url_for('systems'))


# ── API pública ──
@app.route('/api/systems')
def api_systems():
    systems = System.query.filter_by(is_active=True).order_by(System.sort_order).all()
    return jsonify([{
        'id': s.id, 'name': s.name, 'tagline': s.tagline,
        'description': s.description, 'logo_url': s.logo_url,
        'price': s.price, 'category': s.category, 'demo_url': s.demo_url,
        'features': [f.strip() for f in s.features.split('|') if f.strip()] if s.features else [],
        'videos': json.loads(s.videos) if s.videos else [],
        'sort_order': s.sort_order,
    } for s in systems])


@app.route('/api/plans')
def api_plans():
    plans = Plan.query.filter_by(is_active=True).order_by(Plan.sort_order).all()
    return jsonify([{
        'id': p.id, 'name': p.name, 'price': p.price,
        'max_users': p.max_users, 'max_products': p.max_products,
        'features': [f.strip() for f in p.features.split('|') if f.strip()] if p.features else [],
    } for p in plans])


# ── API para POS instances ──
@app.route('/api/heartbeat', methods=['POST'])
def api_heartbeat():
    data = request.get_json() or {}
    subdomain = data.get('subdomain', '')
    client = Client.query.filter_by(subdomain=subdomain).first()
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    client.last_heartbeat = datetime.now(timezone.utc)
    client.instance_url = data.get('instance_url', client.instance_url)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/stats', methods=['POST'])
def api_stats():
    data = request.get_json() or {}
    subdomain = data.get('subdomain', '')
    client = Client.query.filter_by(subdomain=subdomain).first()
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    today = date.today()
    stat = ClientStat.query.filter_by(client_id=client.id, date=today).first()
    if stat:
        stat.total_sales = data.get('total_sales', stat.total_sales)
        stat.total_revenue = data.get('total_revenue', stat.total_revenue)
        stat.total_products = data.get('total_products', stat.total_products)
        stat.active_users = data.get('active_users', stat.active_users)
    else:
        stat = ClientStat(
            client_id=client.id, date=today,
            total_sales=data.get('total_sales', 0),
            total_revenue=data.get('total_revenue', 0),
            total_products=data.get('total_products', 0),
            active_users=data.get('active_users', 0),
        )
        db.session.add(stat)
    client.last_heartbeat = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'ok': True})


# ── Settings ──
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        if request.form.get('action') == 'change_password':
            if not current_user.check_password(request.form['current_password']):
                flash('Contraseña actual incorrecta', 'error')
            elif request.form['new_password'] != request.form['confirm_password']:
                flash('Las contraseñas no coinciden', 'error')
            elif len(request.form['new_password']) < 6:
                flash('La contraseña debe tener al menos 6 caracteres', 'error')
            else:
                current_user.set_password(request.form['new_password'])
                db.session.commit()
                flash('Contraseña cambiada', 'success')
        return redirect(url_for('settings'))
    return render_template('settings.html')


@app.context_processor
def inject_now():
    return {'now': datetime.now(timezone.utc)}


if __name__ == '__main__':
    init_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
