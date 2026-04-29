from fastapi import FastAPI, Depends, HTTPException
from sqlmodel import Session, select
from models import engine, User, Category, Transaction, create_db_and_tables
from sqlmodel import func # Importe o 'func' lá no topo junto com os outros
import hashlib
import os
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi import Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import selectinload # Adicione este import no topo
from fastapi.staticfiles import StaticFiles # Adicione este import no topo
from fastapi import Response # Adicione ao topo
from fastapi import Cookie # Adicione ao topo
from typing import List, Optional  # Adicione o Optional aqui
from fastapi import FastAPI, Depends, HTTPException, Form, Response, Cookie, Request
import ast # Adicione este import no topo do arquivo
from sqlalchemy import extract
from datetime import datetime
import csv
from io import StringIO
from fastapi.responses import StreamingResponse
from dateutil.relativedelta import relativedelta # Você vai precisar instalar: pip install python-dateutil



# Configura onde estão os arquivos HTML
templates = Jinja2Templates(directory="templates")


app = FastAPI(title="Gerenciador de Finanças Pro")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Criar o banco de dados ao iniciar a aplicação
@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# Função auxiliar (Dependency Injection) para gerenciar a sessão do banco
def get_session():
    with Session(engine) as session:
        yield session



# ---- SISTEMA DE LOGIN ------


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="login.html", 
        context={"request": request}
    )

@app.post("/login")
def login(response: Response, email: str = Form(...), password: str = Form(...), session: Session = Depends(get_session)):
    # 1. Busca o usuário pelo e-mail
    user = session.exec(select(User).where(User.email == email)).first()
    
    # 2. Verifica se o usuário existe e se a senha (hash) bate
    if not user or not verify_password(user.hashed_password, password):
        # Em vez de erro 500, vamos retornar uma mensagem amigável se errar
        return HTMLResponse(content="<script>alert('E-mail ou senha incorretos'); window.location='/login';</script>")
    
    # 3. Cria um Cookie de sessão com o ID do usuário
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="user_id", value=str(user.id))
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("user_id")
    return response





# Rota de teste (Root)
#@app.get("/")
#def read_root():
#    return {"mensagem": "API de Finanças está online!"}

# ------- ROTA HOME ----------------------------

@app.get("/", response_class=HTMLResponse)
def home(
    request: Request, 
    user_id: Optional[str] = Cookie(None), 
    mes: Optional[int] = None, 
    ano: Optional[int] = None,
    session: Session = Depends(get_session)
):
    if not user_id:
        return RedirectResponse(url="/login")
    
    user = session.get(User, int(user_id))
    
    # Se não for passado mês/ano, usamos o atual
    mes_atual = mes or datetime.now().month
    ano_atual = ano or datetime.now().year

    # Filtro base por usuário e data
    base_query = select(Transaction).where(
        Transaction.user_id == user.id,
        extract('month', Transaction.date) == mes_atual,
        extract('year', Transaction.date) == ano_atual
    )

    # 1. Transações filtradas
    transacoes = session.exec(base_query.options(selectinload(Transaction.category))).all()
    
    # 2. Resumo calculado apenas para o mês selecionado
    receitas = sum(t.amount for t in transacoes if t.type == "receita")
    despesas = sum(t.amount for t in transacoes if t.type == "despesa")
    
    resumo_filtrado = {
        "total_receitas": round(receitas, 2),
        "total_despesas": round(despesas, 2),
        "saldo_atual": round(receitas - despesas, 2)
    }

    # 3. Categorias e Gráfico (também filtrados)
    categorias = session.exec(select(Category).where(Category.user_id == user.id)).all()
    
    # Lógica do gráfico para o mês
    dados_grafico = {}
    for t in transacoes:
        if t.type == "despesa":
            nome_cat = t.category.name
            dados_grafico[nome_cat] = dados_grafico.get(nome_cat, 0) + t.amount

    contexto = {
        "request": request,
        "usuario": user,
        "resumo": resumo_filtrado,
        "transacoes": transacoes,
        "categorias_disponiveis": categorias,
        "labels_grafico": list(dados_grafico.keys()),
        "valores_grafico": list(dados_grafico.values()),
        "mes_selecionado": mes_atual,
        "ano_selecionado": ano_atual,
        "date_atual": datetime.now().strftime("%Y-%m-%d")
    }
    
    return templates.TemplateResponse(request=request, name="index.html", context=contexto)








# --- ESPAÇO PARA AS ROTAS DE USUÁRIO E CATEGORIA QUE CRIAREMOS A SEGUIR ---


# Função simples e segura para criar o hash da senha
def hash_password(password: str):
    # Criamos um 'tempero' (salt) para a senha ser impossível de descriptografar
    salt = os.urandom(32) 
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt + key  # Guardamos o salt junto com a chave

# Função para verificar se a senha está correta (usaremos no login depois)
def verify_password(stored_password_str, provided_password):
    try:
        # Como salvamos str(senha_segura), o banco guardou algo como "b'\x...' "
        # Precisamos converter essa string de volta para o formato de bytes real
        stored_password_bytes = ast.literal_eval(stored_password_str)
        
        salt = stored_password_bytes[:32]
        stored_key = stored_password_bytes[32:]
        
        new_key = hashlib.pbkdf2_hmac(
            'sha256', 
            provided_password.encode('utf-8'), 
            salt, 
            100000
        )
        return new_key == stored_key
    except Exception as e:
        print(f"Erro na verificação: {e}")
        return False


# Rota para Criar Usuário
# 1. Crie um modelo apenas para a criação (sem o ID e com a senha pura)
from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    email: str
    password: str  # Nome diferente de 'hashed_password' para não confundir

# 2. Atualize a rota de cadastro
@app.post("/users/")
def create_user(user_data: UserCreate, session: Session = Depends(get_session)):
    try:
        # Usamos nossa nova função que não depende do bcrypt problemático
        senha_segura = hash_password(user_data.password)
        
        novo_usuario = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=str(senha_segura) # Salvamos como string
        )
        
        session.add(novo_usuario)
        session.commit()
        session.refresh(novo_usuario)
        
        return {"status": "sucesso", "usuario": novo_usuario.username}
        
    except Exception as e:
        session.rollback()
        print(f"ERRO: {e}")
        raise HTTPException(status_code=500, detail=str(e))





@app.post("/categories/")
def create_category(category: Category, session: Session = Depends(get_session)):
    try:
        session.add(category)
        session.commit()
        session.refresh(category)
        return category
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao criar categoria: {e}")




@app.post("/transactions/")
def create_transaction(transaction: Transaction, session: Session = Depends(get_session)):
    try:
        session.add(transaction)
        session.commit()
        session.refresh(transaction)
        return transaction
    except Exception as e:
        session.rollback()
        # O erro 400 indica que o usuário enviou algo errado (ex: um ID que não existe)
        raise HTTPException(status_code=400, detail=f"Erro ao registrar transação: {e}")




@app.get("/users/{user_id}/transactions/")
def list_transactions(user_id: int, session: Session = Depends(get_session)):
    statement = select(Transaction).where(Transaction.user_id == user_id)
    results = session.exec(statement).all()
    return results


@app.get("/users/")
def list_users(session: Session = Depends(get_session)):
    # O 'select(User)' é como o comando 'SELECT * FROM user' do SQL
    users = session.exec(select(User)).all()
    return users


@app.get("/users/{user_id}/summary/")
def get_user_summary(user_id: int, session: Session = Depends(get_session)):
    # 1. Somar todas as Receitas
    query_receitas = select(func.sum(Transaction.amount)).where(
        Transaction.user_id == user_id, 
        Transaction.type == "receita"
    )
    total_receitas = session.exec(query_receitas).one() or 0.0

    # 2. Somar todas as Despesas
    query_despesas = select(func.sum(Transaction.amount)).where(
        Transaction.user_id == user_id, 
        Transaction.type == "despesa"
    )
    total_despesas = session.exec(query_despesas).one() or 0.0

    # 3. Calcular o Saldo
    saldo = total_receitas - total_despesas

    return {
        "usuario_id": user_id,
        "total_receitas": round(total_receitas, 2),
        "total_despesas": round(total_despesas, 2),
        "saldo_atual": round(saldo, 2)
    }

# Rota para ver TODAS as categorias do sistema (útil para o administrador)
@app.get("/categories/")
def list_all_categories(session: Session = Depends(get_session)):
    categories = session.exec(select(Category)).all()
    return categories

# Rota para ver as categorias de um usuário específico (A mais usada no dia a dia)
@app.get("/users/{user_id}/categories/")
def list_user_categories(user_id: int, session: Session = Depends(get_session)):
    statement = select(Category).where(Category.user_id == user_id)
    categories = session.exec(statement).all()
    
    if not categories:
        return {"mensagem": "Este usuário ainda não criou categorias."}
        
    return categories


@app.get("/users/{user_id}/summary/categories/")
def get_summary_by_category(user_id: int, session: Session = Depends(get_session)):
    # Esta consulta busca o nome da categoria e a soma dos valores
    # agrupando tudo pelo nome da categoria
    statement = (
        select(Category.name, func.sum(Transaction.amount).label("total"))
        .join(Transaction)
        .where(Transaction.user_id == user_id)
        .group_by(Category.name)
    )
    results = session.exec(statement).all()
    
    # Transforma o resultado em um formato fácil de ler: {"Alimentação": 100.0, "Lazer": 50.0}
    return {name: round(total, 2) for name, total in results}


@app.patch("/categories/{category_id}")
def update_category(category_id: int, category_data: dict, session: Session = Depends(get_session)):
    # 1. Buscar a categoria original no banco
    db_category = session.get(Category, category_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    
    # 2. Atualizar apenas os campos que você enviou no JSON
    for key, value in category_data.items():
        setattr(db_category, key, value)
    
    session.add(db_category)
    session.commit()
    session.refresh(db_category)
    return db_category


@app.delete("/categories/{category_id}")
def delete_category(category_id: int, session: Session = Depends(get_session)):
    db_category = session.get(Category, category_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    
    session.delete(db_category)
    session.commit()
    return {"ok": True, "mensagem": f"Categoria {category_id} removida com sucesso"}


@app.patch("/transactions/{transaction_id}")
def update_transaction(transaction_id: int, transaction_data: dict, session: Session = Depends(get_session)):
    # 1. Busca a transação específica pelo ID
    db_transaction = session.get(Transaction, transaction_id)
    if not db_transaction:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    
    # 2. Aplica as mudanças (ex: mudar 'despesas' para 'despesa')
    for key, value in transaction_data.items():
        setattr(db_transaction, key, value)
    
    session.add(db_transaction)
    session.commit()
    session.refresh(db_transaction)
    return db_transaction


# Rota para receber dados do formulário HTML
@app.post("/transactions/web")
def create_transaction_web(
    description: str = Form(...),
    amount: float = Form(...), # Este passa a ser o VALOR TOTAL
    type: str = Form(...),
    category_id: int = Form(...),
    date: str = Form(...),
    repeats: int = Form(1),
    user_id: str = Cookie(None),
    session: Session = Depends(get_session)
):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
        
    data_inicial = datetime.strptime(date, "%Y-%m-%d")

    # --- O PULO DO GATO ---
    # Calculamos quanto vale cada parcela
    valor_parcela = amount / repeats if repeats > 0 else amount

    for i in range(repeats):
        nova_data = data_inicial + relativedelta(months=i)
        desc_final = f"{description} ({i+1}/{repeats})" if repeats > 1 else description

        nova_transacao = Transaction(
            description=desc_final,
            amount=round(valor_parcela, 2), # Salvamos o valor dividido
            type=type,
            user_id=int(user_id),
            category_id=category_id,
            date=nova_data
        )
        session.add(nova_transacao)
    
    session.commit()
    return RedirectResponse(url=f"/?mes={data_inicial.month}&ano={data_inicial.year}", status_code=303)




@app.post("/transactions/delete/{transaction_id}")
def delete_transaction_web(transaction_id: int, session: Session = Depends(get_session)):
    db_transaction = session.get(Transaction, transaction_id)
    if db_transaction:
        session.delete(db_transaction)
        session.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/categories/web")
def create_category_web(name: str = Form(...), session: Session = Depends(get_session)):
    # Criamos a categoria para o usuário 1
    nova_cat = Category(name=name, user_id=1)
    session.add(nova_cat)
    session.commit()
    return RedirectResponse(url="/", status_code=303)


# Rota para mostrar a página de cadastro
@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="register.html", 
        context={"request": request}
    )

# Rota para processar o cadastro
@app.post("/register")
def register(
    username: str = Form(...), 
    email: str = Form(...), 
    password: str = Form(...), 
    session: Session = Depends(get_session)
):
    # 1. Verifica se o e-mail já existe para evitar erro de banco
    user_exists = session.exec(select(User).where(User.email == email)).first()
    if user_exists:
        return HTMLResponse(content="<script>alert('Este e-mail já está cadastrado!'); window.location='/register';</script>")

    # 2. Cria o novo usuário com nossa função de hash segura
    novo_usuario = User(
        username=username,
        email=email,
        hashed_password=str(hash_password(password)) # Converte para string para o SQLite
    )
    
    session.add(novo_usuario)
    session.commit()
    
    # 3. Redireciona para o login após o sucesso
    return RedirectResponse(url="/login", status_code=303)



@app.get("/exportar")
def exportar_csv(user_id: Optional[str] = Cookie(None), session: Session = Depends(get_session)):
    if not user_id:
        return RedirectResponse(url="/login")

    transacoes = session.exec(select(Transaction).where(Transaction.user_id == int(user_id))).all()

    output = StringIO()
    # Mudamos o delimitador para ';' que é o padrão do Excel no Brasil
    writer = csv.writer(output, delimiter=';') 
    
    writer.writerow(['Data', 'Descrição', 'Categoria', 'Tipo', 'Valor'])

    for t in transacoes:
        writer.writerow([
            t.date.strftime("%d/%m/%Y"), 
            t.description, 
            t.category.name, 
            t.type, 
            str(t.amount).replace('.', ',') # Opcional: troca ponto por vírgula no valor
        ])

    # O "pulo do gato": Convertemos o UTF-8 para Latin-1 (cp1252) para o Excel ler acentos
    conteudo_final = output.getvalue().encode('cp1252', errors='replace')
    
    return Response(
        content=conteudo_final,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=minhas_financas.csv"}
    )


# 1. Rota para exibir o formulário de edição
@app.get("/transactions/edit/{transaction_id}", response_class=HTMLResponse)
def edit_transaction_page(request: Request, transaction_id: int, session: Session = Depends(get_session)):
    transacao = session.get(Transaction, transaction_id)
    categorias = session.exec(select(Category).where(Category.user_id == transacao.user_id)).all()
    
    return templates.TemplateResponse(
        request=request, 
        name="edit_transaction.html", 
        context={"request": request, "transacao": transacao, "categorias": categorias}
    )

# 2. Rota para processar a edição
@app.post("/transactions/edit/{transaction_id}")
def edit_transaction_submit(
    transaction_id: int,
    description: str = Form(...),
    amount: float = Form(...),
    type: str = Form(...),
    category_id: int = Form(...),
    date: str = Form(...),
    session: Session = Depends(get_session)
):
    db_transacao = session.get(Transaction, transaction_id)
    if db_transacao:
        db_transacao.description = description
        db_transacao.amount = amount
        db_transacao.type = type
        db_transacao.category_id = category_id
        db_transacao.date = datetime.strptime(date, "%Y-%m-%d")
        
        session.add(db_transacao)
        session.commit()
        
    return RedirectResponse(url=f"/?mes={db_transacao.date.month}&ano={db_transacao.date.year}", status_code=303)
