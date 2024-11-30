from fastapi import FastAPI, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from sqlmodel import Field, SQLModel, create_engine, Session, select
from typing import Optional
from pydantic import BaseModel
from decimal import Decimal
import yfinance as yf

class StockBase(SQLModel):
    symbol: str = Field(unique=True, index=True)
    price: Decimal = Field(default=0, max_digits=12, decimal_places=2)
    forward_pe: Decimal = Field(default=0, max_digits=12, decimal_places=2)
    forward_eps: Decimal = Field(default=0, max_digits=12, decimal_places=2)
    dividend_yield: Decimal = Field(default=0, max_digits=12, decimal_places=2)
    ma50: Decimal = Field(default=0, max_digits=12, decimal_places=2)
    ma200: Decimal = Field(default=0, max_digits=12, decimal_places=2)

class Stock(StockBase, table= True):
    id: int = Field(default= None, primary_key=True)

class StockRequest(BaseModel):
    symbol: str

    # @validator('symbol') # to be corrected
    # def validate_symbol(cls, v):
    #     if not v.isupper():
    #         raise ValueError("Stock symbol must be uppercase.")
    #     return v
    

db_url = "sqlite:///stock.db"
engine = create_engine(db_url, echo= True)

def create_db_and_table():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

app = FastAPI(docs_url="/records")

templates = Jinja2Templates(directory="templates")

@app.on_event('startup')
async def on_startup():
    create_db_and_table()

@app.get('/')
async def home(
    request: Request,
    forward_pe: Optional[str] = None,  
    dividend_yield: Optional[str] = None,
    ma50: Optional[bool] = None,
    ma200: Optional[bool] = None,
    session: Session = Depends(get_session)
):
    """
    Displays the stock screener dashboard / homepage
    """
    query = select(Stock)

    if forward_pe:
        try:
            forward_pe_value = float(forward_pe)  
            query = query.filter(Stock.forward_pe > Decimal(forward_pe_value))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid value for forward_pe")

    
    if dividend_yield:
        try:
            dividend_yield_value = float(dividend_yield)  
            query = query.filter(Stock.dividend_yield > Decimal(dividend_yield_value))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid value for dividend_yield")

    
    if ma50:
        query = query.filter(Stock.price > Stock.ma50)
    if ma200:
        query = query.filter(Stock.price > Stock.ma200)

    
    stocks = session.exec(query).all()

    return templates.TemplateResponse("home.htm", {
        "request": request,
        "stocks": stocks,
        "dividend_yield": dividend_yield,
        "forward_pe": forward_pe,
        "ma200": ma200,
        "ma50": ma50,
        "made_with": "❤️"
    })

# {'message': "200 all ok!"}


async def fetch_stock_data(id: int):
    with Session(engine) as session:
        stock = session.exec(select(Stock).where(Stock.id == id)).first()
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found.")
        
        try:
            yahoo_data = yf.Ticker(stock.symbol)
            stock.ma200 = yahoo_data.info.get('twoHundredDayAverage', 0)
            stock.ma50 = yahoo_data.info.get('fiftyDayAverage', 0)
            stock.price = yahoo_data.info.get('previousClose', 0)
            stock.forward_pe = yahoo_data.info.get('forwardPE', 0)
            stock.forward_eps = yahoo_data.info.get('forwardEps', 0)
            dividend_yield = yahoo_data.info.get('dividendYield')
            stock.dividend_yield = dividend_yield * 100 if dividend_yield else 0
            
            session.add(stock)
            session.commit()
        except Exception as e:
            print(f"Error fetching stock data: {e}")


# async def fetch_stock_data(id: int):
#     with Session(engine) as session:
#         stock = session.exec(select(Stock).where(Stock.id == id)).first() #Stock).filter(Stock.id == id).first()
#         if not stock:
#             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found ...")
#         # stock.forward_pe = 10

#         yahoo_data = yf.Ticker(stock.symbol)

#         stock.ma200 = yahoo_data.info['twoHundredDayAverage']
#         stock.ma50 = yahoo_data.info['fiftyDayAverage']
#         stock.price = yahoo_data.info['previousClose']
#         stock.forward_pe = yahoo_data.info['forwardPE']
#         stock.forward_eps = yahoo_data.info['forwardEps']
#         if yahoo_data.info['dividendYield'] is not None:
#             stock.dividend_yield = yahoo_data.info['dividendYield'] * 100

#         session.add(stock)
#         session.commit()
        



@app.get("/stock")
async def get_all_stocks(session: Session= Depends(get_session)):
    all_stocks = session.exec(select(Stock)).all()
    return all_stocks


@app.post("/stock")
async def create_stock(stock_request: StockRequest, background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    """
    created a stock and stores ikt in the database
    """
    existing_stock = session.exec(select(Stock).where(Stock.symbol == stock_request.symbol)).first()
    if existing_stock:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stock symbol already exists.")
    
    stock = Stock(symbol=stock_request.symbol)
    session.add(stock)
    session.commit()
    
    background_tasks.add_task(fetch_stock_data, stock.id)
    
    return {
        "code": "success",
        "message": "Stock created"
    }


# @app.post("/stock")
# async def create_stock(stock_request: StockRequest, background_tasks: BackgroundTasks, session: Session= Depends(get_session)):

#     stock = Stock()
#     stock.symbol = stock_request.symbol

#     session.add(stock)
#     session.commit()
#     background_tasks.add_task(fetch_stock_data, stock.id)
    
#     return {
#         "code":"success", 
#         "message": "stock created"
#     }