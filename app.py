from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime

app = Flask(__name__)

# Configuração do caminho do banco de dados SQLite
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'database', 'estoque.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modelo do produto
class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    preco = db.Column(db.Float, nullable=False)
    estoque_minimo = db.Column(db.Integer, nullable=False, default=0)


# Rota principal
@app.route('/')
def index():
    produtos = Produto.query.all()
    return render_template('index.html', produtos=produtos)

# Rota para adicionar produto
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

# Rota para excluir produto
@app.route('/delete/<int:id>')
def delete(id):
    produto = Produto.query.get_or_404(id)
    db.session.delete(produto)
    db.session.commit()
    return redirect(url_for('index'))

# Rota para editar produto
@app.route('/edit/<int:id>')
def edit(id):
    produto = Produto.query.get_or_404(id)
    return render_template('edit.html', produto=produto)

# Rota para processar uma edição
@app.route('/update/<int:id>', methods=['POST'])
def update(id):
    produto = Produto.query.get_or_404(id)
    produto.nome = request.form['nome']
    produto.categoria = request.form['categoria']
    produto.quantidade = int(request.form['quantidade'])
    produto.preco = float(request.form['preco'])
    db.session.commit()
    return redirect(url_for('index'))

# Rota para registrar movimentação
@app.route('/movimentar')
def movimentar():
    produtos = Produto.query.all()
    return render_template('movimentar.html', produtos=produtos)

# Rota para registrar movimentação de entrada ou saída
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

# Rota para visualizar o relatório
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

# Rota para adicionar produto (formulário)
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



# Modelo da movimentação de estoque
class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    tipo = db.Column(db.String(10))  # 'entrada' ou 'saida'
    quantidade = db.Column(db.Integer, nullable=False)
    data = db.Column(db.DateTime, default=datetime.utcnow)

    produto = db.relationship('Produto', backref=db.backref('movimentacoes', lazy=True))





if __name__ == '__main__':
    os.makedirs(os.path.join(base_dir, 'database'), exist_ok=True)
    with app.app_context():
        # db.drop_all() descomente para limpar o banco de dados
        db.create_all()
    app.run(debug=True)
