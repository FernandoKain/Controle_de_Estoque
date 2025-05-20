from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from datetime import datetime
import os

# ==================================================
# Configuração inicial
# ==================================================
app = Flask(__name__)
app.secret_key = '123'  # Troque isso por uma chave segura

base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'database', 'estoque.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================================================
# Modelos
# ==================================================
class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)

class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    preco = db.Column(db.Float, nullable=False)
    estoque_minimo = db.Column(db.Integer, nullable=False, default=0)

class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    tipo = db.Column(db.String(10))  # 'entrada' ou 'saida'
    quantidade = db.Column(db.Integer, nullable=False)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    produto = db.relationship('Produto', backref=db.backref('movimentacoes', lazy=True))

# ==================================================
# Autenticação
# ==================================================
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

@app.before_request
def proteger_rotas():
    rotas_livres = ['login', 'static']
    if 'usuario_id' not in session and request.endpoint not in rotas_livres:
        return redirect(url_for('login'))

# ==================================================
# Rotas de autenticação
# ==================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and check_password_hash(usuario.senha, senha):
            login_user(usuario)
            return redirect('/')
        flash('E-mail ou senha inválidos.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

# ==================================================
# Rotas principais
# ==================================================
@app.route('/')
@login_required
def index():
    termo_busca = request.args.get('busca', '')
    if termo_busca:
        produtos = Produto.query.filter(
            or_(
                Produto.nome.ilike(f'%{termo_busca}%'),
                Produto.categoria.ilike(f'%{termo_busca}%')
            )
        ).all()
    else:
        produtos = Produto.query.all()
    return render_template('index.html', produtos=produtos)

@app.route('/adicionar', methods=['GET', 'POST'])
def adicionar():
    if request.method == 'POST':
        nome = request.form['nome']
        categoria = request.form['categoria']
        quantidade = int(request.form['quantidade'])
        preco = float(request.form['preco'])
        estoque_minimo = int(request.form['estoque_minimo'])

        novo_produto = Produto(
            nome=nome,
            categoria=categoria,
            quantidade=quantidade,
            preco=preco,
            estoque_minimo=estoque_minimo
        )
        db.session.add(novo_produto)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('adicionar.html')

@app.route('/add', methods=['POST'])
def add():
    nome = request.form['nome']
    categoria = request.form['categoria']
    quantidade = int(request.form['quantidade'])
    preco = float(request.form['preco'])

    novo_produto = Produto(nome=nome, categoria=categoria, quantidade=quantidade, preco=preco)
    db.session.add(novo_produto)
    db.session.commit()

    return redirect(url_for('index'))

@app.route('/edit/<int:id>')
def edit(id):
    produto = Produto.query.get_or_404(id)
    return render_template('edit.html', produto=produto)

@app.route('/update/<int:id>', methods=['POST'])
def update(id):
    produto = Produto.query.get_or_404(id)
    produto.nome = request.form['nome']
    produto.categoria = request.form['categoria']
    produto.quantidade = int(request.form['quantidade'])
    produto.preco = float(request.form['preco'])
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete(id):
    produto = Produto.query.get_or_404(id)
    db.session.delete(produto)
    db.session.commit()
    return redirect(url_for('index'))

# ==================================================
# Rotas de movimentação
# ==================================================
@app.route('/movimentar')
def movimentar():
    produtos = Produto.query.all()
    return render_template('movimentar.html', produtos=produtos)

@app.route('/registrar_movimentacao', methods=['POST'])
def registrar_movimentacao():
    produto_id = int(request.form['produto_id'])
    tipo = request.form['tipo']
    quantidade = int(request.form['quantidade'])

    produto = Produto.query.get_or_404(produto_id)

    if tipo == 'entrada':
        produto.quantidade += quantidade
    elif tipo == 'saida':
        if produto.quantidade >= quantidade:
            produto.quantidade -= quantidade
        else:
            return "Erro: Estoque insuficiente.", 400

    movimentacao = Movimentacao(produto_id=produto.id, tipo=tipo, quantidade=quantidade)
    db.session.add(movimentacao)
    db.session.commit()
    return redirect(url_for('index'))

# ==================================================
# Relatório
# ==================================================
@app.route('/relatorio')
def relatorio():
    produtos = Produto.query.all()
    movimentacoes = Movimentacao.query.order_by(Movimentacao.data.desc()).all()
    valor_total_estoque = sum(p.quantidade * p.preco for p in produtos)
    total_produtos = len(produtos)

    return render_template(
        'relatorio.html',
        produtos=produtos,
        movimentacoes=movimentacoes,
        valor_total_estoque=valor_total_estoque,
        total_produtos=total_produtos
    )

# ==================================================
# Execução da aplicação
# ==================================================
if __name__ == '__main__':
    os.makedirs(os.path.join(base_dir, 'database'), exist_ok=True)
    with app.app_context():
        db.drop_all()
        db.create_all()
        if not Usuario.query.filter_by(email='admin@admin.com').first():
            senha_hash = generate_password_hash('admin123')
            admin = Usuario(nome='Admin', email='admin@admin.com', senha=senha_hash)
            db.session.add(admin)
            db.session.commit()
            print("Usuário admin criado com sucesso.")
        else:
            print("Usuário admin já existe.")
    app.run(debug=True)
