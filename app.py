from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui_prato_feito'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///prato_feito.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    endereco = db.Column(db.String(200))
    telefone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Marmita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    preco = db.Column(db.Float, nullable=False)
    categoria = db.Column(db.String(50))
    tamanho = db.Column(db.String(20))
    imagem = db.Column(db.String(200))
    disponivel = db.Column(db.Boolean, default=True)

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    data_pedido = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pendente')
    total = db.Column(db.Float, nullable=False)
    endereco_entrega = db.Column(db.String(200), nullable=False)
    user = db.relationship('User', backref=db.backref('pedidos', lazy=True))

class ItemPedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'), nullable=False)
    marmita_id = db.Column(db.Integer, db.ForeignKey('marmita.id'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    preco_unitario = db.Column(db.Float, nullable=False)
    # NOVO: Status individual para cada item da comanda
    status_item = db.Column(db.String(20), default='enviando_restaurante')  # enviando_restaurante, em_andamento, entregando, concluido
    observacoes = db.Column(db.Text)
    marmita = db.relationship('Marmita', backref=db.backref('itens_pedido', lazy=True))
    pedido = db.relationship('Pedido', backref=db.backref('itens', lazy=True))

class Empresa(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    endereco = db.Column(db.String(200))

@login_manager.user_loader
def load_user(user_id):
    # Corrigindo o warning do SQLAlchemy 2.0
    return db.session.get(User, int(user_id)) or db.session.get(Empresa, int(user_id))

# Adicionar hasattr ao contexto dos templates
@app.context_processor
def utility_processor():
    return dict(hasattr=hasattr)

# Funções auxiliares
def user_exists(username, email):
    return User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first()

def empresa_exists(nome, email):
    return Empresa.query.filter_by(nome=nome).first() or Empresa.query.filter_by(email=email).first()

# Funções do carrinho
def get_carrinho():
    if 'carrinho' not in session:
        session['carrinho'] = []
    return session['carrinho']

def salvar_carrinho(carrinho):
    session['carrinho'] = carrinho
    session.modified = True

def calcular_total_carrinho():
    carrinho = get_carrinho()
    total = 0
    for item in carrinho:
        total += item['preco'] * item['quantidade']
    return total

# Rotas principais
@app.route('/')
def index():
    marmitas = Marmita.query.filter_by(disponivel=True).limit(6).all()
    return render_template('index.html', marmitas=marmitas)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username, email, password = request.form['username'], request.form['email'], request.form['password']
        if user_exists(username, email):
            flash('Usuário ou email já existe!', 'error')
            return redirect(url_for('register'))
        
        new_user = User(username=username, email=email, password=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        flash('Cadastro realizado! Faça login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        
        # Tenta login como User
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login realizado!', 'success')
            return redirect(url_for('index'))
        
        # Tenta login como Empresa
        empresa = Empresa.query.filter_by(nome=username).first()
        if empresa and check_password_hash(empresa.password, password):
            login_user(empresa)
            flash(f'Bem-vindo, {empresa.nome}!', 'success')
            return redirect(url_for('area_empresa'))
        
        flash('Usuário/Empresa ou senha incorretos!', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('carrinho', None)
    flash('Logout realizado!', 'success')
    return redirect(url_for('index'))

@app.route('/cardapio')
def cardapio():
    categoria = request.args.get('categoria')
    marmitas = Marmita.query.filter_by(categoria=categoria, disponivel=True).all() if categoria else Marmita.query.filter_by(disponivel=True).all()
    categorias = db.session.query(Marmita.categoria).distinct().all()
    return render_template('cardapio.html', marmitas=marmitas, categorias=categorias)

@app.route('/cadastro_loja', methods=['GET', 'POST'])
def cadastro_loja():
    if request.method == 'POST':
        nome, email, password, endereco = request.form['nome'], request.form['email'], request.form['password'], request.form['endereco']
        if empresa_exists(nome, email):
            flash('Empresa ou email já existe!', 'warning')
            return redirect(url_for('cadastro_loja'))
        
        new_empresa = Empresa(nome=nome, email=email, password=generate_password_hash(password), endereco=endereco)
        db.session.add(new_empresa)
        db.session.commit()
        flash('Empresa cadastrada! Faça login.', 'success')
        return redirect(url_for('login'))
    return render_template('cadastro_loja.html')

# Rotas para pratos
@app.route('/adicionar_prato', methods=['GET', 'POST'])
@login_required
def adicionar_prato():
    if request.method == 'POST':
        nova_marmita = Marmita(
            nome=request.form['nome'],
            descricao=request.form['descricao'],
            preco=float(request.form['preco']),
            categoria=request.form['categoria'],
            tamanho=request.form['tamanho'],
            disponivel=True
        )
        db.session.add(nova_marmita)
        db.session.commit()
        flash(f'Prato "{nova_marmita.nome}" adicionado!', 'success')
        return redirect(url_for('cardapio'))
    return render_template('adicionar_prato.html')

@app.route('/meus_pratos')
@login_required
def meus_pratos():
    marmitas = Marmita.query.all()
    return render_template('meus_pratos.html', marmitas=marmitas)

@app.route('/editar_prato/<int:prato_id>', methods=['GET', 'POST'])
@login_required
def editar_prato(prato_id):
    marmita = Marmita.query.get_or_404(prato_id)
    if request.method == 'POST':
        marmita.nome = request.form['nome']
        marmita.descricao = request.form['descricao']
        marmita.preco = float(request.form['preco'])
        marmita.categoria = request.form['categoria']
        marmita.tamanho = request.form['tamanho']
        marmita.disponivel = 'disponivel' in request.form
        db.session.commit()
        flash(f'Prato "{marmita.nome}" atualizado!', 'success')
        return redirect(url_for('meus_pratos'))
    return render_template('editar_prato.html', marmita=marmita)

@app.route('/excluir_prato/<int:prato_id>')
@login_required
def excluir_prato(prato_id):
    marmita = Marmita.query.get_or_404(prato_id)
    db.session.delete(marmita)
    db.session.commit()
    flash(f'Prato "{marmita.nome}" excluído!', 'success')
    return redirect(url_for('meus_pratos'))

# Rotas do carrinho e pedidos - OBRIGATÓRIO ESTAR LOGADO
@app.route('/adicionar_carrinho/<int:marmita_id>')
@login_required
def adicionar_carrinho(marmita_id):
    marmita = Marmita.query.get_or_404(marmita_id)
    
    if not marmita.disponivel:
        flash('Esta marmita não está disponível no momento.', 'error')
        return redirect(url_for('cardapio'))
    
    quantidade = 1  # Quantidade fixa para simplificar
    
    carrinho = get_carrinho()
    
    # Verifica se o item já está no carrinho
    item_existente = None
    for item in carrinho:
        if item['marmita_id'] == marmita_id:
            item_existente = item
            break
    
    if item_existente:
        item_existente['quantidade'] += quantidade
    else:
        carrinho.append({
            'marmita_id': marmita.id,
            'nome': marmita.nome,
            'preco': float(marmita.preco),
            'quantidade': quantidade,
            'imagem': marmita.imagem
        })
    
    salvar_carrinho(carrinho)
    flash(f'{marmita.nome} adicionado ao carrinho!', 'success')
    return redirect(url_for('cardapio'))

@app.route('/remover_carrinho/<int:index>')
@login_required
def remover_carrinho(index):
    carrinho = get_carrinho()
    if 0 <= index < len(carrinho):
        item_removido = carrinho.pop(index)
        salvar_carrinho(carrinho)
        flash(f'{item_removido["nome"]} removido do carrinho!', 'success')
    return redirect(url_for('carrinho'))

@app.route('/atualizar_carrinho', methods=['POST'])
@login_required
def atualizar_carrinho():
    carrinho = get_carrinho()
    for i, item in enumerate(carrinho):
        nova_quantidade = int(request.form.get(f'quantidade_{i}', 1))
        if nova_quantidade > 0:
            item['quantidade'] = nova_quantidade
        else:
            carrinho.pop(i)
            break
    
    salvar_carrinho(carrinho)
    flash('Carrinho atualizado!', 'success')
    return redirect(url_for('carrinho'))

@app.route('/carrinho')
@login_required
def carrinho():
    carrinho_itens = get_carrinho()
    total = calcular_total_carrinho()
    return render_template('carrinho.html', carrinho=carrinho_itens, total=total)

@app.route('/finalizar_pedido', methods=['GET', 'POST'])
@login_required
def finalizar_pedido():
    carrinho_itens = get_carrinho()
    
    if not carrinho_itens:
        flash('Seu carrinho está vazio!', 'error')
        return redirect(url_for('cardapio'))
    
    if request.method == 'POST':
        endereco_entrega = request.form.get('endereco_entrega', '').strip()
        observacoes = request.form.get('observacoes', '')
        
        if not endereco_entrega and not current_user.endereco:
            flash('Por favor, informe um endereço de entrega.', 'error')
            return redirect(url_for('finalizar_pedido'))
        
        # Usa o endereço do usuário se não foi informado um novo
        endereco_final = endereco_entrega if endereco_entrega else current_user.endereco
        
        # Cria o pedido
        total_pedido = calcular_total_carrinho()
        novo_pedido = Pedido(
            user_id=current_user.id,
            total=total_pedido,
            endereco_entrega=endereco_final,
            status='confirmado'
        )
        
        db.session.add(novo_pedido)
        db.session.flush()  # Para obter o ID do pedido
        
        # Adiciona os itens do pedido
        for item in carrinho_itens:
            item_pedido = ItemPedido(
                pedido_id=novo_pedido.id,
                marmita_id=item['marmita_id'],
                quantidade=item['quantidade'],
                preco_unitario=item['preco'],
                status_item='enviando_restaurante',
                observacoes=observacoes
            )
            db.session.add(item_pedido)
        
        db.session.commit()
        
        # Limpa o carrinho
        session.pop('carrinho', None)
        
        flash('Pedido realizado com sucesso! Acompanhe o status em "Meus Pedidos".', 'success')
        return redirect(url_for('pedidos'))
    
    total = calcular_total_carrinho()
    return render_template('finalizar_pedido.html', carrinho=carrinho_itens, total=total)

@app.route('/pedidos')
@login_required
def pedidos():
    user_pedidos = Pedido.query.filter_by(user_id=current_user.id).order_by(Pedido.data_pedido.desc()).all()
    return render_template('pedidos.html', pedidos=user_pedidos)

@app.route('/detalhes_pedido/<int:pedido_id>')
@login_required
def detalhes_pedido(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    
    # Verifica se o pedido pertence ao usuário logado
    if pedido.user_id != current_user.id:
        flash('Acesso não autorizado!', 'error')
        return redirect(url_for('pedidos'))
    
    itens_pedido = ItemPedido.query.filter_by(pedido_id=pedido_id).all()
    return render_template('detalhes_pedido.html', pedido=pedido, itens_pedido=itens_pedido)

# NOVAS ROTAS PARA A COMANDA
@app.route('/area_empresa')
@login_required
def area_empresa():
    # Verifica se é uma empresa
    if not hasattr(current_user, 'nome'):
        flash('Acesso não autorizado para esta área!', 'error')
        return redirect(url_for('index'))
    
    # Busca todos os itens de pedido que precisam ser preparados
    itens_pedido = ItemPedido.query.join(Pedido).filter(
        ItemPedido.status_item.in_(['enviando_restaurante', 'em_andamento', 'entregando'])
    ).order_by(ItemPedido.id.desc()).all()
    
    return render_template('area_empresa.html', itens_pedido=itens_pedido)

@app.route('/atualizar_status_item/<int:item_id>/<novo_status>')
@login_required
def atualizar_status_item(item_id, novo_status):
    # Verifica se é uma empresa
    if not hasattr(current_user, 'nome'):
        flash('Acesso não autorizado!', 'error')
        return redirect(url_for('index'))
    
    item = ItemPedido.query.get_or_404(item_id)
    
    # Verifica se o status é válido
    status_validos = ['enviando_restaurante', 'em_andamento', 'entregando', 'concluido']
    if novo_status not in status_validos:
        flash('Status inválido!', 'error')
        return redirect(url_for('area_empresa'))
    
    item.status_item = novo_status
    db.session.commit()
    
    flash(f'Status do item atualizado para {novo_status.replace("_", " ").title()}!', 'success')
    return redirect(url_for('area_empresa'))

@app.route('/comanda_detalhes/<int:pedido_id>')
@login_required
def comanda_detalhes(pedido_id):
    # Verifica se é uma empresa
    if not hasattr(current_user, 'nome'):
        flash('Acesso não autorizado!', 'error')
        return redirect(url_for('index'))
    
    pedido = Pedido.query.get_or_404(pedido_id)
    itens_pedido = ItemPedido.query.filter_by(pedido_id=pedido_id).all()
    
    return render_template('comanda_detalhes.html', pedido=pedido, itens_pedido=itens_pedido)

# Rotas simples
@app.route('/perfil')
@login_required
def perfil(): 
    return render_template('perfil.html')

# Dados de exemplo
def add_sample_data():
    if Marmita.query.count() == 0:
        sample_marmitas = [
            Marmita(nome='Marmita Fitness Frango', descricao='Frango grelhado, arroz integral, brócolis e batata doce', preco=25.90, categoria='fitness', tamanho='media'),
            Marmita(nome='Marmita Vegetariana', descricao='Quinoa, grão-de-bico, legumes assados e salada', preco=22.50, categoria='vegetariana', tamanho='media'),
            Marmita(nome='Marmita Low Carb', descricao='Carne moída, abobrinha refogada, salada verde', preco=28.90, categoria='lowcarb', tamanho='media'),
            Marmita(nome='Marmita Fitness Peixe', descricao='Filé de peixe grelhado, arroz integral, legumes no vapor', preco=27.90, categoria='fitness', tamanho='media'),
            Marmita(nome='Marmita Vegana', descricao='Lentilha, abóbora assada, couve e quinoa', preco=24.90, categoria='vegana', tamanho='media'),
            Marmita(nome='Marmita Kids', descricao='Arroz, feijão, carne moída e batata frita', preco=20.90, categoria='kids', tamanho='pequena')
        ]
        db.session.add_all(sample_marmitas)
        
        # Criar empresa de exemplo
        if Empresa.query.filter_by(nome='Restaurante Exemplo').first() is None:
            empresa = Empresa(
                nome='Restaurante Exemplo',
                email='restaurante@exemplo.com',
                password=generate_password_hash('123456'),
                endereco='Rua Exemplo, 123'
            )
            db.session.add(empresa)
        
        db.session.commit()
        print("Dados de exemplo adicionados")

# Função para deletar e recriar o banco (APENAS PARA DESENVOLVIMENTO)
def recreate_database():
    print("Recriando banco de dados...")
    db.drop_all()
    db.create_all()
    add_sample_data()
    print("Banco de dados recriado com sucesso!")

if __name__ == '__main__':
    with app.app_context():
        # CORREÇÃO: Recriar o banco de dados para incluir as novas colunas
        recreate_database()
    
    # CORREÇÃO PARA O RENDER
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)