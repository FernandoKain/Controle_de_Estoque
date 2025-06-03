# ==================================================
# Testes
# ==================================================
@pytest.fixture
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
    
    
