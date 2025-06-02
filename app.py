# Flask e extensões principais
from flask import Flask, render_template, render_template_string, request, redirect, url_for, session, flash, make_response, send_file

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin

# SQLAlchemy adicional
from sqlalchemy import or_
from sqlalchemy import func, case, desc, and_

# Segurança
from werkzeug.security import generate_password_hash, check_password_hash

# Utilidades do sistema
from datetime import datetime
import os
import csv
import io

# Exportação e geração de PDF
from xhtml2pdf import pisa
from io import BytesIO, StringIO


# Testes (se estiver usando pytest de fato)
import pytest

# Importa o db e os modelos do arquivo models.py
from models import db, Usuario, Categoria, Produto, Setor, Movimentacao

# Importa o unicodedata para normalização de strings
import unicodedata

# Importa o módulo de IO para manipulação de arquivos
from io import TextIOWrapper


# =======================================================
# Configuração da aplicação
# =======================================================
app = Flask(__name__)
app.secret_key = '123'  # Troque por uma chave segura

# Configuração do banco
base_dir = os.path.abspath(os.path.dirname(__file__))
os.makedirs(os.path.join(base_dir, 'database'), exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'database', 'estoque.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa o banco com a instância do app
db.init_app(app)



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


@app.route('/lista_compras')
@login_required
def lista_compras():
    movimentacoes = Movimentacao.query.order_by(Movimentacao.data.desc()).all()
    return render_template('lista_compras.html', movimentacoes=movimentacoes)



# ==================================================
# Função para normalizar texto (remover acentos e converter para minúsculas) para ajudar na rota de adicionar produtos
import unicodedata
def normalizar_texto(texto):
    """Remove acentos e converte para minúsculas."""
    texto = texto.strip().lower()
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join([c for c in texto if not unicodedata.combining(c)])
    return texto

@app.route('/adicionar', methods=['POST'])
@login_required
def adicionar():
    nome_original = request.form['nome'].strip()
    nome_normalizado = normalizar_texto(nome_original)
    quantidade = int(request.form['quantidade'])
    preco = float(request.form['preco'])
    estoque_minimo = int(request.form['estoque_minimo'])
    categoria_id = int(request.form['categoria_id'])

    # Verifica se já existe um produto com o mesmo nome (ignorando acentos e maiúsculas)
    produtos = Produto.query.all()
    for p in produtos:
        if normalizar_texto(p.nome) == nome_normalizado:
            flash('Produto já cadastrado. Utilize "Movimentar" caso queira dar entrada no produto.', 'danger')
            return redirect(url_for('index'))

    # Se não existir, adiciona o novo produto
    produto = Produto(
        nome=nome_original,
        quantidade=quantidade,
        preco=preco,
        estoque_minimo=estoque_minimo,
        categoria_id=categoria_id
    )

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
    produto.categoria_id = int(request.form['categoria_id'])  # ✅ CORRETO
    produto.quantidade = int(request.form['quantidade'])
    produto.preco = float(request.form['preco'])
    produto.estoque_minimo = int(request.form['estoque_minimo'])  # você usa isso no form
    db.session.commit()
    flash('Produto atualizado com sucesso.', 'success')
    return redirect(url_for('index', id=id))


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


@app.route('/excluir_movimentacao/<int:id>', methods=['POST'])
@login_required
def excluir_movimentacao(id):
    movimentacao = Movimentacao.query.get_or_404(id)
    produto = Produto.query.get(movimentacao.produto_id)

    # Reverter o estoque
    if movimentacao.tipo == 'entrada':
        produto.quantidade -= movimentacao.quantidade
    elif movimentacao.tipo == 'saida':
        produto.quantidade += movimentacao.quantidade

    db.session.delete(movimentacao)
    db.session.commit()

    flash('Movimentação excluída com sucesso.', 'success')
    return redirect(url_for('relatorio'))



@app.route('/manual', methods=['GET'])
@login_required
def manual():
    if not current_user.is_admin:
        flash('Acesso negado. Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('manual.html'))
    return render_template('manual.html')

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
            novo_setor = Setor(nome=nome, status=True)
            # Verifica se já existe um setor com o mesmo nome
            setor_existente = Setor.query.filter_by(nome=nome).first()
            if setor_existente:
                flash('Já existe um setor com esse nome.', 'warning')
                return redirect(url_for('cadastrar_setor'))
            
            # Adiciona o novo setor ao banco de dados
            db.session.add(novo_setor)
            db.session.commit()
            flash('Setor cadastrado com sucesso!', 'success')
        else:
            flash('O nome do setor é obrigatório.', 'danger')
        return redirect(url_for('cadastrar_setor'))
        
    setores = Setor.query.all()
    return render_template('cadastrar_setor.html', setores=setores)

# ==================================================
# Editar e exlcuir categorias
# ==================================================
@app.route('/editar_categoria/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_categoria(id):
    if not current_user.is_admin:
        flash("Acesso restrito ao administrador.", "danger")
        return redirect(url_for('categorias'))

    categoria = Categoria.query.get_or_404(id)

    if request.method == 'POST':
        novo_nome = request.form['nome']
        if not novo_nome:
            flash('O nome da categoria é obrigatório.', 'danger')
        else:
            existente = Categoria.query.filter_by(nome=novo_nome).first()
            if existente and existente.id != categoria.id:
                flash('Já existe uma categoria com esse nome.', 'warning')
            else:
                categoria.nome = novo_nome
                db.session.commit()
                flash('Categoria atualizada com sucesso.', 'success')
                return redirect(url_for('categorias'))

    return render_template('editar_categoria.html', categoria=categoria)

@app.route('/excluir_categoria/<int:id>', methods=['POST'])
@login_required
def excluir_categoria(id):
    if not current_user.is_admin:
        flash("Acesso restrito ao administrador.", "danger")
        return redirect(url_for('categorias'))

    categoria = Categoria.query.get_or_404(id)

    if categoria.produtos:
        flash('Não é possível excluir uma categoria com produtos vinculados.', 'danger')
    else:
        db.session.delete(categoria)
        db.session.commit()
        flash('Categoria excluída com sucesso.', 'success')

    return redirect(url_for('categorias'))


# ==================================================
# Editar e exlcuir setores
# ==================================================
@app.route('/editar_setor/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_setor(id):
    if not current_user.is_admin:
        flash("Acesso restrito ao administrador.", "danger")
        return redirect(url_for('cadastrar_setor'))

    setor = Setor.query.get_or_404(id)

    if request.method == 'POST':
        novo_nome = request.form['nome']
        if not novo_nome:
            flash('O nome do setor é obrigatório.', 'danger')
        else:
            existente = Setor.query.filter_by(nome=novo_nome).first()
            if existente and existente.id != setor.id:
                flash('Já existe um setor com esse nome.', 'warning')
            else:
                setor.nome = novo_nome
                db.session.commit()
                flash('Setor atualizado com sucesso.', 'success')
                return redirect(url_for('cadastrar_setor'))

    return render_template('editar_setor.html', setor=setor)

@app.route('/desabilitar_setor/<int:id>', methods=['POST'])
@login_required
def desabilitar_setor(id):
    if not current_user.is_admin:
        flash("Acesso restrito ao administrador.", "danger")
        return redirect(url_for('cadastrar_setor'))

    setor = Setor.query.get_or_404(id)

    # Caso seja incluído o campo status no modelo Setor, descomente as linhas abaixo
    setor.status = False  # Define o status como inativo
    db.session.commit()
    
    flash('Setor desabilitado com sucesso.', 'success')

    return redirect(url_for('cadastrar_setor'))

@app.route('/habilitar_setor/<int:id>', methods=['POST'])
@login_required
def habilitar_setor(id):
    if not current_user.is_admin:
        flash("Acesso restrito ao administrador.", "danger")
        return redirect(url_for('cadastrar_setor'))

    setor = Setor.query.get_or_404(id)

    setor.status = True  # Define o status como ativo
    print(f"Habilitando setor: {setor.nome}, status: {setor.status}")  # Debugging
    db.session.commit()
    print(f"Habilitando setor: {setor.nome}, status: {setor.status}")  # Debugging
    
    flash('Setor habilitado com sucesso.', 'success')
    return redirect(url_for('cadastrar_setor'))

# ==================================================
# Relatórios e exportação e importação de CSV e PDF
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

            # Verifica se já existe produto com mesmo nome E mesmo preço
            produto_existente = Produto.query.filter_by(nome=nome, preco=preco).first()
            if produto_existente:
                # Atualiza o produto existente
                produto_existente.quantidade += quantidade
            else:
                # Se não existe, cria novo produto
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

@app.route('/exportar_csv_movimentacoes')
@login_required
def exportar_csv_movimentacoes():
    
    # Se for filtrar, colocar os requisitos aqui
    #

    query = Movimentacao.query
    movimentacoes = query.all()

    # Geração do CSV
    si = StringIO()
    writer = csv.writer(si)
    # Cabeçalho corrigido
    writer.writerow(['data', 'produto', 'tipo', 'qtd', 'setor'])

    for m in movimentacoes:
        writer.writerow([
            m.data.strftime('%Y-%m-%d %H:%M:%S'),
            m.produto.nome if m.produto else '',
            m.tipo,
            m.quantidade,
            m.setor.nome if m.setor else ''
        ])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=relatorio_movimentacao.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output

@app.route('/importar_csv_movimentacoes', methods=['POST'])
@login_required
def importar_csv_movimentacoes():

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
            data_str = linha['data']
            produto_nome = linha['produto']
            tipo = linha['tipo']
            quantidade = int(linha['qtd'])
            setor_nome = linha.get('setor', '').strip()

            # Converte a string de data para datetime
            data = datetime.strptime(data_str, '%Y-%m-%d %H:%M:%S')

            produto = Produto.query.filter_by(nome=produto_nome).first()
            if not produto:
                flash(f'Produto "{produto_nome}" não encontrado. Movimentação não importada.', 'danger')
                continue

            setor = Setor.query.filter_by(nome=setor_nome).first() if setor_nome else None
            
            if setor is None and setor_nome != "":
                # Se o setor não for encontrado, criá-lo
                setor = Setor(nome=setor_nome, status=True)
                db.session.add(setor)
                setor = Setor.query.filter_by(nome=setor_nome).first()

            nova_movimentacao = Movimentacao(
                produto_id=produto.id,
                tipo=tipo,
                quantidade=quantidade,
                data=data,
                setor_id=setor.id if setor else None
            )
            db.session.add(nova_movimentacao)

        db.session.commit()
        flash('Importação Finalizada!', 'success')
    except Exception as e:
        flash(f'Erro ao importar arquivo: {str(e)}', 'danger')
        

    return redirect(url_for('relatorio'))


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
# Gráficos e visualizações
# ==================================================
from datetime import datetime
from sqlalchemy import func

@app.route('/graficos')
@login_required
def graficos():
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    produto_id = request.args.get('produto_id')
    setor_id = request.args.get('setor_id')

    query = Movimentacao.query

    if data_inicio:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        query = query.filter(Movimentacao.data >= data_inicio)

    if data_fim:
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d')
        query = query.filter(Movimentacao.data <= data_fim)

    if produto_id:
        query = query.filter(Movimentacao.produto_id == int(produto_id))

    if setor_id:
        query = query.filter(Movimentacao.setor_id == int(setor_id))

    movimentacoes_filtradas = query.all()

    # Saídas por produto
    saidas_produto = db.session.query(
        Produto.nome,
        func.sum(Movimentacao.quantidade)
    ).join(Produto).filter(
        Movimentacao.tipo == 'saida'
    )

    if produto_id:
        saidas_produto = saidas_produto.filter(Movimentacao.produto_id == int(produto_id))
    if setor_id:
        saidas_produto = saidas_produto.filter(Movimentacao.setor_id == int(setor_id))
    if data_inicio:
        saidas_produto = saidas_produto.filter(Movimentacao.data >= data_inicio)
    if data_fim:
        saidas_produto = saidas_produto.filter(Movimentacao.data <= data_fim)

    saidas_produto = saidas_produto.group_by(Produto.nome).all()

    nomes_produtos = [p[0] for p in saidas_produto]
    quantidades_produtos = [p[1] for p in saidas_produto]

    # Saídas por setor
    saidas_setor = db.session.query(
        Setor.nome,
        func.sum(Movimentacao.quantidade)
    ).join(Setor).filter(
        Movimentacao.tipo == 'saida'
    )

    if produto_id:
        saidas_setor = saidas_setor.filter(Movimentacao.produto_id == int(produto_id))
    if setor_id:
        saidas_setor = saidas_setor.filter(Movimentacao.setor_id == int(setor_id))
    if data_inicio:
        saidas_setor = saidas_setor.filter(Movimentacao.data >= data_inicio)
    if data_fim:
        saidas_setor = saidas_setor.filter(Movimentacao.data <= data_fim)

    saidas_setor = saidas_setor.group_by(Setor.nome).all()

    nomes_setores = [s[0] for s in saidas_setor]
    quantidades_setores = [s[1] for s in saidas_setor]

    # Gráfico mensal
    movimentacoes_mensais = {}
    for mov in movimentacoes_filtradas:
        chave = mov.data.strftime('%Y-%m')
        if chave not in movimentacoes_mensais:
            movimentacoes_mensais[chave] = {'entrada': 0, 'saida': 0}
        movimentacoes_mensais[chave][mov.tipo] += mov.quantidade

    meses = sorted(movimentacoes_mensais.keys())
    entradas_mes = [movimentacoes_mensais[m]['entrada'] for m in meses]
    saidas_mes = [movimentacoes_mensais[m]['saida'] for m in meses]

    # Saldo atual por produto (Entradas - Saídas)
    saldos = db.session.query(
        Produto.nome,
        func.sum(
            case(
                (Movimentacao.tipo == 'entrada', Movimentacao.quantidade),
                (Movimentacao.tipo == 'saida', -Movimentacao.quantidade),
                else_=0
            )
        )
    ).join(Produto).group_by(Produto.nome).all()

    nomes_saldo = [s[0] for s in saldos]
    quantidades_saldo = [s[1] for s in saldos]


    return render_template('graficos.html',
        nomes_produtos=nomes_produtos,
        quantidades_produtos=quantidades_produtos,
        nomes_setores=nomes_setores,
        quantidades_setores=quantidades_setores,
        meses=meses,
        entradas_mes=entradas_mes,
        saidas_mes=saidas_mes,
        nomes_saldo=nomes_saldo,
        quantidades_saldo=quantidades_saldo,
        todos_produtos=Produto.query.all(),
        todos_setores=Setor.query.all()
    )








# ==================================================
# Execução da aplicação
# ==================================================
if __name__ == '__main__':
    with app.app_context():
        #db.drop_all()  # Use com cuidado — apaga todo banco
        db.create_all()
        
        # Cria o usuário admin se não existir
        if not Usuario.query.filter_by(email='admin@admin.com').first():
            senha_hash = generate_password_hash('admin123')
            admin = Usuario(nome='Admin', email='admin@admin.com', senha=senha_hash, tipo='admin')
            db.session.add(admin)
            db.session.commit()
            print("Usuário admin criado com sucesso.")
        else:
            print("Usuário admin já existe.")
            
            
    
    app.run(host='0.0.0.0', port=5000, debug=True)
