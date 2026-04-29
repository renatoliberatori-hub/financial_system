from typing import List, Optional
from sqlmodel import Field, Relationship, SQLModel, create_engine
from datetime import datetime

# 1. MODELO DE USUÁRIO
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    email: str = Field(unique=True)
    hashed_password: str
    
    # Relacionamentos
    categories: List["Category"] = Relationship(back_populates="user")
    transactions: List["Transaction"] = Relationship(back_populates="user")

# 2. MODELO DE CATEGORIA (A nova tabela!)
class Category(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    color: Optional[str] = "#000000"  # Para usar em gráficos no futuro!
    
    # Chave estrangeira para o Usuário (cada um tem suas categorias)
    user_id: int = Field(foreign_key="user.id")
    user: User = Relationship(back_populates="categories")
    
    # Relacionamento com Transações
    transactions: List["Transaction"] = Relationship(back_populates="category")

# 3. MODELO DE TRANSAÇÃO
class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    description: str
    amount: float
    type: str  # "receita" ou "despesa"
    date: datetime = Field(default_factory=datetime.utcnow)
    
    # Ligação com Usuário
    user_id: int = Field(foreign_key="user.id")
    user: User = Relationship(back_populates="transactions")
    
    # Ligação com Categoria (Chave Estrangeira)
    category_id: int = Field(foreign_key="category.id")
    category: Category = Relationship(back_populates="transactions")

# Configuração do Banco (Igual ao anterior)
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, echo=True)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

if __name__ == "__main__":
    create_db_and_tables()
