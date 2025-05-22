from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response, send_file, render_template_string
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from datetime import datetime
import csv
import io
import os
import pytest
from xhtml2pdf import pisa
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from datetime import datetime
from flask import make_response
from flask import send_file
import csv
from io import StringIO
from io import BytesIO
from xhtml2pdf import pisa
import csv
from io import TextIOWrapper
from flask import request, redirect, url_for, flash
from flask import render_template_string
from datetime import datetime
import os
import io


# ==================================================
# Configuração inicial
# ==================================================
app = Flask(__name__)
app.secret_key = '123'  # Troque isso por uma chave segura

base_dir = os.path.abspath(os.path.dirname(__file__))
os.makedirs(os.path.join(base_dir, 'database'), exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'database', 'estoque.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================================================
# Modelos do Banco de Dados
# ==================================================
class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default='usuario')  # 'admin' ou 'usuario'
    
    @property
    def is_admin(self):
        return self.tipo=='admin'

class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False, unique=True)
    produtos = db.relationship('Produto', backref='categoria', lazy=True)

class Produto(db.Model):
    __tablename__ = 'produtos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    preco = db.Column(db.Float, nullable=False)
    estoque_minimo = db.Column(db.Integer, nullable=False, default=0)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=False)

class Setor(db.Model):
    __tablename__ = 'setores'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f'<Setor {self.nome}>'

class Movimentacao(db.Model):
    __tablename__ = 'movimentacoes'
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'))
    tipo = db.Column(db.String(10))  # entrada ou saida
    quantidade = db.Column(db.Integer)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    setor_id = db.Column(db.Integer, db.ForeignKey('setores.id'), nullable=True)

    produto = db.relationship('Produto', backref='movimentacoes')
    setor = db.relationship('Setor', backref='movimentacoes')



# ==================================================
# Autenticação
# ==================================================
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

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
    busca = request.args.get('busca')
    categorias = Categoria.query.all()

    if busca:
        produtos = Produto.query.join(Categoria).filter(
            Produto.nome.ilike(f'%{busca}%') |
            Categoria.nome.ilike(f'%{busca}%')
        ).all()
    else:
        produtos = Produto.query.all()

    return render_template('index.html', produtos=produtos, categorias=categorias)


@app.route('/adicionar', methods=['POST'])
@login_required
def adicionar():
    nome = request.form['nome']
    quantidade = int(request.form['quantidade'])
    preco = float(request.form['preco'])
    estoque_minimo = int(request.form['estoque_minimo'])
    categoria_id = int(request.form['categoria_id'])

    produto = Produto(nome=nome, quantidade=quantidade, preco=preco,
                      estoque_minimo=estoque_minimo, categoria_id=categoria_id)

    db.session.add(produto)
    db.session.commit()
    flash('Produto adicionado com sucesso.', 'success')
    return redirect(url_for('index'))

@app.route('/edit/<int:id>')
@login_required
def edit(id):
    produto = Produto.query.get_or_404(id)
    categorias = Categoria.query.all()
    return render_template('edit.html', produto=produto, categorias=categorias)

@app.route('/update/<int:id>', methods=['POST'])
@login_required
def update(id):
    produto = Produto.query.get_or_404(id)
    produto.nome = request.form['nome']
    produto.categoria = request.form['categoria']
    produto.quantidade = int(request.form['quantidade'])
    produto.preco = float(request.form['preco'])
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/categorias', methods=['GET', 'POST'])
@login_required
def categorias():
    if not current_user.is_admin:
        flash("Acesso restrito ao administrador.")
        return redirect(url_for('index'))

    if request.method == 'POST':
        nome = request.form['nome']
        if not nome:
            flash('Nome da categoria é obrigatório.', 'danger')
        else:
            categoria_existente = Categoria.query.filter_by(nome=nome).first()
            if categoria_existente:
                flash('Categoria já cadastrada.', 'warning')
            else:
                nova = Categoria(nome=nome)
                db.session.add(nova)
                db.session.commit()
                flash('Categoria cadastrada com sucesso.', 'success')
        return redirect(url_for('categorias'))

    categorias = Categoria.query.all()
    return render_template('categorias.html', categorias=categorias)

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    produto = Produto.query.get_or_404(id)
    db.session.delete(produto)
    db.session.commit()
    return redirect(url_for('index'))

# ==================================================
# Rotas de movimentação
# ==================================================
@app.route('/movimentar')
@login_required
def movimentar():
    produtos = Produto.query.all()
    setores = Setor.query.all()
    return render_template('movimentar.html', produtos=produtos, setores=setores)

@app.route('/registrar_movimentacao', methods=['POST'])
@login_required
def registrar_movimentacao():
    produto_id = int(request.form['produto_id'])
    tipo = request.form['tipo']
    quantidade = int(request.form['quantidade'])

    setor_id = request.form.get('setor_id') if tipo == 'saida' else None
    if tipo == 'saida' and not setor_id:
        flash('O setor é obrigatório para saídas.', 'danger')
        return redirect(url_for('movimentar'))

    produto = Produto.query.get(produto_id)
    if tipo == 'entrada':
        produto.quantidade += quantidade
    elif tipo == 'saida':
        if produto.quantidade >= quantidade:
            produto.quantidade -= quantidade
        else:
            flash('Estoque insuficiente para esta saída.', 'danger')
            return redirect(url_for('movimentar'))

    nova_mov = Movimentacao(
        produto_id=produto_id,
        tipo=tipo,
        quantidade=quantidade,
        setor_id=int(setor_id) if setor_id else None
    )
    db.session.add(nova_mov)
    db.session.commit()
    flash('Movimentação registrada com sucesso.', 'success')
    return redirect(url_for('movimentar'))

# ==================================================
# Cadastrar Setor
# ==================================================
@app.route('/cadastrar_setor', methods=['GET', 'POST'])
@login_required
def cadastrar_setor():
    if not current_user.is_admin:
        flash('Acesso negado. Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        nome = request.form['nome']
        if nome:
            novo_setor = Setor(nome=nome)
            db.session.add(novo_setor)
            db.session.commit()
            flash('Setor cadastrado com sucesso!', 'success')
        else:
            flash('O nome do setor é obrigatório.', 'danger')
        return redirect(url_for('cadastrar_setor'))
        
    setores = Setor.query.all()
    return render_template('cadastrar_setor.html', setores=setores)

# ==================================================
# Relatório
# ==================================================
@app.route('/relatorio')
@login_required
def relatorio():
    movimentacoes = Movimentacao.query.order_by(Movimentacao.data.desc()).all()
    return render_template('relatorio.html', movimentacoes=movimentacoes)


@app.route('/relatorio_avancado')
@login_required
def relatorio_avancado():
    categoria_nome = request.args.get('categoria')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    estoque_baixo = request.args.get('estoque_baixo')

    query = Produto.query

    # Filtro por categoria
    if categoria_nome:
        categoria = Categoria.query.filter_by(nome=categoria_nome).first()
        if categoria:
            query = query.filter(Produto.categoria_id == categoria.id)

    # Filtro por data (baseado na movimentação)
    if data_inicio or data_fim:
        subquery = db.session.query(Movimentacao.produto_id)
        if data_inicio:
            subquery = subquery.filter(Movimentacao.data >= data_inicio)
        if data_fim:
            subquery = subquery.filter(Movimentacao.data <= data_fim)
        query = query.filter(Produto.id.in_(subquery))

    # Filtro por estoque baixo
    if estoque_baixo:
        query = query.filter(Produto.quantidade <= Produto.estoque_minimo)


    # Filtro por nome limitando a 10 produtos
    
    page = request.args.get('page', 1, type=int)
    per_page = 500  # ou outro valor desejado
    produtos_filtrados = query.paginate(page=page, per_page=per_page)
    
    

    # Se não houver produtos filtrados, retorna todos os produtos - opcional
    # produtos_filtrados = query.all()
    categorias = Categoria.query.all()

    return render_template('relatorio_avancado.html', produtos=produtos_filtrados, categorias=categorias)


@app.route('/exportar_csv')
@login_required
def exportar_csv():
    # Reutiliza os mesmos filtros
    categoria_nome = request.args.get('categoria')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    estoque_baixo = request.args.get('estoque_baixo')

    query = Produto.query

    if categoria_nome:
        categoria = Categoria.query.filter_by(nome=categoria_nome).first()
        if categoria:
            query = query.filter(Produto.categoria_id == categoria.id)

    if data_inicio or data_fim:
        subquery = db.session.query(Movimentacao.produto_id)
        if data_inicio:
            subquery = subquery.filter(Movimentacao.data >= data_inicio)
        if data_fim:
            subquery = subquery.filter(Movimentacao.data <= data_fim)
        query = query.filter(Produto.id.in_(subquery))

    if estoque_baixo:
        query = query.filter(Produto.quantidade <= Produto.estoque_minimo)

    produtos = query.all()

    # Geração do CSV
    si = StringIO()
    writer = csv.writer(si)
    # Cabeçalho corrigido
    writer.writerow(['nome', 'quantidade', 'preco', 'estoque_minimo', 'categoria'])

    for p in produtos:
        writer.writerow([
            p.nome,
            p.quantidade,
            f'{p.preco:.2f}',
            p.estoque_minimo,
            p.categoria.nome if p.categoria else ''
        ])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=relatorio.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output


@app.route('/exportar_pdf')
@login_required
def exportar_pdf():
    categoria_nome = request.args.get('categoria')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    estoque_baixo = request.args.get('estoque_baixo')

    query = Produto.query

    if categoria_nome:
        categoria = Categoria.query.filter_by(nome=categoria_nome).first()
        if categoria:
            query = query.filter(Produto.categoria_id == categoria.id)

    if data_inicio or data_fim:
        subquery = db.session.query(Movimentacao.produto_id)
        if data_inicio:
            subquery = subquery.filter(Movimentacao.data >= data_inicio)
        if data_fim:
            subquery = subquery.filter(Movimentacao.data <= data_fim)
        query = query.filter(Produto.id.in_(subquery))

    if estoque_baixo:
        query = query.filter(Produto.quantidade <= Produto.estoque_minimo)

    produtos = query.all()

    # Renderiza o template HTML
    html = render_template('relatorio_pdf.html', produtos=produtos)

    # Cria um buffer para bytes
    result = BytesIO()

    # Gera o PDF
    pdf_status = pisa.CreatePDF(html.encode('utf-8'), dest=result)

    if not pdf_status.err:
        result.seek(0)  # volta o ponteiro para o início
        return send_file(
            result,
            mimetype='application/pdf',
            download_name='relatorio.pdf',
            as_attachment=True
        )
    else:
        return "Erro ao gerar PDF", 500



@app.route('/importar_csv', methods=['POST'])
@login_required
def importar_csv():

    if 'arquivo_csv' not in request.files:
        flash('Nenhum arquivo enviado.', 'danger')
        return redirect(url_for('relatorio_avancado'))

    arquivo = request.files['arquivo_csv']

    if not arquivo.filename.endswith('.csv'):
        flash('Formato de arquivo inválido. Envie um arquivo .csv', 'danger')
        return redirect(url_for('index'))

    try:
        stream = TextIOWrapper(arquivo, encoding='utf-8')
        reader = csv.DictReader(stream)

        for linha in reader:
            nome = linha['nome']
            quantidade = int(linha['quantidade'])
            preco = float(linha['preco'])
            estoque_minimo = int(linha.get('estoque_minimo', 0))
            categoria_nome = linha.get('categoria', '').strip()

            if not nome or not categoria_nome:
                flash('Nome ou categoria ausente em alguma linha.', 'danger')
                continue

            categoria = Categoria.query.filter_by(nome=categoria_nome).first()
            if not categoria:
                categoria = Categoria(nome=categoria_nome)
                db.session.add(categoria)
                db.session.commit()

            produto = Produto(
                nome=nome,
                quantidade=quantidade,
                preco=preco,
                estoque_minimo=estoque_minimo,
                categoria_id=categoria.id
            )
            db.session.add(produto)

        db.session.commit()
        flash('Produtos importados com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao importar arquivo: {str(e)}', 'danger')

    return redirect(url_for('relatorio_avancado'))



def test_importar_csv(client, db):
    # Conteúdo CSV de exemplo, deve bater com o seu formato esperado
    csv_data = """ID,Nome,Categoria,Quantidade,Estoque Mínimo,Preço
1,Produto Teste,Categoria Teste,10,5,R$ 15,50
2,Produto Novo,Categoria Nova,20,10,R$ 30,00
"""

    data = {
        'arquivo_csv': (io.BytesIO(csv_data.encode('utf-8')), 'produtos_teste.csv')
    }

    # Faz o POST para a rota /importar_csv
    response = client.post('/importar_csv', data=data, content_type='multipart/form-data', follow_redirects=True)

    assert response.status_code == 200
    assert "Importação concluída com sucesso" in response.data.decode('utf-8') or "Importacao concluida com sucesso" in response.data.decode('utf-8')


    # Aqui você pode fazer mais asserts consultando o banco se quiser
    produto_teste = Produto.query.filter_by(nome='Produto Teste').first()
    assert produto_teste is not None
    assert produto_teste.quantidade == 10

# ==================================================
# Execução da aplicação
# ==================================================
if __name__ == '__main__':
    with app.app_context():
        db.drop_all()  # Use com cuidado — apaga todo banco
        db.create_all()
        if not Usuario.query.filter_by(email='admin@admin.com').first():
            senha_hash = generate_password_hash('admin123')
            admin = Usuario(nome='Admin', email='admin@admin.com', senha=senha_hash, tipo='admin')
            db.session.add(admin)
            db.session.commit()
            print("Usuário admin criado com sucesso.")
        else:
            print("Usuário admin já existe.")
            
            
    
    app.run(debug=True)
