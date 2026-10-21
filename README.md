# Mesa de Compras

Sistema de compras do galpão. Registra tudo o que é comprado e faz a conta reversa:
**quanto posso pagar no produto para o seller ganhar 10% líquido nos marketplaces.**

Conta usada em todo o sistema:

```
custo com desconto ÷ 0,70  = preço do galpão
preço de venda − taxa média dos marketplaces − imposto − custo extra − preço do galpão = sobra do seller
```

A taxa é a **média** dos marketplaces marcados na aba Taxas (Shopee CNPJ, Shopee CPF, ML Clássico, ML Premium, TikTok Shop, Kwai, Shein). Todas as faixas são editáveis.

## Abas

- **Pesquisa de preço**: tira foto pela câmera do celular, digita nome ou código. A IA identifica o produto, pesquisa preços no Mercado Livre, Shopee e TikTok Shop e mostra quanto pagar para o seller ter 3%, 6%, 9% e 10%. Também lê preços colados ou prints.
- **Compras**: lista de compras com tabela, desconto, custo real, preço do galpão, sobra do seller e o limite de compra.
- **Taxas**: tabelas de cada marketplace e quais entram na média.

## Rodar no computador

```
python3 -m venv .venv && source .venv/bin/activate
```

```
pip install -r requirements-dev.txt
```

```
cp .env.example .env
```

Edite o `.env` (para teste local use `COOKIE_SECURE=0` e apague a linha `DATABASE_URL`), depois:

```
set -a && source .env && set +a && uvicorn app.main:app --reload --port 8090
```

Abra http://localhost:8090

Testes:

```
python -m pytest -q
```

## Instalar na VPS (Ubuntu 24.04, mesma do CRM)

1. Banco no Postgres:

```
sudo -u postgres psql -c "CREATE USER mesa WITH PASSWORD 'TROQUE_A_SENHA';" -c "CREATE DATABASE mesa_compras OWNER mesa;"
```

2. Código:

```
sudo git clone https://github.com/medson124/mesa-de-compras.git /opt/mesa-de-compras
```

```
cd /opt/mesa-de-compras && sudo python3 -m venv .venv && sudo .venv/bin/pip install -r requirements.txt
```

3. Configuração (preencha senha, SECRET_KEY, DATABASE_URL e ANTHROPIC_API_KEY):

```
sudo cp .env.example .env && sudo nano .env
```

4. Serviço:

```
sudo cp deploy/mesa-de-compras.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now mesa-de-compras
```

5. Domínio + HTTPS (crie antes o registro DNS `compras` apontando para o IP da VPS):

```
sudo cp deploy/nginx-compras.conf /etc/nginx/sites-available/compras && sudo ln -s /etc/nginx/sites-available/compras /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx
```

```
sudo certbot --nginx -d compras.intermediacaologistica.com.br
```

Atualizar depois de um novo PR aprovado:

```
cd /opt/mesa-de-compras && sudo git pull && sudo .venv/bin/pip install -r requirements.txt && sudo systemctl restart mesa-de-compras
```

## IA

Usa a API da Anthropic (`ANTHROPIC_API_KEY`). A busca de preços usa a pesquisa na web da API, restrita a mercadolivre.com.br, shopee.com.br e tiktok.com. Sem a chave, o sistema funciona normalmente com preços digitados.
