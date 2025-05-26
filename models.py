from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


# ==================================================
# Modelos do Banco de Dados
# ==================================================

class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default='usuario')
    

    @property
    def is_admin(self):
        return self.tipo == 'admin'

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
