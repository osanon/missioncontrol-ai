"""Conservative SQL grammar, table/function allowlists, plus a separate read-only DB role."""
from decimal import Decimal
from datetime import date, datetime
import sqlglot
from sqlglot import exp
from sqlalchemy import text
from backend.db import reader, DATA_TABLES

FUNCTIONS={'COUNT','SUM','AVG','MIN','MAX','ROUND','COALESCE','NULLIF','LOWER','UPPER','ABS','CAST','EXTRACT','CASE','IF'}
NODES={'Select','From','Table','Identifier','Column','Star','Alias','TableAlias','Join','Where','Group','Having','Order','Ordered','Limit','Offset','Literal','Null','Boolean','Distinct','Paren','Subquery','With','CTE','Union','Intersect','Except','EQ','NEQ','GT','GTE','LT','LTE','And','Or','Not','Is','In','Between','Like','ILike','Add','Sub','Mul','Div','Mod','Neg','DataType','DataTypeParam','When','Exists'}

def validate_sql(sql):
    if len(sql)>12000:raise ValueError('SQL exceeds the size limit.')
    try: statements=sqlglot.parse(sql,read='postgres')
    except sqlglot.errors.ParseError as e:raise ValueError('SQL could not be parsed.') from e
    if len(statements)!=1 or not isinstance(statements[0],(exp.Select,exp.Union,exp.Intersect,exp.Except)):
        raise ValueError('Only one SELECT query is allowed.')
    tree=statements[0]
    ctes={n.alias_or_name for n in tree.find_all(exp.CTE)}
    if ctes.intersection(DATA_TABLES):raise ValueError('CTEs cannot shadow source tables.')
    for node in tree.walk():
        if isinstance(node,exp.Func):
            name=node.sql_name() if not isinstance(node,exp.Anonymous) else node.name.upper()
            if name not in FUNCTIONS:raise ValueError(f'Function {name} is not allowed.')
        elif type(node).__name__ not in NODES:
            raise ValueError(f'SQL construct {type(node).__name__} is not allowed.')
        if isinstance(node,exp.With) and node.args.get('recursive'):
            raise ValueError('Recursive queries are not allowed.')
        if isinstance(node,exp.Table):
            if node.db or node.catalog or node.name not in set(DATA_TABLES)|ctes:
                raise ValueError('Only approved demo tables are available.')
        if isinstance(node,exp.DataType) and str(node.this).split('.')[-1] not in {'INT','BIGINT','FLOAT','DOUBLE','DECIMAL','TEXT','VARCHAR','DATE','BOOLEAN','UNKNOWN'}:
            raise ValueError('Cast type is not allowed.')
    return tree.sql(dialect='postgres')

def safe_query(sql):
    clean=validate_sql(sql)
    with reader.connect() as c:
        if c.dialect.name=='postgresql':
            c.execute(text('SET TRANSACTION READ ONLY'))
            c.execute(text("SET LOCAL statement_timeout = '3000ms'"))
        # Result cap cannot be overridden by a model-supplied LIMIT.
        result=c.execute(text(f'SELECT * FROM ({clean}) AS bounded_result LIMIT 201'))
        rows=[{k:float(v) if isinstance(v,Decimal) else v.isoformat() if isinstance(v,(date,datetime)) else v for k,v in x.items()} for x in result.mappings()]
    return {'sql':clean,'rows':rows[:200],'truncated':len(rows)>200,'limit':200}
